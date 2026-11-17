"""Shape B (single ReAct agent): guardrail của host khi DB bị sửa hoặc agent đi lệch.

Bổ sung cho test_2A202603535_single_shape.py, các ca không có sẵn trong ma trận public:
approval của claim khác, thiếu approval, ledger lệch tiền, claim không tồn tại, chạm step cap.
"""

import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.shapes import single
from lab8.shapes.single import run_claim


@pytest.fixture(autouse=True)
def _trace_in_tmp(tmp_path, monkeypatch):
    # Trace ghi vào ./traces; chạy trong tmp để không ghi đè trace benchmark.
    monkeypatch.chdir(tmp_path)


def _sql(store, query: str, params: tuple = ()) -> list:
    conn = connect(store)
    try:
        rows = conn.execute(query, params).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


def _ledger_rows(store, claim_id: str) -> int:
    return _sql(store, "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,))[0]["n"]


def _trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


def test_single_approval_of_other_claim_is_blocked(public_db):
    # C-001 trỏ sang A-010 (approval hợp lệ nhưng cấp cho C-010): không được hoàn tiền.
    assert _sql(public_db, "SELECT claim_id FROM approvals WHERE approval_id = 'A-010'")[0]["claim_id"] == "C-010"
    _sql(public_db, "UPDATE claims SET approval_id = 'A-010' WHERE claim_id = 'C-001'")

    result = run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "denied"
    assert result.error_reason == "approval_claim_mismatch"
    assert result.refund_effects == []
    assert _ledger_rows(public_db, "C-001") == 0
    # A-010 vẫn dùng được cho đúng claim của nó.
    assert run_claim("C-010", seed=11, store_path=str(public_db)).status == "resolved"


def test_single_missing_approval_no_refund(public_db):
    _sql(public_db, "UPDATE claims SET approval_id = NULL WHERE claim_id = 'C-001'")

    result = run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "denied"
    assert result.error_reason == "missing_approval"
    assert result.proposal_amount == 35000
    assert _ledger_rows(public_db, "C-001") == 0


def test_single_ledger_amount_conflict_does_not_write_second_refund(public_db):
    # Ledger đã có refund:C-001 với số tiền khác: host báo conflict, không ghi đè, không tạo dòng mới.
    _sql(
        public_db,
        "INSERT INTO refund_ledger (claim_id, order_id, idempotency_key, amount_vnd, status) "
        "VALUES ('C-001', 'O-107', 'refund:C-001', 1000, 'committed')",
    )

    result = run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "failed"
    assert result.error_reason == "amount_conflict"
    rows = _sql(public_db, "SELECT amount_vnd FROM refund_ledger WHERE claim_id = 'C-001'")
    assert [int(r["amount_vnd"]) for r in rows] == [1000]


def test_single_unknown_claim_fails_with_trace(public_db):
    result = run_claim("C-999", seed=11, store_path=str(public_db))

    assert result.status == "failed"
    assert result.error_reason == "unknown_claim"
    assert result.refund_effects == []
    assert _trace(result)["run_id"] == "R-single-C-999-s11"


def test_single_step_cap_fails_closed(public_db, monkeypatch):
    # Agent không kết thúc trong 8 bước: phải trả failed có trace, không gọi issue_refund.
    def _never_finishes(*args, **kwargs):
        return {"stopped": "step_cap", "final": {"status": "failed", "error_reason": "step_cap"}}

    def _must_not_refund(*args, **kwargs):
        raise AssertionError("issue_refund không được gọi khi chạm step cap")

    monkeypatch.setattr(single, "run_react", _never_finishes)
    monkeypatch.setattr(single, "issue_refund", _must_not_refund)

    result = run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "failed"
    assert result.error_reason == "step_cap"
    assert _ledger_rows(public_db, "C-001") == 0
    events = _trace(result)["events"]
    assert {"kind": "decision", "payload": {"status": "failed", "reason": "step_cap"}} in events
