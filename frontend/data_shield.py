"""Data shield: hide personal identifiers from DeepL during text translation.

Sensitive values are swapped for XML placeholders such as ``<x i="1"/>``
before the text is sent to DeepL. DeepL is called with ``tag_handling=xml``
so it keeps the placeholders intact, and the real values are put back into
the translated text afterwards. The values never leave this server.

Because the whole text is sent as XML, the rest of the text is XML-escaped
before masking and unescaped again on restore.
"""

import os
import re
from dataclasses import dataclass, field
from html import escape, unescape

PLACEHOLDER_TAG = "x"
_PLACEHOLDER_RE = re.compile(r'<x\s+i="(\d+)"\s*/>')

# Order matters: earlier patterns win when matches overlap.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "pan",
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    ),
    (
        "aadhaar",
        re.compile(r"(?<![\d-])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![\d-])"),
    ),
    (
        "phone",
        re.compile(
            r"(?<![\w+])(?:\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?![\w-])"
        ),
    ),
    (
        # Policy, account and other long reference numbers, e.g.
        # POL-2024-008812, 0345678912, 12/34567/890. At least 8 digits.
        "reference",
        re.compile(r"\b[A-Za-z]{0,6}[-/]?\d[\d/-]{6,}\d\b"),
    ),
]

_DATE_RE = re.compile(r"^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}$")


def _policy_pattern() -> re.Pattern[str] | None:
    """Optional company-specific format, e.g. DATA_SHIELD_POLICY_PATTERN=\\bBL\\d{9}\\b"""
    pattern = os.getenv("DATA_SHIELD_POLICY_PATTERN", "").strip()
    return re.compile(pattern) if pattern else None


class DataShieldError(Exception):
    """Protected values could not be restored into the translation."""


@dataclass
class ShieldResult:
    text: str
    values: dict[str, str] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)

    @property
    def is_masked(self) -> bool:
        return bool(self.values)


def _is_reference_number(value: str) -> bool:
    digits = sum(character.isdigit() for character in value)
    return digits >= 8 and not _DATE_RE.match(value)


def find_sensitive_spans(text: str) -> list[tuple[int, int, str]]:
    """Return non-overlapping (start, end, kind) spans, earliest pattern first."""
    patterns = list(_PATTERNS)
    custom = _policy_pattern()
    if custom is not None:
        patterns.insert(0, ("policy", custom))

    taken: list[tuple[int, int, str]] = []
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            start, end = match.span()
            if start == end:
                continue
            if kind == "reference" and not _is_reference_number(match.group()):
                continue
            if any(start < t_end and end > t_start for t_start, t_end, _ in taken):
                continue
            taken.append((start, end, kind))
    return sorted(taken)


def mask(text: str) -> ShieldResult:
    """Replace sensitive values with placeholders and XML-escape the rest."""
    spans = find_sensitive_spans(text)
    if not spans:
        return ShieldResult(text=text)

    ids_by_value: dict[str, str] = {}
    result = ShieldResult(text="")
    parts: list[str] = []
    cursor = 0
    for start, end, kind in spans:
        parts.append(escape(text[cursor:start], quote=False))
        value = text[start:end]
        placeholder_id = ids_by_value.get(value)
        if placeholder_id is None:
            placeholder_id = str(len(ids_by_value) + 1)
            ids_by_value[value] = placeholder_id
            result.values[placeholder_id] = value
            result.kinds[placeholder_id] = kind
        parts.append(f'<{PLACEHOLDER_TAG} i="{placeholder_id}"/>')
        cursor = end
    parts.append(escape(text[cursor:], quote=False))
    result.text = "".join(parts)
    return result


def restore(translated: str, shield: ShieldResult) -> str:
    """Put the real values back. Raises if DeepL dropped a placeholder."""
    if not shield.is_masked:
        return translated

    found: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        placeholder_id = match.group(1)
        value = shield.values.get(placeholder_id)
        if value is None:
            raise DataShieldError(
                "The translation contained an unknown protected value."
            )
        found.add(placeholder_id)
        return f"\x00{placeholder_id}\x00"

    with_markers = _PLACEHOLDER_RE.sub(replace, translated)
    missing = set(shield.values) - found
    if missing:
        raise DataShieldError(
            f"{len(missing)} protected value(s) were lost during translation, "
            "so the result was not shown. Try again, or turn off Data shield "
            "for this text."
        )

    restored = unescape(with_markers)
    return re.sub(
        "\x00(\\d+)\x00",
        lambda match: shield.values[match.group(1)],
        restored,
    )


def summary(shield: ShieldResult) -> str:
    labels = {
        "email": "email",
        "pan": "PAN",
        "aadhaar": "Aadhaar number",
        "phone": "phone number",
        "reference": "policy/reference number",
        "policy": "policy number",
    }
    counts: dict[str, int] = {}
    for kind in shield.kinds.values():
        counts[kind] = counts.get(kind, 0) + 1
    parts = []
    for kind, count in counts.items():
        label = labels.get(kind, kind)
        parts.append(f"{count} {label}{'' if count == 1 else 's'}")
    return ", ".join(parts)
