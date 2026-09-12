"""Tools - wrappers delgados sobre el backend ya desplegado, nunca
reimplementan lógica de auditoría (ver docs/copilot-spec.md, restricción
#2). El agente le pega al backend por HTTP en vez de importar
infrastructure/ directo, así no duplica credenciales de Postgres/R2 ni
su configuración (decisión tomada explícitamente antes de escribir esto).

Cada docstring es código funcional, no documentación - el modelo la lee
para decidir cuándo y cómo llamar la tool."""

import httpx
from langchain_core.tools import tool

from agent.settings import settings


@tool
def get_rule(rule_id: str) -> dict:
    """Return the full definition of a rule (built-in or user-defined) by its name.

    Args:
        rule_id: the rule's name, e.g. "sede_existe" (built-in) or
            "descuento_maximo_ropa" (user-defined). Always a name,
            never a numeric database id.

    Returns a dict with the rule's metadata. For a built-in rule:
    name, severity, scope (header/item), whether it's endogenous
    (checks the record against itself) or exogenous (cross-references
    a master catalog), and what it checks. For a user-defined rule:
    name, severity, scope, and its actual threshold or exclusion-window
    condition.

    Use this when the user asks what a specific rule checks or wants
    its exact condition. There is no bulk-list tool yet - to compare
    several rules, call this once per name.

    Returns {"error": "..."} if no rule with that name exists (checked
    against both built-in and user-defined rules) or if the backend
    can't be reached - never guess a rule's definition in that case.
    """
    try:
        resp = httpx.get(f"{settings.BACKEND_BASE_URL}/rules/", timeout=10)
        resp.raise_for_status()
        for regla in resp.json():
            if regla["nombre"] == rule_id:
                return regla
    except httpx.HTTPError as e:
        return {"error": f"couldn't reach the backend to check user-defined rules: {e}"}

    try:
        resp = httpx.get(f"{settings.BACKEND_BASE_URL}/rules/static/{rule_id}", timeout=10)
        if resp.status_code == 404:
            return {"error": f"no rule named '{rule_id}' exists (checked both built-in and user-defined rules)"}
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        return {"error": f"couldn't reach the backend to check built-in rules: {e}"}


@tool
def query_gold_results(
    rule_id: str | None = None,
    dataset_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Query real rule-evaluation rows from a processed dataset's gold table.

    Args:
        rule_id: filter to one rule's results by name (built-in or
            user-defined), e.g. "factura_total_cuadra". Omit to get
            results across all rules.
        dataset_id: the upload/job id to query. Omit to use the most
            recently uploaded dataset - use this for questions like
            "what failed in the last batch".
        limit: max rows to return (default 20). Each row is one rule
            evaluated against one invoice or line item, not one
            invoice - an invoice with several violations produces
            several rows.

    Returns a list of gold rows, each shaped like: numero_factura,
    item_id (null for header-scope rules), sede_codigo, fecha, regla,
    severidad, paso (bool), mensaje. `paso: false` rows are the actual
    violations; `mensaje` explains why in the rule's own words.

    Use this instead of get_rule when the user asks about actual
    invoices or violations rather than a rule's definition.

    Returns a single-item list [{"error": "..."}] if no dataset has
    been uploaded yet, if the dataset's pipeline hasn't finished
    running (no gold table yet), or if the backend can't be reached -
    never invent invoice data in that case.
    """
    if dataset_id is None:
        try:
            resp = httpx.get(f"{settings.BACKEND_BASE_URL}/uploads/?limit=1", timeout=10)
            resp.raise_for_status()
            uploads = resp.json()["uploads"]
        except httpx.HTTPError as e:
            return [{"error": f"couldn't reach the backend to find the latest dataset: {e}"}]
        if not uploads:
            return [{"error": "no datasets have been uploaded yet"}]
        dataset_id = uploads[0]["upload_id"]

    params: dict[str, str | int] = {"limit": limit, "offset": 0}
    if rule_id:
        params["regla"] = rule_id

    try:
        resp = httpx.get(f"{settings.BACKEND_BASE_URL}/audits/{dataset_id}/gold/query", params=params, timeout=10)
        if resp.status_code == 404:
            return [{"error": f"dataset '{dataset_id}' has no gold results yet - has the pipeline finished running?"}]
        resp.raise_for_status()
        return resp.json()["rows"]
    except httpx.HTTPError as e:
        return [{"error": f"couldn't reach the backend: {e}"}]


@tool
def summarize_dataset(dataset_id: str | None = None, top_n: int = 5) -> dict:
    """Get aggregate stats for a processed dataset, including a ranked
    list of which rules failed most often.

    Args:
        dataset_id: the upload/job id to summarize. Omit to use the
            most recently uploaded dataset.
        top_n: how many rules to include in the ranking (default 5).
            The full dataset may have well over a dozen rules with
            violations - keep this small (5-10) unless the user asked
            for a longer list, it's easier to read off correctly than
            a long one.

    Returns totals (invoice count, how many are fully valid vs. have at
    least one error, registered vs. validated monetary value) plus
    `reglas`: the top `top_n` rules as {regla, severidad,
    facturas_afectadas}, already sorted by facturas_afectadas
    descending - `reglas[0]` is the single most-violated rule, read the
    list top to bottom, do not re-sort or recount it yourself.

    Use this for any question about which rules fail most/least, or for
    an overall health summary of a batch - it's already aggregated
    server-side. Do not use query_gold_results and try to count rows
    yourself for this kind of question; counting rows by hand from a
    small sample is unreliable, this tool does the real count over the
    full dataset.

    Returns {"error": "..."} if no dataset has been uploaded yet, if its
    pipeline hasn't finished running, or if the backend can't be
    reached.
    """
    if dataset_id is None:
        try:
            resp = httpx.get(f"{settings.BACKEND_BASE_URL}/uploads/?limit=1", timeout=10)
            resp.raise_for_status()
            uploads = resp.json()["uploads"]
        except httpx.HTTPError as e:
            return {"error": f"couldn't reach the backend to find the latest dataset: {e}"}
        if not uploads:
            return {"error": "no datasets have been uploaded yet"}
        dataset_id = uploads[0]["upload_id"]

    try:
        resp = httpx.get(f"{settings.BACKEND_BASE_URL}/audits/{dataset_id}/dashboard", timeout=10)
        if resp.status_code == 404:
            return {"error": f"dataset '{dataset_id}' has no gold results yet - has the pipeline finished running?"}
        resp.raise_for_status()
        data = resp.json()
        data["reglas"] = data["reglas"][:top_n]
        return data
    except httpx.HTTPError as e:
        return {"error": f"couldn't reach the backend: {e}"}


TOOLS = [get_rule, query_gold_results, summarize_dataset]
