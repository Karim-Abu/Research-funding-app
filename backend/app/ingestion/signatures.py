"""File-type detection + signature/container validation (security-critical).

Extension, magic-byte signature, and (for DOCX) container structure must agree.
Executables/scripts and implausibly-binary text are rejected.
"""
from __future__ import annotations

import io
import zipfile

from app.config.settings import get_settings

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
_EMPTY_ZIP = b"PK\x05\x06"  # empty archive end-of-central-directory
_EXECUTABLE_MAGICS = (
    b"MZ",            # PE/DOS
    b"\x7fELF",       # ELF
    b"\xfe\xed\xfa",  # Mach-O
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",  # Java/Mach-O fat
    b"#!",            # shebang script
)
_TEXT_BYTES = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D, 0x0C, 0x0B}


class UnsupportedFileError(Exception):
    """Maps to HTTP 415."""


def is_executable(data: bytes) -> bool:
    return any(data[:8].startswith(magic) for magic in _EXECUTABLE_MAGICS)


def looks_binary(data: bytes) -> bool:
    sample = data[:8192]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    printable = sum(1 for b in sample if b in _TEXT_BYTES)
    return (printable / len(sample)) < 0.85


def validate_docx_container(data: bytes) -> None:
    settings = get_settings()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UnsupportedFileError("not a valid DOCX container") from exc
    names = archive.namelist()
    if "[Content_Types].xml" not in names or not any(
        n.startswith("word/") for n in names
    ):
        raise UnsupportedFileError("not a DOCX container")
    if len(names) > settings.max_archive_entries:
        raise UnsupportedFileError("archive has too many entries")
    if sum(info.file_size for info in archive.infolist()) > settings.max_expanded_archive_bytes:
        raise UnsupportedFileError("archive expands beyond the configured limit")


def detect_source_type(filename: str, data: bytes) -> str:
    """Return 'pdf' | 'docx' | 'txt', or raise UnsupportedFileError (415)."""
    if is_executable(data):
        raise UnsupportedFileError("executable or script content is not allowed")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if data.startswith(PDF_MAGIC):
        if ext and ext != "pdf":
            raise UnsupportedFileError("extension does not match PDF signature")
        return "pdf"

    if data.startswith(ZIP_MAGIC) or data.startswith(_EMPTY_ZIP):
        validate_docx_container(data)
        if ext and ext != "docx":
            raise UnsupportedFileError("extension does not match DOCX signature")
        return "docx"

    if ext in ("txt", "md", "text", "") and not looks_binary(data):
        return "txt"

    raise UnsupportedFileError("unsupported or mismatched file type")
