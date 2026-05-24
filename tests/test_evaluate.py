from importlib import import_module


evaluate_module = import_module("eval.evaluate")


def test_build_qrels_and_run_uses_source_level_first_rank_scores():
    rows = [
        {
            "id": "Q001",
            "expected_sources": ["shipment_escalation_sop.md"],
            "retrieved_sources": [
                "customer_communication_playbook.md",
                "shipment_escalation_sop.md",
                "procurement_approval_policy.md",
            ],
            "retrieval_eligible": True,
        },
        {
            "id": "Q017",
            "expected_sources": [],
            "retrieved_sources": [],
            "retrieval_eligible": False,
        },
    ]

    qrels, run = evaluate_module.build_qrels_and_run(rows)

    assert qrels == {"Q001": {"shipment_escalation_sop.md": 1}}
    assert run == {
        "Q001": {
            "customer_communication_playbook.md": 1.0,
            "shipment_escalation_sop.md": 0.5,
            "procurement_approval_policy.md": 1 / 3,
        }
    }


def test_calculate_retrieval_metrics_excludes_non_retrieval_rows():
    rows = [
        {
            "id": "Q001",
            "expected_sources": ["shipment_escalation_sop.md"],
            "retrieved_sources": ["shipment_escalation_sop.md"],
            "retrieval_eligible": True,
        },
        {
            "id": "Q011",
            "expected_sources": ["inventory_branch_snapshot.csv"],
            "retrieved_sources": [],
            "retrieval_eligible": False,
        },
    ]

    metrics = evaluate_module.calculate_retrieval_metrics(rows, metrics=["hit_rate@1", "precision@1", "recall@1"])

    assert metrics == {"hit_rate@1": 1.0, "precision@1": 1.0, "recall@1": 1.0}


def test_retrieval_eligibility_requires_sources_and_retrieval_route_type():
    assert evaluate_module._is_retrieval_eligible(
        {"question_type": "rag", "expected_sources": ["shipment_escalation_sop.md"]}
    )
    assert evaluate_module._is_retrieval_eligible(
        {"question_type": "guardrail", "expected_sources": ["shipment_escalation_sop.md"]}
    )
    assert not evaluate_module._is_retrieval_eligible(
        {"question_type": "structured_data", "expected_sources": ["inventory_branch_snapshot.csv"]}
    )
    assert not evaluate_module._is_retrieval_eligible(
        {"question_type": "unsupported", "expected_sources": []}
    )


def test_rank_and_recall_helpers_are_top_k_aware():
    retrieved = ["a.md", "b.md", "c.md"]
    expected = ["b.md", "d.md"]

    assert evaluate_module._rank_of_first_expected(retrieved, expected) == 2
    assert evaluate_module._recall_at_k(retrieved, expected, top_k=1) == 0.0
    assert evaluate_module._recall_at_k(retrieved, expected, top_k=2) == 0.5
