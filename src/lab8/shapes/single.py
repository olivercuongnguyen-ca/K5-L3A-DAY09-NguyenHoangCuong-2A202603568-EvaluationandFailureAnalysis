"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn,claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    run_id = make_run_id("single", claim_id, seed)
    trace = Trace(run_id)

    state: dict[str, Any] = {
        "claim_view": None,
        "order_view": None,
        "refund_history": None,
        "quote_payload": None,
    }

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        last_tool = seen.get("last_tool")
        last_result = seen.get("last_result")

        if last_tool == "get_claim_view":
            state["claim_view"] = last_result
            trace.add(
                "tool",
                {
                    "tool": last_tool,
                    "found": bool(last_result.get("found")),
                    "has_order_id": bool(last_result.get("order_id")),
                },
            )
        elif last_tool == "lookup_order":
            state["order_view"] = last_result
            trace.add("tool", {"tool": last_tool, "result": safe_dump(last_result)})
        elif last_tool == "lookup_refund_history":
            state["refund_history"] = last_result
            trace.add("tool", {"tool": last_tool, "result": safe_dump(last_result)})
        elif last_tool == "compute_compensation":
            state["quote_payload"] = last_result
            trace.add("tool", {"tool": last_tool, "result": safe_dump(last_result)})

        claim_view = state["claim_view"]
        if claim_view is None:
            complete(budget, seed=seed, purpose="react", prompt=f"claim={claim_id}")
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}

        if not claim_view.get("found"):
            return {
                "final": {
                    "status": "failed",
                    "proposal_amount": 0,
                    "error_reason": "unknown_claim",
                }
            }

        order_id = claim_view.get("order_id")
        if not order_id:
            complete(budget, seed=seed, purpose="draft", prompt="needs_info")
            return {
                "final": {
                    "status": "needs_info",
                    "proposal_amount": 0,
                    "error_reason": "missing_order_id",
                }
            }

        principal_id = claim_view["principal_id"]
        order_view = state["order_view"]
        if order_view is None:
            complete(budget, seed=seed, purpose="react", prompt=f"lookup_order:{order_id}")
            return {
                "tool": "lookup_order",
                "args": {"order_id": order_id, "principal_id": principal_id},
            }

        if not order_view.get("visible"):
            complete(budget, seed=seed, purpose="draft", prompt="escalated")
            return {
                "final": {
                    "status": "escalated",
                    "proposal_amount": 0,
                    "error_reason": order_view.get("reason"),
                }
            }

        if state["refund_history"] is None:
            complete(budget, seed=seed, purpose="react", prompt=f"history:{order_id}")
            return {
                "tool": "lookup_refund_history",
                "args": {"order_id": order_id, "principal_id": principal_id},
            }

        quote_payload = state["quote_payload"]
        if quote_payload is None:
            complete(budget, seed=seed, purpose="react", prompt=f"quote:{order_id}")
            return {
                "tool": "compute_compensation",
                "args": {"order": order_view["order"]},
            }

        proposal = int(quote_payload["amount_vnd"])
        complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
        return {
            "final": {
                "status": "quoted",
                "proposal_amount": proposal,
                "error_reason": quote_payload.get("reason"),
            }
        }

    loop_result = run_react(
        conn,
        budget,
        observation={"claim_id": claim_id},
        decide=decide,
        max_steps=8,
        worker=False,
    )

    if loop_result["stopped"] == "step_cap":
        trace.add("decision", {"status": "failed", "reason": "step_cap"})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="step_cap",
        )

    final = loop_result["final"]
    if final["status"] in ("failed", "needs_info", "escalated"):
        trace.add("decision", {"status": final["status"], "reason": final.get("error_reason")})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=final["status"],
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason"),
        )

    proposal = int(final["proposal_amount"])
    trace.add("quote", {"proposal_amount": proposal, "reason": final.get("error_reason")})
    if proposal <= 0:
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason"),
        )

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    return finish(
        conn,
        shape="single",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )
