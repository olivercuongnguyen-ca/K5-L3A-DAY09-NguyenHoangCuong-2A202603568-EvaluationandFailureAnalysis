"""Bonus B3 tests: the code verifier in bonus.swarm_verified.

Seed 55 is the seed where the reference swarm trusts the ticket delay over the order row.
Not marked `student`; runs in the host gate (`python -m pytest -q`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bonus import swarm_verified
from lab8.config_loader import repo_path
from lab8.db import connect, init_store, load_json, load_jsonl
from lab8.shapes import swarm_reference

WORLD = load_json(repo_path("bonus", "world.json"))
CASES = load_jsonl(repo_path("bonus", "cases.jsonl"))
BY_ID = {row["claim_id"]: row for row in CASES}
BAD_SEED = 55  # seed % 5 == 0: swarm weakness fires
SECRETS = ("CANARY_SECRET_", "CANARY_INTERNAL_", "parent_secret", "raw_headers", "Bearer ")


@pytest.fixture
def bonus_db(tmp_path: Path) -> Path:
    store = tmp_path / "bonus.sqlite"
    init_store(store, WORLD, CASES).close()
    return store


def _trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


def _kinds(result) -> list[str]:
    return [e["kind"] for e in _trace(result)["events"]]


def _ledger_rows(store: Path, claim_id: str) -> int:
    conn = connect(store)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM refund_ledger WHERE claim_id = ?", (claim_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_there_are_at_least_8_handwritten_adversarial_cases():
    assert len(CASES) >= 8
    assert all("expected" in c and c["case_note"] for c in CASES)


def test_reference_swarm_is_fooled_but_verifier_is_not(bonus_db):
    # B-01: order says 2 days (no entitlement), ticket says 7 days.
    fooled = swarm_reference.run_claim("B-01", seed=BAD_SEED, store_path=str(bonus_db))
    assert fooled.status == "resolved"  # the weakness the verifier must catch

    store2 = bonus_db.parent / "second.sqlite"
    init_store(store2, WORLD, CASES).close()
    safe = swarm_verified.run_claim("B-01", seed=BAD_SEED, store_path=str(store2))
    assert safe.status == "denied"
    assert _ledger_rows(store2, "B-01") == 0
    assert "verifier_override" in _kinds(safe)


def test_verifier_repairs_an_understated_ticket_and_pays_the_structured_amount(bonus_db):
    # B-02: order says 5 days, ticket understates as 1 day. Expected 28.000.
    result = swarm_verified.run_claim("B-02", seed=BAD_SEED, store_path=str(bonus_db))
    assert result.status == "resolved"
    assert result.proposal_amount == BY_ID["B-02"]["expected"]["proposal_amount"]
    assert _ledger_rows(bonus_db, "B-02") == 1


def test_verifier_is_silent_when_nothing_is_wrong(bonus_db):
    result = swarm_verified.run_claim("B-02", seed=11, store_path=str(bonus_db))
    assert result.status == "resolved"
    assert "verifier_override" not in _kinds(result)


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
@pytest.mark.parametrize("claim_id", sorted(BY_ID))
def test_verified_swarm_matches_handwritten_labels(tmp_path, claim_id, seed):
    store = tmp_path / "s.sqlite"
    init_store(store, WORLD, CASES).close()
    result = swarm_verified.run_claim(claim_id, seed=seed, store_path=str(store))
    expected = BY_ID[claim_id]["expected"]
    assert result.status == expected["status"]
    assert result.proposal_amount == expected["proposal_amount"]
    assert _ledger_rows(store, claim_id) == expected["refund_count"]


def test_trace_has_no_secret_after_a_verifier_override(bonus_db):
    result = swarm_verified.run_claim("B-01", seed=BAD_SEED, store_path=str(bonus_db))
    raw = Path(result.trace_path).read_text(encoding="utf-8")
    assert not any(marker in raw for marker in SECRETS)


def test_unknown_claim_fails_with_no_refund(bonus_db):
    result = swarm_verified.run_claim("B-999", seed=11, store_path=str(bonus_db))
    assert result.status == "failed"
