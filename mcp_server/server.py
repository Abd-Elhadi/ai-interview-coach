import json
import os
import uuid
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

DATA = Path(__file__).parent / "data"
RESUME_DIR = Path("tmp/uploads").resolve()
AUDIO_DIR = Path("tmp/audio").resolve()
mcp = FastMCP("interview-coach")

QType = Literal["behavioral", "technical", "situational"]
Level = Literal["junior", "mid", "senior"]

def _load(name):
    return json.loads((DATA / name).read_text())

@mcp.tool()
def get_interview_questions(role: str, level: Level, category: QType, quantity: int = 1) -> list[dict]:
    role = role.strip()[:80]
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


@mcp.tool()
def transcribe_answer(filename: str) -> str:
    """Transcribe one audio answer from the restricted audio directory."""
    path = (AUDIO_DIR / Path(filename).name).resolve()
    if AUDIO_DIR not in path.parents or path.suffix not in {".wav", ".webm", ".mp3"}:
        raise ValueError("Invalid audio path")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with path.open("rb") as audio:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio,
        )
    return transcript.text


@mcp.tool()
def synthesize_question(text: str) -> str:
    """Speak a question with TTS and save the mp3 in the audio directory."""
    filename = f"{uuid.uuid4().hex}.mp3"
    path = (AUDIO_DIR / Path(filename).name).resolve()
    if AUDIO_DIR not in path.parents or path.suffix not in {".mp3"}:
        raise ValueError("Invalid audio path")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text,
        response_format="mp3",
    )
    speech.write_to_file(path)
    return filename


def _problems() -> list[dict]:
    return _load("coding_problems.json")


@mcp.tool()
def get_coding_problem(level: Level, exclude_ids: list[str] | None = None) -> dict:
    """Return one coding problem (prompt, function name, starter code). Hidden tests are never returned."""
    excluded = set(exclude_ids or [])
    for problem in _problems():
        if level in problem["levels"] and problem["id"] not in excluded:
            keys = ("id", "title", "prompt", "function_name", "starter_code")
            return {key: problem[key] for key in keys}
    raise ValueError("No coding problem available for this level")


@mcp.tool()
def get_test_cases(problem_id: str) -> list[dict]:
    """Return the visible test cases of a problem. Hidden cases are never exposed."""
    for problem in _problems():
        if problem["id"] == problem_id:
            return [
                {"args": t["args"], "expected": t["expected"]}
                for t in problem["tests"]
                if t["visible"]
            ]
    raise ValueError("Unknown problem id")

if __name__ == "__main__":
    mcp.run(transport="stdio")