"""Bonus B3 — swarm plus a code verifier before the write.

Same flow as lab8.shapes.swarm_reference (the swarm weakness is kept on purpose, so the
verifier has something to catch). The only addition is `_verify`: before quoting money, it
re-reads the order from the structured store and compares every fact used for the quote
(`status`, `delay_days`, `damage_verified`, fee, paid). On a mismatch it re-quotes from the
structured order, at most one repair round, and writes a `verifier_override` trace event.
Writes still go through `durability.issue_refund` with the full quote.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete, parse_delay_days
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "swarm_verified"
QUOTE_FACTS = ("status", "delay_days", "damage_verified", "shipping_fee_vnd", "paid_vnd")


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _verify(conn, budget, trace, claim_row, working_order, quote_payload):
    """Compare the facts behind the quote with the structured order. One repair round."""
    budget.add_tool(tool_cost())
    fresh_view = lookup_order(conn, claim_row["order_id"], claim_row["principal_id"])
    if not fresh_view.get("visible"):
        return None, quote_payload  # ownership is decided by the host path, not here
    fresh = fresh_view["order"]
    diff = [k for k in QUOTE_FACTS if working_order.get(k) != fresh.get(k)]
    if not diff:
        return working_order, quote_payload
    budget.add_tool(tool_cost())
    repaired_quote = compute_compensation(conn, fresh)
    trace.add(
        "verifier_override",
        {
            "fields": diff,
            "used": {k: working_order.get(k) for k in diff},
            "structured": {k: fresh.get(k) for k in diff},
            "quote_before": int(quote_payload["amount_vnd"]),
            "quote_after": int(repaired_quote["amount_vnd"]),
        },
    )
    return dict(fresh), repaired_quote


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, amount: int, reason: str | None) -> RunResult:
        return finish(
            conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status,
            proposal_amount=amount, budget=budget, trace=trace, error_reason=reason,
        )

    budget.add_tool(tool_cost())
    claim_row = conn.execute(
        "SELECT claim_id, principal_id, order_id, ticket FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if claim_row is None:
        trace.add("error", {"reason": "unknown_claim"})
        return done("failed", 0, "unknown_claim")

    ticket = claim_row["ticket"]
    complete(budget, seed=seed, purpose="peer", prompt=ticket)
    parsed_delay = parse_delay_days(ticket)
    complete(budget, seed=seed, purpose="parse", prompt=ticket)

    if not claim_row["order_id"]:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        trace.add("decision", {"status": "needs_info"})
        return done("needs_info", 0, "missing_order_id")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_applicable_policy",
        facts={},
        allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"],
    )
    trace.add("handoff", safe_dump(handoff))
    investigated = run_readonly_investigators(
        conn, budget, handoff, principal_id=claim_row["principal_id"]
    )
    order_view = investigated["tools"].get("lookup_order", {})
    trace.add("investigator", {"lookup_order": order_view})
    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, order_view.get("reason"))

    order = dict(order_view["order"])
    quote_payload = investigated["tools"]["compute_compensation"]
    # Swarm weakness kept on purpose: one seed in five trusts the ticket delay over the DB.
    if parsed_delay is not None and parsed_delay != int(order["delay_days"]) and seed % 5 == 0:
        order["delay_days"] = parsed_delay
        trace.add("model_override", {"delay_days": parsed_delay})
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, order)

    # The addition: verify the facts behind the quote against structured data.
    order, quote_payload = _verify(conn, budget, trace, claim_row, order, quote_payload)
    if order is None:
        return done("escalated", 0, "verifier_order_not_visible")

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
