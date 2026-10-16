import re
from dataclasses import dataclass, field


class GuardrailError(ValueError):
    pass


@dataclass
class CheckedText:
    text: str
    warnings: list[str] = field(default_factory=list)


INJECTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
        r"disregard (all |any |the )?(previous|prior|above|system) (instructions|prompts?|rules)",
        r"you are now (a|an|the) ",
        r"reveal (your |the )?(system )?prompt",
        r"new instructions:",
    )
]
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,2}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")


def _redact(text: str) -> tuple[str, int]:
    count = 0
    for pattern, token in ((SSN, "[ID]"), (EMAIL, "[EMAIL]"), (PHONE, "[PHONE]")):
        text, hits = pattern.subn(token, text)
        count += hits
    return text, count


def check_text(text: str, label: str, min_chars: int, max_chars: int) -> CheckedText:
    """Validate length, drop prompt-injection lines, redact contact details and IDs."""
    text = (text or "").strip()
    if len(text) < min_chars:
        raise GuardrailError(f"The {label} is too short (minimum {min_chars} characters).")
    if len(text) > max_chars:
        raise GuardrailError(f"The {label} is too long (maximum {max_chars} characters).")

    warnings, kept, removed = [], [], 0
    for line in text.splitlines():
        if any(p.search(line) for p in INJECTION):
            removed += 1
        else:
            kept.append(line)
    if removed:
        warnings.append(f"Removed {removed} line(s) from the {label} that looked like instructions to the AI.")

    cleaned, redacted = _redact("\n".join(kept))
    if redacted:
        warnings.append(f"Redacted {redacted} email, phone, or ID value(s) from the {label} before AI processing.")
    if len(cleaned) < min_chars:
        raise GuardrailError(f"The {label} has too little usable content after cleaning.")
    return CheckedText(cleaned, warnings)