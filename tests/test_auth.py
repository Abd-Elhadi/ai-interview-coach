import sqlite3

import pytest

from interview_coach import auth


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_PATH", tmp_path / "test.db")
    auth._failures.clear()
    auth.init_db()


def test_sign_up_and_sign_in():
    user = auth.sign_up("Jane@Example.com", "password123", "password123")
    assert user["email"] == "jane@example.com"
    assert auth.sign_in("jane@example.com", "password123")["id"] == user["id"]


def test_duplicate_email_rejected():
    auth.sign_up("a@b.co", "password123", "password123")
    with pytest.raises(auth.AuthError):
        auth.sign_up("A@B.co", "password123", "password123")


def test_wrong_password_and_unknown_email_share_a_message():
    auth.sign_up("a@b.co", "password123", "password123")
    with pytest.raises(auth.AuthError, match="Invalid email or password"):
        auth.sign_in("a@b.co", "wrongpass1")
    with pytest.raises(auth.AuthError, match="Invalid email or password"):
        auth.sign_in("nobody@b.co", "password123")


@pytest.mark.parametrize("password,confirm", [("short", "short"), ("password123", "different123")])
def test_weak_or_mismatched_password_rejected(password, confirm):
    with pytest.raises(auth.AuthError):
        auth.sign_up("a@b.co", password, confirm)


def test_lockout_after_repeated_failures():
    auth.sign_up("a@b.co", "password123", "password123")
    for _ in range(auth.MAX_FAILURES):
        with pytest.raises(auth.AuthError):
            auth.sign_in("a@b.co", "wrongpass1")
    with pytest.raises(auth.AuthError, match="Too many"):
        auth.sign_in("a@b.co", "password123")


def test_password_is_hashed():
    auth.sign_up("a@b.co", "password123", "password123")
    stored = sqlite3.connect(auth.DB_PATH).execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("scrypt$") and "password123" not in stored


def test_reports_are_private_to_their_owner():
    first = auth.sign_up("a@b.co", "password123", "password123")
    second = auth.sign_up("c@d.co", "password123", "password123")
    report_id = auth.save_report(first["id"], 4.0, "# Report")
    assert auth.get_report(first["id"], report_id) == "# Report"
    assert auth.get_report(second["id"], report_id) is None


def test_seen_questions_ignore_duplicates():
    user = auth.sign_up("a@b.co", "password123", "password123")
    auth.mark_seen(user["id"], ["b1", "t1"])
    auth.mark_seen(user["id"], ["b1", "s1"])
    assert sorted(auth.seen_question_ids(user["id"])) == ["b1", "s1", "t1"]