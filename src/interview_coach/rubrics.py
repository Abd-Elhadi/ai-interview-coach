import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "mcp_server" / "data"


@lru_cache
def load_rubrics() -> dict:
    return json.loads((DATA / "rubrics.json").read_text())


def weights_for(question_type: str) -> dict[str, float]:
    return {d["name"]: d["weight"] for d in load_rubrics()[question_type]["dimensions"]}


def dimension_names(question_type: str) -> set[str]:
    return set(weights_for(question_type))

def bank_ids() -> set[str]:
    return {q["id"] for q in json.loads((DATA / "questions.json").read_text())}