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