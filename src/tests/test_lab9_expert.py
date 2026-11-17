"""M7 public vectors for the integrity gate (hand-built reports, no shape run)."""
import copy

import pytest

pytestmark = pytest.mark.student


def _report(rows, metrics, items=4, seeds=(1, 2)):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": []}


ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "denial", "metric": "pass_rate", "min": 0.9, "no_significant_drop": True, "blocking": True}]}


@pytest.fixture()
def gate():
    from lab9 import gate

    return gate


def base():
    return _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})


def test_report_against_itself_is_trustworthy(gate):
    assert gate.integrity_check(base(), base(), SPEC, SPEC) == []


def test_edited_metric_that_rows_do_not_support(gate):
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)


def test_duplicate_row_replacing_a_failure(gate):
    rows = copy.deepcopy(ROWS)
    rows[-1] = copy.deepcopy(rows[0])
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)


def test_none_value_and_evaluator_failure(gate):
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = None
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)
    rep = base()
    rep["evaluator_failures"] = ["E-000@1:ApprovalBypass:boom"]
    assert gate.integrity_check(rep, base(), SPEC)


def test_relabelled_slice_hides_regression(gate):
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)


def test_ratchet_rejects_each_kind_of_loosening(gate):
    for edit in (lambda s: s["metrics"][0]["threshold"].update(min=0.5),
                 lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
                 lambda s: s["metrics"][0].update(blocking=False),
                 lambda s: s.update(metrics=[]),
                 lambda s: s["slices"][0].update(min=0.5),
                 lambda s: s.update(slices=[])):
        loose = copy.deepcopy(SPEC)
        edit(loose)
        assert gate.integrity_check(base(), base(), loose, SPEC), edit
    stricter = copy.deepcopy(SPEC)
    stricter["metrics"][0]["threshold"]["min"] = 0.9
    assert gate.integrity_check(base(), base(), stricter, SPEC) == []
