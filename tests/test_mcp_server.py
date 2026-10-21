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

def test_questions_vary_between_calls():
    firsts = {server.get_interview_questions("x", "mid", "behavioral", 1)[0]["id"] for _ in range(40)}
    assert len(firsts) > 1


def test_excluded_ids_are_skipped():
    out = server.get_interview_questions("x", "mid", "behavioral", 5, ["b1", "b2"])
    assert not {"b1", "b2"} & {q["id"] for q in out}


def test_exclusion_falls_back_when_pool_is_exhausted():
    every_mid = ["b1", "b2", "b3", "b5", "b7"]
    assert server.get_interview_questions("x", "mid", "behavioral", 1, every_mid)