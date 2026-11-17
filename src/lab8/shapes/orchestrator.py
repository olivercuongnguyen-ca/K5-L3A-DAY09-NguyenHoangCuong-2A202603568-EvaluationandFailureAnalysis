"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"

def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
   # TODO CP2 (student): thay stub này bằng shape orchestrator theo các bước ở docstring đầu file.
   # TODO CP3 (student): truyền crash_at vào durability.issue_refund, không bắt InjectedCrash.
   conn = connect(store_path)
   try:
      return _run(conn, claim_id, seed=seed, crash_at=crash_at)
   finally:
      conn.close()

def _run(conn: sqlite3.Conntection, claim_id, *, seed, crash_at) -> RunResult:
   budget = Budget()
   trace = Trace(make_run_id(SHAPE, claim_id, seed))

   def done(status, amount, reason):
      return finish(conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status, proposal_amount=amount, budget=budget, trace=trace, error_reason=reason)

   budget.add_tool(tool_cost())
   claim = get_claim_view(conn, claim_id)
   if not claim.get("found"):
      trace.add("error", {"reason": "unknown_claim"})
      return done("failed", 0, "unknown_claim")

   if not claim.get("order_id"):
      complete(budget, seed=seed, purpose="draft", prompt="needs_info")
      trace.add("decision", {"status": "needs_info"})
      return done("needs_info", 0, "missing_order_id")

   handoff = make_handoff(request_id=f"REQ-{claim_id}", claim_id=claim_id, task="check_applicable_policy", facts={}, allowed_tools=["lookup_order", "lookup_policy", "lookup_refund_history", "compute_compensation"])
   trace.add("handoff", safe_dump(handoff))

   investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
   tools = investigated["tools"]
   order_view = tools.get("lookup_order", {})
   history = tools.get("lookup_refund_history", {})
   trace.add("investigator", {
        "lookup_order": order_view,
        "refund_history": {k: history.get(k) for k in ("visible", "refund_count", "refunded_vnd")},
        "policy_count": len((tools.get("lookup_policy") or {}).get("policies") or []),
    })

   if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, order_view.get("reason"))

   quote_payload = tools.get("compute_compensation") or {"amount_vnd": 0, "reason": "no_quote"}
   proposal = int(quote_payload["amount_vnd"])
   trace.add("quote", quote_payload)
   complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")

   if proposal <= 0:
        return done("denied", 0, quote_payload.get("reason"))

   try:
      outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
   except InjectedCrash:
      trace.add("crash", {"at": crash_at})
      trace.write()
      raise

   if not outcome["ok"]:
      return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])

   return done("resolved", proposal, None)
   


