from lab8.shapes.workflow import run_claim


def test_workflow_unknown_claim_does_not_create_refund(public_db):
    result = run_claim(
        "C-UNKNOWN",
        seed=11,
        store_path=str(public_db),
    )

    assert result.status == "failed"
    assert result.error_reason == "unknown_claim"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert result.committed_audit_count == 0