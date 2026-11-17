"""Behaviour tests for shape C (orchestrator).

These check design decisions that are specific to the orchestrator, not the generic
T01-T14 matrix: the ticket never changes the money, the handoff is read-only and clean,
the full quote reaches the host, and nothing sensitive reaches the trace.
Not marked `student`, so they run in the host gate (`python -m pytest -q`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.handoff import READONLY_TOOLS, WRITE_TOOLS
from lab8.shapes import orchestrator
from tests.conftest import BY_ID

SECRET_MARKERS = ("CANARY_SECRET_", "CANARY_INTERNAL_", "parent_secret", "raw_headers", "Bearer ")


def _run(public_db: Path, claim_id: str, seed: int = 11):
    return orchestrator.run_claim(claim_id, seed=seed, store_path=str(public_db))


def _ledger_rows(public_db: Path, claim_id: str) -> int:
    conn = connect(public_db)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM refund_ledger WHERE claim_id = ?", (claim_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_ticket_delay_never_changes_the_money(public_db, seed):
    # C-002: the ticket says "tre 5 ngay" but the order row says 2 days.
    # The swarm trusts the ticket on seed 55. The orchestrator must deny on every seed.
    assert "5 ngày" in BY_ID["C-002"]["ticket"]
    result = _run(public_db, "C-002", seed)
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert _ledger_rows(public_db, "C-002") == 0


def test_handoff_is_read_only_and_trace_has_no_secret(public_db):
    result = _run(public_db, "C-001")
    body = _trace(result)
    assert body["run_id"] == result.run_id
    handoffs = [e["payload"] for e in body["events"] if e["kind"] == "handoff"]
    assert len(handoffs) == 1
    tools = set(handoffs[0]["allowed_tools"])
    assert tools and tools <= READONLY_TOOLS
    assert not tools & WRITE_TOOLS
    assert handoffs[0]["facts"] == {}  # investigators find the facts themselves
    blob = Path(result.trace_path).read_text(encoding="utf-8")
    for marker in SECRET_MARKERS:
        assert marker not in blob
    assert BY_ID["C-001"]["ticket"] not in blob  # ticket text is never traced


def test_full_quote_is_passed_so_host_pays_only_the_difference(public_db):
    # C-014 (T14): 30,000 already refunded, damage entitlement 150,000.
    # proposal_amount stays the FULL quote; the host writes the 120,000 difference.
    result = _run(public_db, "C-014")
    assert result.status == "resolved"
    assert result.proposal_amount == 150_000
    assert [e["amount_vnd"] for e in result.refund_effects] == [120_000]
    assert result.committed_audit_count == 1


def test_zero_quote_does_not_call_the_host(public_db):
    # C-009 (order O-404, 1 day late): quote is 0, so issue_refund must not be called.
    # If it were, the host would leave a policy_denied audit or a ledger row behind.
    result = _run(public_db, "C-009")
    assert result.status == "denied"
    assert result.proposal_amount == 0
    conn = connect(public_db)
    try:
        audits = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE claim_id = ?", ("C-009",)
        ).fetchone()[0]
    finally:
        conn.close()
    assert audits == 0
    assert _ledger_rows(public_db, "C-009") == 0


def test_host_rejection_keeps_full_quote_and_audit(public_db):
    # C-007: approval expired. Quote > 0, so the host must be asked and must say no.
    result = _run(public_db, "C-007")
    assert result.status == "denied"
    assert result.proposal_amount == 35_000
    assert result.refund_effects == []
    conn = connect(public_db)
    try:
        denied = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
            ("C-007",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert denied >= 1
