import pytest

from interview_coach.coding import runner

GOOD = """
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
"""
WRONG = "def two_sum(nums, target):\n    return [0, 0]\n"
LOOP = "def two_sum(nums, target):\n    while True:\n        pass\n"


def test_correct_solution_passes_all():
    out = runner.run_tests(GOOD, "c1")
    assert out["passed"] == out["total"] == 4
    assert out["error"] is None


def test_wrong_solution_fails():
    assert runner.run_tests(WRONG, "c1")["passed"] < 4


def test_infinite_loop_times_out():
    assert "Time limit" in runner.run_tests(LOOP, "c1")["error"]


def test_forbidden_import_rejected():
    out = runner.run_tests("import os\ndef two_sum(nums, target):\n    return []\n", "c1")
    assert "Import not allowed" in out["error"]


def test_dunder_access_rejected():
    out = runner.run_tests("def two_sum(nums, target):\n    return ().__class__\n", "c1")
    assert "Dunder" in out["error"]


def test_hidden_cases_not_exposed():
    out = runner.run_tests(GOOD, "c1")
    hidden = [r for r in out["results"] if not r["visible"]]
    assert hidden and all("args" not in r and "expected" not in r for r in hidden)


def test_malformed_csharp_case_is_reported_not_raised(monkeypatch, tmp_path):
    problem = {
        "id": "c1",
        "function_name": "TwoSum",
        "tests": [{"args": [[1, 2]], "expected": [0, 1], "visible": True}],
    }
    monkeypatch.setattr(
        runner,
        "_run_json_process",
        lambda *args, **kwargs: {
            "results": [{"passed": False, "error": "Invalid generated test case"}]
        },
    )
    out = runner._run_csharp("public static class Solution {}", problem, str(tmp_path))
    assert out["results"][0]["error"] == "Invalid generated test case"


def test_standalone_csharp_method_is_wrapped_for_runner(monkeypatch, tmp_path):
    problem = {
        "id": "c1",
        "function_name": "findUniqueElements",
        "tests": [{"args": [[1], [2]], "expected": [1, 2], "visible": True}],
    }
    captured = {}

    def fake_process(command, cwd, **kwargs):
        captured["source"] = (tmp_path / "Program.cs").read_text()
        return {"results": [{"passed": True}]}

    monkeypatch.setattr(runner, "_run_json_process", fake_process)
    runner._run_csharp(
        "public int[] findUniqueElements(int[] array1, int[] array2) { return array1; }",
        problem,
        str(tmp_path),
    )

    assert "public static class Solution" in captured["source"]
    assert "public static int[] findUniqueElements" in captured["source"]


def test_csharp_three_argument_array_call_matches_generated_signature():
    call, _ = runner._csharp_case(
        "c1",
        [[1, 2], [2, 3], 2],
        "findPairsWithSum",
    )
    assert call == "Solution.findPairsWithSum(new[] {1,2}, new[] {2,3}, 2)"


def test_standalone_javascript_function_is_exported(monkeypatch, tmp_path):
    problem = {
        "function_name": "findMaxCommonElement",
        "tests": [{"args": [[1], [1]], "expected": 1, "visible": True}],
    }
    captured = {}

    def fake_process(command, cwd, **kwargs):
        captured["source"] = (tmp_path / "solution.js").read_text()
        return {"results": [{"passed": True}]}

    monkeypatch.setattr(runner, "_run_json_process", fake_process)
    runner._run_javascript(
        "function findMaxCommonElement(arr1, arr2) { return 1; }",
        problem,
        str(tmp_path),
    )

    assert "module.exports = { findMaxCommonElement };" in captured["source"]