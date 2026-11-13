"""Data shield for uploaded documents.

Before a document is sent to DeepL, every sensitive value found by
``data_shield.find_sensitive_spans`` is replaced with a token such as
``[ZXQJAAB]``, and each token is swapped back for its real value after the
translation comes back.

The square brackets matter: when a bare code like ``ZXQJAAB`` stands alone
(an Aadhaar number on its own line, a table cell) DeepL spells it out in
the target script, e.g. Devanagari. In tests across Marathi, Hindi, German,
Japanese, Chinese and Arabic the bracketed form always came back unchanged.

Supported inputs:
  * PDF with selectable text (values are redacted and overwritten)
  * DOCX / PPTX (text inside the Office XML is rewritten)
  * Plain text formats such as TXT, Markdown, HTML, SRT, JSON

Images, scanned PDFs and other formats cannot be checked, so they raise
``DocumentShieldUnsupported`` instead of being sent unmasked.

After masking, the masked file is scanned again. If any sensitive value is
still present the file is refused, so a value can never slip through.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePath

import pymupdf
from lxml import etree

try:
    from . import data_shield
except ImportError:
    import data_shield

TOKEN_PREFIX = "ZXQJ"
# Bracketed token, tolerating spaces DeepL may add inside the brackets, or
# a bare token if DeepL dropped the brackets.
_TOKEN_RE = re.compile(
    rf"\[\s*({TOKEN_PREFIX}[A-Z]{{3}})\s*\]"
    rf"|(?<![A-Z])({TOKEN_PREFIX}[A-Z]{{3}})(?![A-Z])"
)


def _token_key(match: re.Match[str]) -> str:
    return f"[{match.group(1) or match.group(2)}]"

PLAIN_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".htm", ".html", ".srt", ".vtt", ".xml",
    ".json", ".yaml", ".yml", ".properties", ".strings", ".xlf", ".xliff",
    ".dita", ".resx",
}
OFFICE_EXTENSIONS = {".docx", ".pptx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_TEXT_TAGS = {f"{{{_W_NS}}}t", f"{{{_A_NS}}}t"}
_PARAGRAPH_TAGS = {f"{{{_W_NS}}}p", f"{{{_A_NS}}}p"}

# A PDF page with less text than this but with images is treated as a scan.
_SCANNED_PAGE_TEXT_LIMIT = 20


class DocumentShieldUnsupported(Exception):
    """Data shield cannot check this file, so it must not be sent masked."""


@dataclass
class MaskedDocument:
    content: bytes
    shield: data_shield.ShieldResult
    warnings: list[str] = field(default_factory=list)


class _Tokens:
    """Gives each distinct sensitive value its own token."""

    def __init__(self) -> None:
        self.shield = data_shield.ShieldResult(text="")
        self._by_value: dict[str, str] = {}

    def token_for(self, value: str, kind: str) -> str:
        token = self._by_value.get(value)
        if token is None:
            token = _make_token(len(self._by_value))
            self._by_value[value] = token
            self.shield.values[token] = value
            self.shield.kinds[token] = kind
        return token


def _make_token(index: int) -> str:
    if index >= 26 ** 3:
        raise DocumentShieldUnsupported(
            "This file has too many personal details for Data shield."
        )
    letters = ""
    for _ in range(3):
        index, remainder = divmod(index, 26)
        letters = chr(ord("A") + remainder) + letters
    return f"[{TOKEN_PREFIX}{letters}]"


def _extension(file_name: str) -> str:
    return PurePath(file_name).suffix.lower()


# ---------------------------------------------------------------- masking


def mask_document(file_name: str, content: bytes) -> MaskedDocument:
    """Return a copy of the file with sensitive values replaced by tokens."""
    extension = _extension(file_name)
    tokens = _Tokens()

    if extension == ".pdf":
        masked, warnings = _mask_pdf(content, tokens)
    elif extension in OFFICE_EXTENSIONS:
        masked, warnings = _mask_office(content, tokens)
    elif extension in PLAIN_TEXT_EXTENSIONS:
        masked, warnings = _mask_plain(content, tokens), []
    elif extension in IMAGE_EXTENSIONS:
        raise DocumentShieldUnsupported(
            "Data shield can't read text inside images, so it can't hide "
            "numbers in this file."
        )
    else:
        raise DocumentShieldUnsupported(
            f"Data shield can't check {extension or 'this type of'} files yet."
        )

    _verify_masked(extension, masked, tokens.shield)
    return MaskedDocument(content=masked, shield=tokens.shield, warnings=warnings)


def _mask_string(text: str, tokens: _Tokens) -> str:
    parts = []
    cursor = 0
    for start, end, kind in data_shield.find_sensitive_spans(text):
        parts.append(text[cursor:start])
        parts.append(tokens.token_for(text[start:end], kind))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentShieldUnsupported(
            "Data shield can only check text files saved as UTF-8."
        ) from error


def _mask_plain(content: bytes, tokens: _Tokens) -> bytes:
    return _mask_string(_decode_text(content), tokens).encode("utf-8")


def _mask_pdf(content: bytes, tokens: _Tokens) -> tuple[bytes, list[str]]:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (RuntimeError, ValueError) as error:
        raise DocumentShieldUnsupported(
            "Data shield could not open this PDF."
        ) from error

    with document:
        if document.needs_pass:
            raise DocumentShieldUnsupported(
                "Data shield can't check password-protected PDFs."
            )

        image_pages = 0
        for page in document:
            text = page.get_text()
            has_images = bool(page.get_images(full=False))
            if has_images:
                image_pages += 1
            if has_images and len(text.strip()) < _SCANNED_PAGE_TEXT_LIMIT:
                raise DocumentShieldUnsupported(
                    f"Page {page.number + 1} looks like a scan. Data shield "
                    "can't read text inside scanned pages."
                )

            replacements = []
            for start, end, kind in data_shield.find_sensitive_spans(text):
                value = text[start:end]
                token = tokens.token_for(value, kind)
                for rect in page.search_for(value):
                    replacements.append((rect, token))
            _overwrite_pdf_text(page, replacements)

            for widget in page.widgets() or []:
                value = widget.field_value
                if isinstance(value, str) and value:
                    masked_value = _mask_string(value, tokens)
                    if masked_value != value:
                        widget.field_value = masked_value
                        widget.update()

        metadata = document.metadata or {}
        masked_metadata = {
            key: _mask_string(value, tokens) if isinstance(value, str) else value
            for key, value in metadata.items()
        }
        if masked_metadata != metadata:
            document.set_metadata(masked_metadata)

        masked = document.tobytes(garbage=3, deflate=True)

    warnings = []
    if image_pages:
        warnings.append(
            f"{image_pages} page(s) contain images. Text inside images "
            "can't be checked and is sent as it is."
        )
    return masked, warnings


def _overwrite_pdf_text(page, replacements) -> None:
    """Remove the text under each rectangle and write new text in its place."""
    if not replacements:
        return
    for rect, _ in replacements:
        page.add_redact_annot(rect, fill=(1, 1, 1))

    redact_options = {"images": pymupdf.PDF_REDACT_IMAGE_NONE}
    if hasattr(pymupdf, "PDF_REDACT_LINE_ART_NONE"):
        redact_options["graphics"] = pymupdf.PDF_REDACT_LINE_ART_NONE
    page.apply_redactions(**redact_options)

    for rect, text in replacements:
        font_size = max(rect.height * 0.8, 4)
        baseline = pymupdf.Point(rect.x0, rect.y1 - rect.height * 0.22)
        page.insert_text(baseline, text, fontsize=font_size, fontname="helv")


def _paragraph_groups(root) -> list[list]:
    """Text nodes grouped by the paragraph that directly contains them."""
    groups: dict[int, list] = {}
    order: list[int] = []
    for node in root.iter(*_TEXT_TAGS):
        paragraph = next(
            (a for a in node.iterancestors() if a.tag in _PARAGRAPH_TAGS),
            None,
        )
        key = id(paragraph) if paragraph is not None else id(node)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(node)
    return [groups[key] for key in order]


def _rewrite_group(nodes, replacements) -> None:
    """Apply (start, end, new_text) replacements to text split across nodes.

    New text goes into the node where the replaced value starts; the rest of
    the value is removed from the following nodes, so formatting is kept.
    """
    if not replacements:
        return
    offset = 0
    for node in nodes:
        text = node.text or ""
        node_start, node_end = offset, offset + len(text)
        offset = node_end
        pieces = []
        cursor = node_start
        changed = False
        for start, end, new_text in replacements:
            if end <= node_start or start >= node_end:
                continue
            changed = True
            pieces.append(text[cursor - node_start:max(start, node_start) - node_start])
            if node_start <= start < node_end:
                pieces.append(new_text)
            cursor = min(end, node_end)
        if not changed:
            continue
        pieces.append(text[cursor - node_start:])
        node.text = "".join(pieces)
        if node.tag == f"{{{_W_NS}}}t":
            node.set(_XML_SPACE, "preserve")


def _office_parts(archive: zipfile.ZipFile):
    for info in archive.infolist():
        name = info.filename
        if name.endswith(".xml") and name.startswith(("word/", "ppt/")):
            yield info


def _rewrite_office(content: bytes, rewrite) -> bytes:
    """Copy an Office zip, passing each text XML part through ``rewrite``."""
    try:
        source = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as error:
        raise DocumentShieldUnsupported(
            "Data shield could not open this Office file."
        ) from error

    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        text_parts = {info.filename for info in _office_parts(source)}
        for info in source.infolist():
            data = source.read(info)
            if info.filename in text_parts:
                root = etree.fromstring(data)
                if rewrite(root):
                    data = etree.tostring(
                        root,
                        xml_declaration=True,
                        encoding="UTF-8",
                        standalone=True,
                    )
            target.writestr(info, data)
    return output.getvalue()


def _mask_office(content: bytes, tokens: _Tokens) -> tuple[bytes, list[str]]:
    def rewrite(root) -> bool:
        changed = False
        for nodes in _paragraph_groups(root):
            text = "".join(node.text or "" for node in nodes)
            replacements = [
                (start, end, tokens.token_for(text[start:end], kind))
                for start, end, kind in data_shield.find_sensitive_spans(text)
            ]
            if replacements:
                _rewrite_group(nodes, replacements)
                changed = True
        return changed

    masked = _rewrite_office(content, rewrite)

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        image_count = sum(
            1
            for name in archive.namelist()
            if "/media/" in name
            and _extension(name) in {".png", ".jpg", ".jpeg", ".gif",
                                     ".bmp", ".tif", ".tiff", ".emf", ".wmf"}
        )
    warnings = []
    if image_count:
        warnings.append(
            f"This file contains {image_count} image(s). Text inside images "
            "can't be checked and is sent as it is."
        )
    return masked, warnings


# ----------------------------------------------------------- verification


def _extract_texts(extension: str, content: bytes) -> list[str]:
    if extension == ".pdf":
        texts = []
        with pymupdf.open(stream=content, filetype="pdf") as document:
            for page in document:
                texts.append(page.get_text())
                texts.extend(
                    str(widget.field_value or "")
                    for widget in page.widgets() or []
                )
            texts.extend(
                value for value in (document.metadata or {}).values()
                if isinstance(value, str)
            )
        return texts

    if extension in OFFICE_EXTENSIONS:
        texts = []
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                if not info.filename.endswith(".xml"):
                    continue
                root = etree.fromstring(archive.read(info))
                texts.extend(
                    "".join(node.text or "" for node in nodes)
                    for nodes in _paragraph_groups(root)
                )
                # Text outside paragraphs: chart values, document properties.
                texts.append(" ".join(root.itertext()))
        return texts

    return [_decode_text(content)]


def _verify_masked(extension, masked: bytes, shield) -> None:
    texts = _extract_texts(extension, masked)
    for text in texts:
        leftover = data_shield.find_sensitive_spans(text)
        if leftover or any(value in text for value in shield.values.values()):
            raise data_shield.DataShieldError(
                "Data shield could not hide every personal detail in this "
                "file, so it was not sent. Paste the text instead, or remove "
                "those details before uploading."
            )


# ---------------------------------------------------------------- restore


def restore_document(content: bytes, shield) -> bytes:
    """Put the real values back into DeepL's translated file."""
    if not shield.is_masked:
        return content

    if content.startswith(b"%PDF"):
        restored, found = _restore_pdf(content, shield)
    elif content.startswith(b"PK"):
        restored, found = _restore_office(content, shield)
    else:
        text = _decode_text(content)
        found = {
            _token_key(match)
            for match in _TOKEN_RE.finditer(text)
            if _token_key(match) in shield.values
        }
        restored = _TOKEN_RE.sub(
            lambda match: shield.values.get(_token_key(match), match.group()),
            text,
        ).encode("utf-8")

    missing = set(shield.values) - found
    if missing:
        raise data_shield.DataShieldError(
            f"{len(missing)} protected value(s) were lost during translation, "
            "so the document was not saved. Try again, or turn off Data "
            "shield for this file."
        )
    return restored


def _restore_pdf(content: bytes, shield) -> tuple[bytes, set[str]]:
    found: set[str] = set()
    with pymupdf.open(stream=content, filetype="pdf") as document:
        for page in document:
            replacements = []
            for token, value in shield.values.items():
                # Fall back to the bare code if DeepL dropped the brackets.
                rects = page.search_for(token) or page.search_for(token[1:-1])
                for rect in rects:
                    replacements.append((rect, value))
                    found.add(token)
            _overwrite_pdf_text(page, replacements)
        restored = document.tobytes(garbage=3, deflate=True)
    return restored, found


def _restore_office(content: bytes, shield) -> tuple[bytes, set[str]]:
    found: set[str] = set()

    def rewrite(root) -> bool:
        changed = False
        for nodes in _paragraph_groups(root):
            text = "".join(node.text or "" for node in nodes)
            replacements = []
            for match in _TOKEN_RE.finditer(text):
                token = _token_key(match)
                value = shield.values.get(token)
                if value is not None:
                    replacements.append((match.start(), match.end(), value))
                    found.add(token)
            if replacements:
                _rewrite_group(nodes, replacements)
                changed = True
        return changed

    return _rewrite_office(content, rewrite), found
