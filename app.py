import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from interview_coach.ui.gradio_app import build_app  # noqa: E402

demo = build_app()

if __name__ == "__main__":
    demo.launch()