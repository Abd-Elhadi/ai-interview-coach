import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from interview_coach.ui.gradio_app import build_app  # noqa: E402

demo = build_app()

if __name__ == "__main__":
    demo.launch()