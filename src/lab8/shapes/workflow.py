
"""Shape A — deterministic workflow."""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace
from lab8.tools import (
    compute_compensation,
    get_claim_view,
    lookup_order,
    tool_cost,
)


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(
            conn,
            claim_id,
            seed=seed,
            crash_at=crash_at,
        )
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    shape = "workflow"
    budget = Budget()

    run_id = make_run_id(shape, claim_id, seed)
    trace = Trace(run_id)

    # Step 1: Read the claim through the approved tool.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)

    if not claim.get("found"):
        trace.add("error", {"reason": "unknown_claim"})
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    # Do not put the raw ticket into the trace.
    trace.add(
        "claim_read",
        {
            "found": True,
            "claim_id": claim_id,
            "has_order_id": bool(claim.get("order_id")),
        },
    )

    # Step 2: Missing order ID.
    if not claim.get("order_id"):
        trace.add("decision", {"status": "needs_info"})
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status="needs_info",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="missing_order_id",
        )

    # Step 3: Look up the order within the claim owner's scope.
    budget.add_tool(tool_cost())
    order_result = lookup_order(
        conn,
        claim["order_id"],
        claim["principal_id"],
    )

    trace.add(
        "order_lookup",
        {
            "visible": order_result.get("visible", False),
            "reason": order_result.get("reason"),
        },
    )

    if not order_result.get("visible"):
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status="escalated",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=order_result.get("reason"),
        )

    # Step 4: Calculate compensation from structured order data.
    # Never use delay numbers from the ticket.
    order = order_result["order"]

    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    proposal = int(quote["amount_vnd"])

    trace.add("quote", safe_dump(quote))

    # Step 5: No compensation is due.
    if proposal <= 0:
        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=quote.get("reason"),
        )

    # Step 6: Ask the host to authorize and commit the refund.
    # Pass the FULL quote. The host handles approval and order-level caps.
    budget.add_tool(tool_cost())

    outcome = issue_refund(
        conn,
        claim_id,
        proposal,
        crash_at=crash_at,
    )

    trace.add(
        "refund_result",
        {
            "ok": outcome["ok"],
            "reason": outcome["reason"],
            "conflict": outcome["conflict"],
        },
    )

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"

        return finish(
            conn,
            shape=shape,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    # Step 7: Refund committed successfully.
    return finish(
        conn,
        shape=shape,
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )
