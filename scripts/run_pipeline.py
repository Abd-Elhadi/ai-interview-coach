import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from interview_coach import pipeline  # noqa: E402

resume = (ROOT / "sample_data" / "resume.txt").read_text()
job = (ROOT / "sample_data" / "job_post.txt").read_text()

session = pipeline.start_session(resume, job)
print("Role:", session.job_profile.title, session.job_profile.seniority)
for q in session.plan.questions:
    print(f"- [{q.category}] {q.question} (source {q.source_question_id})")

answer = (
    "At BrightPay our payment API was slow during peak hours. I profiled the endpoints, "
    "found repeated database reads, and added Redis caching. I rolled it out behind a flag "
    "and monitored errors. Average latency dropped from 420 ms to 180 ms."
)
ev = pipeline.evaluate_answer(session, 0, answer)
print("Score:", ev.overall_score)
print("Improved:", ev.improved_answer)