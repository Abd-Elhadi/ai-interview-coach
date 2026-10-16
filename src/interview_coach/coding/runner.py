"""Runs candidate code against test cases in an isolated subprocess.

Demo-level sandbox: AST screening, isolated interpreter, empty environment (no API keys),
temp directory, time and memory limits. Not a replacement for a container sandbox.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "mcp_server" / "data" / "coding_problems.json"
TIMEOUT_SECONDS = 5
MAX_CODE_CHARS = 8000
FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "requests", "urllib", "http",
    "ctypes", "importlib", "builtins", "pickle", "multiprocessing", "threading", "signal",
}
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint"}

HARNESS = """
import contextlib, io, json, sys
from itertools import starmap

source = open(sys.argv[1]).read()
cases = json.load(open(sys.argv[3]))
namespace = {}
sink = io.StringIO()
results = []
try:
    with contextlib.redirect_stdout(sink):
        exec(compile(source, "solution", "exec"), namespace)
    fn = namespace[sys.argv[2]]
except Exception as err:
    print(json.dumps({"fatal": type(err).__name__ + ": " + str(err)[:200]}))
    sys.exit(0)
for case in cases:
    try:
        with contextlib.redirect_stdout(sink):
            got = next(starmap(fn, [case["args"]]))
        got = json.loads(json.dumps(got))
        results.append({"passed": got == case["expected"], "got": got})
    except Exception as err:
        results.append({"passed": False, "error": type(err).__name__ + ": " + str(err)[:200]})
print(json.dumps({"results": results}))
"""


def load_problem(problem_id: str) -> dict:
    for problem in json.loads(DATA.read_text()):
        if problem["id"] == problem_id:
            return problem
    raise ValueError("Unknown problem id")


def validate_code(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as err:
        return f"Syntax error: {err.msg} (line {err.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            roots = {(node.module or "").split(".")[0]}
        else:
            roots = set()
        blocked = roots & FORBIDDEN_IMPORTS
        if blocked:
            return f"Import not allowed: {sorted(blocked)[0]}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                return f"Call not allowed: {node.func.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return "Dunder attribute access is not allowed."
    return None


def _safe_env() -> dict:
    keep = ("PATH", "SYSTEMROOT", "TEMP", "TMP")
    return {key: os.environ[key] for key in keep if key in os.environ}


def _limits() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (536_870_912, 536_870_912))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))


def _failed(tests: list, message: str) -> dict:
    return {"passed": 0, "total": len(tests), "error": message, "results": []}


def run_tests(code: str, problem_id: str) -> dict:
    problem = load_problem(problem_id)
    tests = problem["tests"]
    if len(code) > MAX_CODE_CHARS:
        return _failed(tests, "Code exceeds the size limit.")
    problem_error = validate_code(code)
    if problem_error:
        return _failed(tests, problem_error)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "harness.py").write_text(HARNESS)
        (base / "solution.py").write_text(code)
        (base / "cases.json").write_text(json.dumps(tests))
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "harness.py", "solution.py", problem["function_name"], "cases.json"],
                cwd=tmp,
                env=_safe_env(),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                preexec_fn=_limits if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired:
            return _failed(tests, f"Time limit of {TIMEOUT_SECONDS} seconds exceeded.")

    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return _failed(tests, "Program crashed or produced no result.")
    if "fatal" in payload:
        return _failed(tests, payload["fatal"])

    results = []
    for index, (test, outcome) in enumerate(zip(tests, payload["results"])):
        item = {"index": index, "visible": test["visible"], "passed": outcome["passed"], "error": outcome.get("error")}
        if test["visible"]:
            item.update({"args": test["args"], "expected": test["expected"], "got": outcome.get("got")})
        results.append(item)
    passed = sum(1 for r in results if r["passed"])
    return {"passed": passed, "total": len(tests), "error": None, "results": results}