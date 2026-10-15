import pytest

from mcp_server import server

TYPES = ["behavioral", "technical", "situational"]
LEVELS = ["junior", "mid", "senior"]


@pytest.mark.parametrize("qtype", TYPES)
def test_rubric_weights_sum_to_one(qtype):
    rubric = server.get_scoring_rubric(qtype)
    assert abs(sum(d["weight"] for d in rubric["dimensions"]) - 1.0) < 1e-9


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("qtype", TYPES)
def test_question_available_for_every_level(qtype, level):
    result = server.get_interview_questions("backend engineer", level, qtype, 1)
    assert len(result) == 1
    assert result[0]["category"] == qtype


def test_quantity_is_capped():
    assert len(server.get_interview_questions("x", "mid", "behavioral", 99)) <= 5


@pytest.mark.parametrize("qtype", TYPES)
def test_delivery_guidelines_keys(qtype):
    guide = server.get_delivery_guidelines(qtype)
    assert {"recommended_duration_seconds", "recommended_structure"} <= guide.keys()


def test_read_resume_restricted(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "RESUME_DIR", tmp_path.resolve())
    (tmp_path / "cv.txt").write_text("hello")
    assert server.read_resume("cv.txt") == "hello"
    with pytest.raises(ValueError):
        server.read_resume("cv.exe")
    with pytest.raises(FileNotFoundError):
        server.read_resume("../secret.txt")