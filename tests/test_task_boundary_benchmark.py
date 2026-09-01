from benchmarks.task_boundary_benchmark import run_benchmark


def test_seeded_task_boundary_benchmark() -> None:
    result = run_benchmark()
    assert result["scenario_count"] == 10
    assert result["summary"] == {
        "correct": 10,
        "blocking_recall": 1.0,
        "blocking_precision": 1.0,
        "false_reopening_rate": 0.0,
        "all_passed": True,
    }
