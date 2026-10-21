from pathlib import Path

import pytest

from interview_coach import emailer, reporting


def test_unconfigured_email(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(emailer.EmailError, match="not configured"):
        emailer.send_report(1, "a@b.co", "missing.pdf", 4.0)


def test_email_rate_limit(monkeypatch, tmp_path):
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setenv("RESEND_API_KEY", "test")
    emailer._sent.clear()

    class Response:
        status_code = 200

        def json(self):
            return {}

    def fake_post(url, json, headers, timeout):
        return Response()

    monkeypatch.setattr(emailer.httpx, "post", fake_post)
    for _ in range(emailer.MAX_PER_HOUR):
        emailer.send_report(1, "a@b.co", str(pdf), 4.0)
    with pytest.raises(emailer.EmailError, match="limit"):
        emailer.send_report(1, "a@b.co", str(pdf), 4.0)


def test_pdf_is_created_and_survives_odd_characters():
    text = "# Title\n\n- Point with <b>tags</b> & symbols \u2192 \u2019quotes\u2019\n\nPlain line"
    path = reporting.report_to_pdf(text)
    assert Path(path).read_bytes()[:4] == b"%PDF"