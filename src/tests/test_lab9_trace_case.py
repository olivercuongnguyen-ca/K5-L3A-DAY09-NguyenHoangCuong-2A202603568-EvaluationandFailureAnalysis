"""Regression test for docs/trace_case.md: swarm C-002@55 trusts the ticket over the DB (FM-03).

Runs real shapes on a temp store (MockLLM, no key). The graders must flag the faulty trial and
stay quiet on the `fixed` control for the same claim and seed.
"""
import pytest

pytestmark = pytest.mark.student

CLAIM, SEED = "C-002", 55


def _grade(shape, seed=SEED):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9 import graders
    from lab9.trace_case import investigate

    case = investigate(shape, CLAIM, seed)
    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"],
                           output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})
    return case["trial"], {
        "db_fact_kept": graders.DbFactKept().evaluate(ctx).value,
        "refund_amount_correct": graders.RefundAmountCorrect().evaluate(ctx).value,
    }


def test_swarm_c002_seed55_first_wrong_step_is_model_override():
    trial, verdict = _grade("swarm")
    kinds = [e["kind"] for e in trial["events"]]
    assert kinds.index("model_override") == 2            # step 3: before the quote at step 4
    assert trial["events"][2]["payload"] == {"delay_days": 5}
    assert verdict == {"db_fact_kept": False, "refund_amount_correct": False}
    assert trial["snapshot"]["refund_vnd"] == 20000      # label says 0: the ticket's "5 days" paid out


def test_fixed_control_same_claim_and_seed_is_clean():
    trial, verdict = _grade("fixed")
    assert "model_override" not in [e["kind"] for e in trial["events"]]
    assert verdict == {"db_fact_kept": True, "refund_amount_correct": True}


def test_swarm_c002_other_seed_is_clean():
    """The weakness only fires on seeds divisible by 5, so seed 11 must not trip the graders."""
    _, verdict = _grade("swarm", seed=11)
    assert verdict == {"db_fact_kept": True, "refund_amount_correct": True}
