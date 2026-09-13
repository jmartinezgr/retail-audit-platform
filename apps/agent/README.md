# AuditLake Copilot — Phases 1 & 2

A conversational agent over AuditLake's audit pipeline, built with LangGraph.
Full spec and rationale for the whole 4-phase plan: [`docs/copilot-spec.md`](../../docs/copilot-spec.md).
Covers Phase 1 (minimum viable agent, plus one tool added beyond the
original spec) and Phase 2 (explaining why an invoice failed, plus one
tool added there too) — both explained below, with the real evidence
that made each addition necessary.

## What it does

```
$ python -m agent "Which rules failed most often in dataset <upload_id>?"
The top 3 rules that failed most often are:
1. factura_total_cuadra (ERROR) - 7 invoices
2. cantidad_dentro_de_transferencias (WARNING) - 4 invoices
3. comprador_existe (WARNING) - 3 invoices
```

Every factual claim in that answer came from a real HTTP call to the running
backend — the agent never computes an audit result itself. If a rule name
doesn't exist or a dataset hasn't finished processing, it says so instead of
guessing.

## Why LangChain vs. LangGraph

LangChain is the toolbox — model wrappers, the `@tool` decorator, message
types. LangGraph (built on top of it) is the orchestrator: the agent is
modeled as a **state graph**, not a hand-rolled `while` loop. Nodes are units
of work (`agent` calls the LLM, `tools` executes whatever it asked for),
edges — including *conditional* edges — decide where to go next based on the
current state. That's what makes the step cap and the "loop until done"
behavior declarative instead of imperative: `route_after_agent()` (in
`agent/graph.py`) is the single place that decides tool-call vs. finalize vs.
stop, instead of that logic being scattered through a manual loop.

## Architecture

```
agent/
  settings.py   backend URL, Ollama config, MAX_STEPS
  state.py      AgentState: messages (reducer: add_messages) + step_count
  tools.py      get_rule, query_gold_results, summarize_dataset
  graph.py      the StateGraph: agent -> tools -> agent -> ... -> finalize/end
  __main__.py   `python -m agent "question"`
```

`agent -> tools` is the *only* dependency direction that matters here:
**the agent never imports the backend's `infrastructure/` layer.** It talks
to the already-running FastAPI backend over plain HTTP (`httpx`). This was a
deliberate decision (see `docs/PLANNING.md` §… agent phase) over importing
`infrastructure/storage/duckdb_query.py` directly: the agent needs zero
Postgres/R2 credentials of its own, and "the backend must be running to test
this" is an explicit, obvious requirement instead of a hidden one.

## The tools

### `get_rule(rule_id)`

Returns a rule's definition — built-in (18 hardcoded rules) or user-defined.
Checks user-defined rules first (`GET /rules/`), then falls back to a new
**static rule catalog** (`GET /rules/static/{name}`, backed by
`packages/domain/src/domain/rules/catalog.py`).

That catalog didn't exist before this phase. The spec's own instruction is
"if a tool needs logic that doesn't exist yet, stop and flag it rather than
inventing it" — the 18 built-in rules were only ever described as prose in
`docs/DATA_MODEL.md` and hardcoded Polars logic in `engine.py`, with no
queryable structured form. Adding `catalog.py` packages that same prose as
data (name, severity, scope, endogenous/exogenous, description) — zero new
business logic, and a module-level assertion keeps it in sync with
`engine.py`'s `NOMBRES_REGLAS_ESTATICAS` so it can't silently drift.

### `query_gold_results(rule_id, dataset_id, limit)`

Thin wrapper over the existing `GET /audits/{id}/gold/query`. `dataset_id`
is optional — omitting it fetches the most recently uploaded dataset first
(`GET /uploads/?limit=1`), for questions like "what failed in the last batch"
with no ID given.

### `summarize_dataset(dataset_id, top_n)` — added during Phase 1, not in the original spec

**Why this exists**: testing the spec's own example question — *"which
rules failed most often in dataset X"* — against `query_gold_results` alone
produced a wrong, rambling answer. A 7B local model asked to manually count
and rank raw gold rows (up to thousands of them) is not reliable at
arithmetic-over-a-list; it doesn't fail loudly, it just answers something
plausible-sounding and wrong for one invoice instead of the whole dataset.

The fix was not a bigger prompt — it was noticing that `GET
/audits/{id}/dashboard` (used by the existing web dashboard) **already
computes this exact ranking server-side**, sorted, over the full dataset. So
instead of asking the model to aggregate, `summarize_dataset` wraps that
endpoint and hands the model an already-sorted, already-truncated
(`top_n`, default 5) list. Same zero-new-logic constraint as the other two
tools — this is 100% reuse, just of a different existing endpoint.

Even with pre-aggregated data, the first version (no truncation) still
picked the wrong 3rd entry from an 18-item sorted list — truncating to 5
items server-side fixed it. Lesson kept here on purpose: **tool design for a
small local model means minimizing how much reasoning you ask it to do over
the tool's output, not just how much reasoning you ask it to do overall.**

### `explain_invoice_result(invoice_id, dataset_id)`

Thin wrapper over the existing `GET /audits/{id}/factura/{numero}` (the same
endpoint the invoice detail page uses) — every rule evaluated against one
invoice, header and item scope, from the last time gold ran. One thing that
endpoint does *not* do on its own: it returns `200` with empty lists for an
invoice number that doesn't exist, rather than a `404` — the tool checks
`facturas` is non-empty itself and turns that into `{"error": ...}` before
handing it to the model, so a typo'd invoice number doesn't get treated as
"an invoice with zero data" instead of "not found."

Also adds a pre-computed `resumen` (counts) and a `violaciones` list
(failing evaluations only) on top of the endpoint's raw response — see
"Known model limitations" below for why; this wasn't in the original design,
it's a fix for a real bug found testing this tool against Ollama.

### `run_rule(rule_id, invoice_id, dataset_id)` — added during Phase 2, not in the original spec

**Why this exists**: the spec's example question — *"run rule R-07 against
invoice 4821"* — implies recomputing live, not reading what gold already
says. That's a real gap: nothing in the app runs a single rule against a
single invoice; the closest thing, "Re-run gold," recomputes *all* rules for
*the whole dataset*. This was flagged and discussed before writing any code
(not silently built) — the concern was that recomputing on a filtered
subset might require real new business logic, which the spec says to avoid.

It didn't, in the end: `POST /audits/{id}/factura/{numero}/run-rule` (new
endpoint, `AuditService.run_rule_on_invoice`) reads that one invoice's
already-typed silver rows (`duckdb_query.get_dataframe_by_factura` — new,
see below) and the *current* catalog/dynamic-rule state, then calls
`to_gold()` — the exact same function `run-gold` already calls for a whole
dataset — on that one-invoice subset, and filters the output to the
requested rule. Zero new rule logic; the new code is orchestration glue
(read filtered, call the existing evaluator, filter the result).

**A real bug found building this, not a design decision**: the first
version read the invoice's silver rows as `list[dict]` (the existing
`get_rows_by_factura`) and rebuilt a Polars DataFrame from them by hand.
That silently broke `to_gold()` with a `SchemaError` whenever every row of
*this one invoice* happened to have `codigo_descuento = null` — Polars
infers an all-null column as type `Null` when building a DataFrame from raw
dicts, which then fails to join against the catalog's `Utf8` column. The
fix was `get_dataframe_by_factura`, a duckdb_query.py function that returns
the DuckDB/Delta-backed DataFrame directly instead of round-tripping through
dicts — it keeps Delta's real schema (a nullable Utf8 column stays Utf8
regardless of which values happen to be null in a given subset). Lesson:
"convert to dicts and back" is not a neutral operation for a typed data
pipeline, even when it looks like one.

## Known model limitations (not tool bugs)

Two failure modes showed up live, both about the *last* step — the model
narrating a tool's result — not about the tools or their data:

- **Aggregation over raw rows is unreliable** (Phase 1, see
  `summarize_dataset` above) — fixed by pre-aggregating server-side instead
  of asking the model to count.
- **Summarizing a longer already-correct list was not reliably faithful**
  (Phase 2, found testing `explain_invoice_result`): asked to summarize an
  invoice with ~20 rule evaluations (only 1 actually failing), the model
  correctly *listed* every rule's real status, then wrote a closing summary
  claiming "4 errors" and describing problems ("discount code issues") that
  contradicted its own list two lines above — reproduced twice. Same shape
  as the aggregation bug, so fixed the same way: `explain_invoice_result`
  now returns a pre-computed `resumen` (`total_evaluaciones`,
  `total_fallidas`, `fallidas_error`, `fallidas_warning`) and a `violaciones`
  list containing only the failing evaluations, instead of leaving the model
  to derive those numbers from ~20 raw rows itself. The system prompt
  (`graph.py`) also now explicitly says to use any pre-counted field
  ("resumen", "total_*") as-is rather than recompute it. Retested the exact
  question that reproduced the bug: the model now reports "1 fallida, 0
  advertencias," matching the real data. **Fixed, verified against a real
  rerun, not just assumed from the code change.**
- **Still not fixed**: the model ignores an explicit "answer in one
  sentence" / "only the header rules" instruction and produces the full
  unfiltered breakdown anyway, even in the retest above — an
  instruction-following gap, distinct from the factual-accuracy one that's
  now fixed. No equivalent "pre-compute it" escape hatch applies here since
  the ask is about response *format*, not the numbers in it; worth trying a
  stronger model or a firmer system-prompt instruction before Phase 3, not
  worth guessing at blind.

## The graph

```
START -> agent -> (has tool_calls? -> tools -> agent, loop)
                -> (no tool_calls? -> END)
                -> (tool_calls AND step_count >= MAX_STEPS? -> finalize -> END)
```

- **`agent` node**: calls `ChatOllama` with the three tools bound, increments
  `step_count`.
- **`tools` node**: LangGraph's prebuilt `ToolNode` — executes whatever the
  model asked for, appends `ToolMessage`s to state.
- **`finalize` node**: only reached at the step cap. Calls the model *once
  more, with tools unbound*, explicitly told to stop asking for tools and
  answer in plain text from whatever's already in the message history. This
  exists so hitting the cap produces a partial answer instead of an
  AIMessage whose only content is an unresolved tool call.

**Step cap**: `settings.MAX_STEPS = 8` (env-overridable). Without a hard cap,
a model stuck in "let me check one more thing" has no reason to stop; a
portfolio agent that can hang indefinitely on a bad prompt is a worse demo
than one that visibly gives up gracefully. 8 was picked as "generous enough
for a 2-3 tool-call chain with room to recover from one bad call," not
tuned against real failure data yet.

**Checkpointing**: none, on purpose, for now. Phase 1 is a one-shot CLI
(`python -m agent "question"`) — every invocation starts a fresh
`{"messages": [...], "step_count": 0}`, there's no conversation to resume
between calls. A checkpointer (`langgraph.checkpoint`) would matter once
there's a persistent session — the MCP server in Phase 4 is the more likely
place that becomes necessary, revisit there.

## Tool failure handling

Each tool catches `httpx.HTTPError` and 404s itself, returning `{"error":
"..."}` (or `[{"error": "..."}]` for the list-returning tools) as a normal
successful return value, rather than letting an exception propagate.
LangGraph's `ToolNode` already has its own default exception handling
(`_default_handle_tool_errors`, turns a raised exception into a `ToolMessage`
automatically) — this is a deliberate choice on top of that, not a
workaround for its absence: it keeps every tool's return shape consistent
(always the tool's normal dict/list shape, error or not) instead of two
different shapes depending on whether something raised. The model sees the
error string either way and is instructed (system prompt in `graph.py`) to
say it doesn't know rather than paper over it — verified in
`test_get_rule_reports_error_when_backend_unreachable` and by hand (asking
about a rule name that doesn't exist correctly produces "that rule doesn't
exist," not a hallucinated description).

## Measured token cost

One real run of the example question above (`qwen2.5:7b` via Ollama,
`temperature=0`), 2 steps (1 tool call):

| | input tokens | output tokens |
|---|---|---|
| Step 1 (agent decides to call `summarize_dataset`) | 1,226 | 61 |
| Step 2 (agent reads the tool result, answers) | 1,601 | 178 |
| **Total** | **2,827** | **239** |

**3,066 tokens for one grounded answer.** Most of the input-token cost is
the system prompt + tool schemas being re-sent on every step (LangGraph
resends the full message history each turn, not a diff) — this is the
expected cost of a stateless-per-call tool-calling loop, and the main lever
for reducing it later would be trimming tool docstrings/schemas rather than
the system prompt, since the docstrings are what feeds the model's picture
of what each tool does.

## Setup

```bash
cd apps/agent
python -m venv venv && venv\Scripts\activate   # or source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                          # BACKEND_BASE_URL defaults to localhost:8000

ollama pull qwen2.5:7b                          # confirmed to support real tool-calling, not just prose
ollama serve                                    # if not already running

python -m agent "your question here"
```

Requires the backend running (`apps/backend`, see its own README/`.env`) —
by design, see "Architecture" above.

## Testing

```bash
python -m pytest -v
```

17 tests: unit tests for all five tools (backend mocked at the `httpx`
boundary, same standard as `packages/domain`'s 99 tests), plus two graph
integration tests with the LLM itself scripted — asserting on the tool-call
sequence and message shape (`test_graph_calls_tool_then_answers`), and on
the step cap producing a partial answer instead of hanging
(`test_graph_stops_at_step_cap_with_a_partial_answer`) — never on a real
model's exact wording, which isn't deterministic.
