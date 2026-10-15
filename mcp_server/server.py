import json
from pathlib import Path
from typing import Literal
from mcp.server.fastmcp import FastMCP

DATA = Path(__file__).parent / "data"
RESUME_DIR = Path("tmp/uploads").resolve()
mcp = FastMCP("interview-coach")

QType = Literal["behavioral", "technical", "situational"]
Level = Literal["junior", "mid", "senior"]

def _load(name):
    return json.loads((DATA / name).read_text())

@mcp.tool()
def get_interview_questions(role: str, level: Level, category: QType, quantity: int = 1) -> list[dict]:
    """Return tailored questions from the question bank."""
    quantity = max(1, min(quantity, 5))
    bank = _load("questions.json")
    pool = [q for q in bank if q["category"] == category and level in q["levels"]]
    return pool[:quantity]

@mcp.tool()
def get_scoring_rubric(question_type: QType) -> dict:
    """Return weighted scoring dimensions for a question type."""
    return _load("rubrics.json")[question_type]

@mcp.tool()
def get_delivery_guidelines(question_type: QType) -> dict:
    """Return time range and structure guidance for spoken answers."""
    return _load("delivery.json")[question_type]

@mcp.tool()
def read_resume(filename: str) -> str:
    """Read an uploaded resume from the restricted upload directory."""
    path = (RESUME_DIR / Path(filename).name).resolve()
    if RESUME_DIR not in path.parents or path.suffix not in {".txt", ".pdf"}:
        raise ValueError("Invalid resume path")
    return path.read_text(errors="ignore")

if __name__ == "__main__":
    mcp.run(transport="stdio")