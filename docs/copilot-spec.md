# AuditLake Copilot — build spec

Drop this in the repo as `docs/copilot-spec.md`. Point Claude Code at it one phase at a time — do not ask it to build all four phases in one go.

---

## Context

AuditLake is an existing retail invoice audit platform:

- **Frontend:** React + TypeScript
- **Backend:** FastAPI
- **Pipeline:** Excel upload → S3 → Delta (bronze/silver/gold) → rule results in the gold table
- **Domain layer:** pure, no I/O, ~97 tests
- **Rules:** 18 built-in and user-defined, each producing an explainable audit trail per invoice

We are adding a conversational agent layer on top. The agent does **not** reimplement any audit logic. It calls the existing domain layer through a thin tool wrapper.

## Goal

A user can ask, in plain language:

- "What failed in the last batch?"
- "Why did invoice 4821 fail?"
- "What does the rate-cap rule actually check?"
- "Run rule R-07 against invoice 4821."

…and get answers grounded in real pipeline output, never in the model's imagination.

## Hard constraints

1. **The agent never computes an audit result itself.** Every factual claim about an invoice must come from a tool call that hits the domain layer or the gold table. If the agent can't back a claim with a tool result, it says it doesn't know.
2. **No new business logic.** Tools are thin wrappers over existing domain functions. If a tool needs logic that doesn't exist yet, stop and flag it rather than inventing it.
3. **The domain layer stays pure.** No agent imports inside `domain/`. Dependencies point one way: `agent/` → `domain/`.
4. **Bounded iterations.** The graph must enforce a max step count (start at 8) and return a partial answer rather than looping.
5. **Tools fail loudly and recoverably.** A tool raising an exception returns a structured error to the model so it can retry with different arguments; it does not crash the run.

---

## Architecture

```
agent/
  graph.py        LangGraph state graph — nodes, edges, entry point
  state.py        Typed state object (messages, step count, tool results)
  tools.py        Tool definitions, thin wrappers over domain/
  rag/
    index.py      Build the vector index over rule documentation
    retrieve.py   Search interface, exposed as a tool
  mcp_server.py   MCP server exposing the same tools (phase 4)
```

The graph is: `agent node` → conditional edge → `tool node` → back to `agent node`, until the agent produces a final answer or hits the step cap.

---

## Phase 1 — minimum viable agent

**Build:**

- `state.py`: typed state with the message list, a step counter, and room for tool output.
- Two tools in `tools.py`:
  - `get_rule(rule_id: str) -> dict` — full rule definition from the domain layer.
  - `query_gold_results(rule_id: str | None, dataset_id: str | None, limit: int) -> list[dict]` — read from the gold table.
- `graph.py`: agent node + tool node + conditional edge + step cap.
- A CLI entry point: `python -m agent "your question here"`.

**Every tool needs a real docstring.** The model reads it to decide whether to call the tool — it is functional code, not documentation. State what the tool returns, what the arguments mean, and when *not* to use it.

**Done when:** asking "which rules failed most often in dataset X" produces a correct answer, and the trace shows the tool call that produced it.

## Phase 2 — the explanation path

**Build:**

- `run_rule(rule_id: str, invoice_id: str) -> dict` — executes a rule against one invoice via the domain layer, returns the result plus the audit trail.
- `explain_invoice_result(invoice_id: str) -> dict` — returns which rules ran, which failed, and the trail for each.

**Done when:** "why did invoice 4821 fail?" produces an answer naming the specific rule, the offending value, and the threshold — all sourced from the trail, not paraphrased by the model.

## Phase 3 — RAG over rule documentation

**Build:**

- `rag/index.py`: chunk and embed the rule definitions and any prose docs; store in Qdrant (local via Docker is fine).
- `search_rule_docs(query: str, k: int) -> list[dict]` — returns chunks with their source rule id.
- Wire it into the graph as another tool.

Record the chunking strategy and why you chose it. Rule definitions are short and self-contained, so chunk-per-rule likely beats fixed-size windows — but say so explicitly in the README.

**Done when:** "what does the rate-cap rule check?" returns an answer citing the rule id it retrieved.

## Phase 4 — MCP server

**Build:**

- `mcp_server.py` exposing the same tool set over MCP.
- Setup instructions in the README for connecting a local MCP client.

The tool functions must be shared with the LangGraph agent, not duplicated. One definition, two consumers.

**Done when:** an MCP client can list the tools and successfully call `explain_invoice_result`.

---

## Non-goals

- Agent-driven file upload. Files go through the existing UI; the agent works with `dataset_id` references only.
- Multi-agent orchestration. One agent, one tool set.
- Fine-tuning or training anything.
- Rewriting the frontend. A minimal chat panel is optional and comes last.

---

## README additions (write these, they are the deliverable)

Interviewers read the README, not the code. Cover:

- Why a state graph rather than a hand-rolled loop.
- How state moves between nodes, and what is checkpointed.
- What happens when a tool raises — the retry path.
- The step cap and why it exists.
- **Measured token cost of a typical question.** Instrument it and put a real number in. Almost nobody does this, and "optimise token consumption" appears verbatim in real job postings.
- One worked example: the question, the sequence of tool calls, the final answer.

## Testing

- Tool wrappers get unit tests with the domain layer mocked — same standard as the existing 97 tests.
- At least one integration test that runs the graph end to end against a fixture dataset and asserts on the tool-call sequence, not on the model's exact wording.