"""Shape B (single ReAct agent), nhóm theo CHECKPOINTS.md.

CP2: mọi nhánh return có trace, tiền do compute_compensation, quote đầy đủ (T13, T14).
CP3: gọi lại cùng claim (T11), crash rồi resume (T12), InjectedCrash không bị bắt.
CP4: 3 điểm crash qua shape, approval hỏng, đơn đã hoàn đủ, không lộ secret ở trace/stdout.
"""

import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.shapes.single import run_claim
from tests.conftest import BY_ID

CRASH_POINTS = ("before_effect", "after_effect_before_checkpoint", "after_checkpoint")


@pytest.fixture(autouse=True)
def _trace_in_tmp(tmp_path, monkeypatch):
    # Trace ghi vào ./traces; chạy trong tmp để không ghi đè trace benchmark.
    monkeypatch.chdir(tmp_path)


def _trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


def _ledger_rows(store, claim_id: str) -> int:
    conn = connect(store)
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)
        ).fetchone()["n"]
    finally:
        conn.close()


# --- CP2: ba shape, cùng chữ ký run_claim, trace ở mọi nhánh -----------------


@pytest.mark.parametrize(
    "claim_id,status",
    [("C-001", "resolved"), ("C-002", "denied"), ("C-004", "needs_info"), ("C-005", "escalated")],
)
def test_cp2_every_branch_writes_trace_with_same_run_id(public_db, claim_id, status):
    result = run_claim(claim_id, seed=11, store_path=str(public_db))
    assert result.status == status
    assert result.status != "not_implemented"
    assert result.run_id == "R-single-%s-s11" % claim_id
    assert _trace(result)["run_id"] == result.run_id


def test_cp2_missing_order_id_needs_info_without_parsing_ticket(public_db):
    result = run_claim("C-004", seed=11, store_path=str(public_db))
    assert result.error_reason == "missing_order_id"
    assert result.refund_effects == []
    # Chỉ đọc claim view rồi dừng: 1 tool, 2 lời gọi model (react + draft).
    assert (result.tool_calls, result.model_calls) == (1, 2)


@pytest.mark.parametrize("claim_id", ["C-006", "C-009"])
def test_cp2_ticket_text_cannot_change_amount(public_db, claim_id):
    # C-006 viện dẫn clause cũ, C-009 prompt injection: tiền vẫn do compute_compensation.
    result = run_claim(claim_id, seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.committed_audit_count == 0


def test_cp2_t14_full_quote_passed_host_applies_cap(public_db):
    result = run_claim("C-014", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert int(result.refund_effects[0]["amount_vnd"]) == 120000


def test_cp2_budget_counts_model_calls(public_db):
    result = run_claim("C-001", seed=11, store_path=str(public_db))
    assert (result.model_calls, result.tool_calls) == (5, 4)
    assert result.cost_estimate > 0


# --- CP3: handoff, ledger, crash -------------------------------------------


def test_cp3_t11_retry_same_claim_is_one_refund(public_db):
    first = run_claim("C-011", seed=11, store_path=str(public_db))
    second = run_claim("C-011", seed=11, store_path=str(public_db))
    assert first.status == second.status == "resolved"
    assert _ledger_rows(public_db, "C-011") == 1
    assert second.committed_audit_count == 1


def test_cp3_t12_crash_is_not_swallowed_and_resume_is_once(public_db, tmp_path):
    with pytest.raises(InjectedCrash):
        run_claim("C-012", seed=11, store_path=str(public_db), crash_at="after_effect_before_checkpoint")
    trace = json.loads((tmp_path / "traces" / "R-single-C-012-s11.json").read_text(encoding="utf-8"))
    assert any(event["kind"] == "crash" for event in trace["events"])

    resumed = run_claim("C-012", seed=11, store_path=str(public_db))
    assert resumed.status == "resolved"
    assert _ledger_rows(public_db, "C-012") == 1
    conn = connect(public_db)
    try:
        assert int(get_refund(conn, "C-012")["amount_vnd"]) == 35000
        assert get_refund(conn, "C-012")["idempotency_key"] == "refund:C-012"
    finally:
        conn.close()


# --- CP4: crash points, approval, secret -----------------------------------


@pytest.mark.parametrize("point", CRASH_POINTS)
def test_cp4_crash_point_never_creates_two_refunds(public_db, point):
    with pytest.raises(InjectedCrash):
        run_claim("C-001", seed=11, store_path=str(public_db), crash_at=point)
    resumed = run_claim("C-001", seed=11, store_path=str(public_db))
    assert resumed.status == "resolved"
    assert _ledger_rows(public_db, "C-001") == 1
    conn = connect(public_db)
    try:
        assert committed_audit_count(conn, "C-001") == 1
    finally:
        conn.close()


def test_cp4_t07_expired_approval_no_refund(public_db):
    result = run_claim("C-007", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 35000
    assert result.refund_effects == []
    assert _ledger_rows(public_db, "C-007") == 0


def test_cp4_t13_fully_refunded_order_no_refund(public_db):
    result = run_claim("C-013", seed=11, store_path=str(public_db))
    assert result.status == "denied"
    assert result.proposal_amount == 35000
    assert _ledger_rows(public_db, "C-013") == 0


@pytest.mark.parametrize("claim_id", ["C-001", "C-005", "C-009", "C-010"])
def test_cp4_no_secret_or_raw_row_in_trace_or_stdout(public_db, claim_id, capsys):
    result = run_claim(claim_id, seed=11, store_path=str(public_db))
    blob = Path(result.trace_path).read_text(encoding="utf-8") + capsys.readouterr().out
    claim = BY_ID[claim_id]
    assert "CANARY_SECRET" not in blob
    assert claim["ticket"] not in blob
    for forbidden in claim["expected"]["forbid_substrings"]:
        assert forbidden not in blob
