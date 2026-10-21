"""Runs candidate code against test cases in an isolated subprocess.

Demo-level sandbox: AST screening, isolated interpreter, empty environment (no API keys),
temp directory, time and memory limits. Not a replacement for a container sandbox.
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import shutil

DATA = Path(__file__).resolve().parents[3] / "mcp_server" / "data" / "coding_problems.json"
TIMEOUT_SECONDS = 5
MAX_CODE_CHARS = 8000
LANGUAGES = {"python", "javascript", "csharp"}
FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "requests", "urllib", "http",
    "ctypes", "importlib", "builtins", "pickle", "multiprocessing", "threading", "signal",
}
FORBIDDEN_CALLS = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "dir", "help",
}

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

JS_FUNCTIONS = {"c1": "twoSum", "c2": "isValidParentheses", "c3": "mergeIntervals", "c4": "topKFrequent"}
CSHARP_FUNCTIONS = {"c1": "TwoSum", "c2": "IsValidParentheses", "c3": "MergeIntervals", "c4": "TopKFrequent"}
JS_BLOCKED = ("require(", "process.", "child_process", "fs.", "eval(", "Function(")
CSHARP_BLOCKED = ("System.Diagnostics", "System.IO", "Process.", "File.", "Directory.", "HttpClient")


def starter_code(problem_id: str, language: str) -> str:
    if language == "python":
        return load_problem(problem_id)["starter_code"]
    if language == "javascript":
        name = JS_FUNCTIONS[problem_id]
        return f"function {name}() {{\n    // implement the solution\n}}\n\nmodule.exports = {{ {name} }};\n"
    if language == "csharp":
        signatures = {
            "c1": "int[] TwoSum(int[] nums, int target)",
            "c2": "bool IsValidParentheses(string s)",
            "c3": "int[][] MergeIntervals(int[][] intervals)",
            "c4": "int[] TopKFrequent(int[] nums, int k)",
        }
        return (
            "using System;\nusing System.Collections.Generic;\n\n"
            "public static class Solution\n{\n"
            f"    public static {signatures[problem_id]}\n    {{\n        throw new NotImplementedException();\n    }}\n}}\n"
        )
    raise ValueError(f"Unsupported language: {language}")


def load_problem(problem_id: str) -> dict:
    for problem in load_all_problems():
        if problem["id"] == problem_id:
            return problem
    raise ValueError("Unknown problem id")


def load_all_problems() -> list[dict]:
    return json.loads(DATA.read_text())


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


def _validate_language_code(code: str, language: str) -> str | None:
    if language == "python":
        return validate_code(code)
    blocked = JS_BLOCKED if language == "javascript" else CSHARP_BLOCKED
    match = next((token for token in blocked if token in code), None)
    return f"Code contains a blocked operation: {match}" if match else None


def _safe_env() -> dict:
    keep = (
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
        "DOTNET_ROOT", "DOTNET_CLI_HOME",
    )
    return {key: os.environ[key] for key in keep if key in os.environ}


def _limits() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (536_870_912, 536_870_912))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))


def _failed(tests: list, message: str) -> dict:
    return {"passed": 0, "total": len(tests), "error": message, "results": []}


def _run_json_process(
    command: list[str], cwd: str, use_dotnet_environment: bool = False, timeout_seconds: int = TIMEOUT_SECONDS
) -> dict:
    env = os.environ.copy() if use_dotnet_environment else _safe_env()
    if use_dotnet_environment:
        for key in list(env):
            if any(secret in key.upper() for secret in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")):
                env.pop(key, None)
    if "NUGET_PACKAGES" not in env:
        env["NUGET_PACKAGES"] = str(Path.home() / ".nuget" / "packages")
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            preexec_fn=_limits if os.name == "posix" else None,
        )
    except FileNotFoundError as err:
        return {"error": f"Required runtime is unavailable: {err.filename}"}
    except subprocess.TimeoutExpired:
        return {"error": f"Time limit of {timeout_seconds} seconds exceeded."}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        diagnostic = "\n".join(part for part in (proc.stderr.strip(), proc.stdout.strip()) if part)
        detail = " ".join(diagnostic.splitlines()[-4:]) if diagnostic else ""
        return {"error": f"Program crashed or produced no result.{(' ' + detail[:300]) if detail else ''}"}


def _run_python(code: str, problem: dict, tmp: str) -> dict:
    base = Path(tmp)
    (base / "harness.py").write_text(HARNESS)
    (base / "solution.py").write_text(code)
    (base / "cases.json").write_text(json.dumps(problem["tests"]))
    return _run_json_process(
        [sys.executable, "-I", "harness.py", "solution.py", problem["function_name"], "cases.json"],
        tmp,
    )


def _run_javascript(code: str, problem: dict, tmp: str) -> dict:
    base = Path(tmp)
    harness = """
const solution = require('./solution.js');
const cases = require('./cases.json');
const fn = solution[process.argv[2]];
if (typeof fn !== 'function') { console.log(JSON.stringify({fatal: 'Function was not exported.'})); process.exit(0); }
const results = [];
for (const test of cases) {
  try {
    const got = fn(...test.args);
    results.push({passed: JSON.stringify(got) === JSON.stringify(test.expected), got});
  } catch (err) { results.push({passed: false, error: `${err.name}: ${String(err.message).slice(0, 200)}`}); }
}
console.log(JSON.stringify({results}));
"""
    (base / "harness.js").write_text(harness)
    if not re.search(r"\bmodule\.exports\b|\bexports\.", code):
        code = f"{code.rstrip()}\n\nmodule.exports = {{ {problem['function_name']} }};\n"
    (base / "solution.js").write_text(code)
    (base / "cases.json").write_text(json.dumps(problem["tests"]))
    return _run_json_process(["node", "harness.js", problem["function_name"]], tmp)


def _csharp_case(problem_id: str, args: list, function_name: str | None = None) -> tuple[str, str]:
    function_name = function_name or CSHARP_FUNCTIONS[problem_id]
    if len(args) == 3 and all(isinstance(value, list) for value in args[:2]) and isinstance(args[2], int):
        call = (
            f"Solution.{function_name}({_csharp_array(args[0])}, "
            f"{_csharp_array(args[1])}, {args[2]})"
        )
        return call, json.dumps(args)
    if len(args) == 2 and all(isinstance(value, list) for value in args):
        call = f"Solution.{function_name}({_csharp_array(args[0])}, {_csharp_array(args[1])})"
        return call, json.dumps(args)
    if problem_id == "c1":
        call = f"Solution.{function_name}({_csharp_array(args[0])}, {args[1]})"
    elif problem_id == "c2":
        call = f"Solution.{function_name}({json.dumps(args[0])})"
    elif problem_id == "c3":
        intervals = ",".join(_csharp_array(pair) for pair in args[0])
        call = f"Solution.{function_name}(new[] {{{intervals}}})"
    else:
        call = f"Solution.{function_name}({_csharp_array(args[0])}, {args[1]})"
    return call, json.dumps(args)


def _csharp_array(values: list) -> str:
    if not all(isinstance(value, int) for value in values):
        raise TypeError("C# array test arguments must contain integers.")
    return "new[] {" + ",".join(map(str, values)) + "}"


def _prepare_csharp_solution(code: str) -> str:
    if re.search(r"\bclass\s+Solution\b", code):
        return code
    method_code = re.sub(
        r"\bpublic\s+(?!static\b)",
        "public static ",
        code,
        count=1,
    )
    return "public static class Solution\n{\n" + method_code.strip() + "\n}\n"


def _run_csharp(code: str, problem: dict, tmp: str) -> dict:
    base = Path(tmp)
    checks = []
    for test in problem["tests"]:
        try:
            call, _ = _csharp_case(problem["id"], test["args"], problem["function_name"])
        except (IndexError, TypeError, ValueError) as err:
            checks.append(
                "results.Add(new { passed = false, error = "
                f"\"Invalid generated test case: {str(err).replace(chr(34), chr(39))}\" }});"
            )
            continue
        expected = json.dumps(test["expected"], separators=(",", ":")).replace('"', '\\"')
        checks.append(
            f"try {{ var got = System.Text.Json.JsonSerializer.Serialize({call}); "
            f"results.Add(new {{ passed = got == \"{expected}\" }}); }} "
            "catch (Exception err) { results.Add(new { passed = false, error = err.GetType().Name + \": \" + err.Message }); }"
        )
    harness = """
public static class Harness
{
    public static void Main()
    {
        var results = new List<object>();
        CHECKS
        Console.WriteLine(JsonSerializer.Serialize(new { results }));
    }
}
""".replace("CHECKS", "\n        ".join(checks))
    header = "using System;\nusing System.Collections.Generic;\nusing System.Text.Json;\n"
    (base / "Program.cs").write_text(header + _prepare_csharp_solution(code) + "\n" + harness)
    (base / "Coding.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup>"
        "<OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>"
        "<ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable>"
        "</PropertyGroup></Project>"
    )
    return _run_json_process(
        ["dotnet", "run", "--project", "Coding.csproj", "--nologo"],
        tmp,
        use_dotnet_environment=True,
        timeout_seconds=30,
    )

def available_languages() -> list[str]:
    """Return configured languages whose runtimes are installed."""
    enabled = {
        part.strip().lower()
        for part in os.getenv("ENABLED_LANGUAGES", "python,javascript,csharp").split(",")
    }
    tools = {
        "python": True,
        "javascript": shutil.which("node") is not None,
        "csharp": shutil.which("dotnet") is not None,
    }
    languages = [name for name in ("python", "javascript", "csharp") if name in enabled and tools[name]]
    return languages or ["python"]


def run_tests(
    code: str,
    problem_id: str,
    language: str = "python",
    problem: dict | None = None,
) -> dict:
    if language not in available_languages():
        raise ValueError(f"{language} is not enabled on this deployment.")
    problem = problem or load_problem(problem_id)
    if "tests" not in problem:
        problem = {**problem, "tests": load_problem(problem_id)["tests"]}
    tests = problem["tests"]
    if len(code) > MAX_CODE_CHARS:
        return _failed(tests, "Code exceeds the size limit.")
    problem_error = _validate_language_code(code, language)
    if problem_error:
        return _failed(tests, problem_error)

    with tempfile.TemporaryDirectory() as tmp:
        runners = {"python": _run_python, "javascript": _run_javascript, "csharp": _run_csharp}
        payload = runners[language](code, problem, tmp)
    if "error" in payload and "results" not in payload:
        return _failed(tests, payload["error"])
    if "fatal" in payload:
        return _failed(tests, payload["fatal"])
    if len(payload.get("results", [])) != len(tests):
        return _failed(tests, "Test harness returned an incomplete result.")

    results = []
    for index, (test, outcome) in enumerate(zip(tests, payload["results"])):
        item = {"index": index, "visible": test["visible"], "passed": outcome["passed"], "error": outcome.get("error")}
        if test["visible"]:
            item.update({"args": test["args"], "expected": test["expected"], "got": outcome.get("got")})
        results.append(item)
    passed = sum(1 for r in results if r["passed"])
    return {"passed": passed, "total": len(tests), "error": None, "results": results}