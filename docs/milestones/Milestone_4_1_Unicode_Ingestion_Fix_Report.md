# Milestone 4.1 (M5a) — Unicode / Non-ASCII Text Ingestion Fix — Final Report

**Branch:** `fix/unicode-text-ingestion` (off tag **`milestone-4-requirements-rules`** @ M4 commit
`404a0d1`). **Date:** 2026-06-23. **Status:** ✅ Complete. **Not committed** (only the
`milestone-4-requirements-rules` tag + branch were created).

A small, deterministic, self-contained fix: pasted/uploaded **non-ASCII text** (German umlauts, ß, French
accents, German quotation marks/apostrophes) was misclassified as binary and the source ended up
`failed`. M4 testing had to use ASCII-only source text because of it. This milestone fixes the defect
permanently and adds a thorough regression suite. `processing_mode` stays `deterministic_only`; no new
feature surface.

## Scope (per user decisions during planning)
- **This milestone (4.1):** only the Unicode ingestion fix + regression tests.
- **Next milestone (after 4.1, NOT deferred to M9):** deterministic Evidence — `EvidenceCandidate`,
  `EvidenceAnchor`, `EvidenceLink` and deterministic **exact-quote verification**, implemented **without
  any LLM**.
- **Deferred to Milestone 9:** A1 profiles, ModelGateway, anthropic_direct/openai_direct adapters,
  fake/real providers, CostGuard, AgentInvocation/ToolInvocation, cloud_assisted enablement and any cloud
  toggle. `validate_processing_mode` is left rejecting `cloud_assisted` (unchanged).

## Root cause
`backend/app/ingestion/signatures.py::looks_binary` judged "binary" on **raw bytes** against an ASCII-only
allow-set `_TEXT_BYTES = set(range(0x20,0x7F)) | {whitespace}`. Valid UTF-8 multibyte characters use high
bytes that are not in that set (`ü` → `0xC3 0xBC`, `ß` → `0xC3 0x9F`, `„` → `0xE2 0x80 0x9E`). For short
non-ASCII text the printable-byte ratio dropped below the `0.85` threshold, so the content was flagged
binary. This broke two paths:
- `parse_txt` → `ParserError` → source **`failed`** (the observed text-source symptom).
- `detect_source_type` (`ext in txt/md/text and not looks_binary`) → umlaut `.txt` uploads rejected with
  **415**.

The normalizer was **not** at fault — `normalize_text` uses **NFKC**, which preserves umlauts/ß/accents
and German quotes and composes NFD input to NFC.

## Fix
Rewrote `looks_binary` to be **Unicode-aware** (single function; the `_TEXT_BYTES` set was removed):
1. Empty → not binary; a NUL byte in the 8192-byte sample → binary (unchanged guard).
2. Try `sample.decode("utf-8")` (strict).
   - **Success** → decide on the decoded text.
   - **`UnicodeDecodeError`** with `reason == "unexpected end of data"` (a multibyte sequence cut by the
     sample boundary) → decode the **valid prefix** `sample[:exc.start]` and decide on that. Genuine
     mid-stream corruption (`invalid start byte` / `invalid continuation byte`) does **not** take this
     branch.
   - Otherwise → try **Windows-1252** (`sample.decode("cp1252")`, strict; cp1252's 5 undefined bytes
     raise → binary). This replaces the old ASCII byte-ratio fallback so plausible cp1252 text (e.g.
     Windows-saved umlauts) is accepted — consistent with `parse_txt`'s existing cp1252 fallback.
3. **Unicode-aware control check** (shared): over the *decoded text*, count code points `< 0x20`
   (excluding `\t \n \r \f \v`) plus `0x7F`; ratio `> 0.15` → binary. High letters (é, ü, „) count as
   printable, not "non-text".

Security guarantees preserved: NUL → binary; control-heavy / non-decodable binary → binary; executables
and magic-byte/container checks (`is_executable`, PDF/ZIP/DOCX) are untouched.

## Changed files
- **`backend/app/ingestion/signatures.py`** — Unicode-aware `looks_binary` + `_control_ratio_too_high`
  helper; replaced `_TEXT_BYTES` with `_ALLOWED_CONTROL_CHARS` + `_MAX_CONTROL_RATIO`.
- **`backend/tests/test_unicode_ingestion.py`** (new) — 14 regression tests.
- **`backend/tests/test_requirements_flow.py`** — M4 flow-test source text switched from the ASCII
  workaround to umlaut text (`"Quelle für die Prüfung der Förderfähigkeit."`), proving the end-to-end
  path; M4 assertions unchanged.
- **`e2e/source-ingestion.spec.ts`** — added "umlaut text source ingests and displays after refresh".

No migration; no contract files modified; no frontend source changes (React renders UTF-8 natively).

## Tests covered (regression)
- `looks_binary` **False** for UTF-8 German (`ä ö ü Ä Ö Ü ß`), French (`é è à ç`), German quotes/
  apostrophes (`„ " ‚ ' » «`), short + long; and for plausible **cp1252** umlaut bytes.
- `looks_binary` still **True** for NUL, control-heavy bytes, and a real binary blob; `is_executable` /
  magic detection unaffected.
- **Composed vs decomposed** (NFC `ä` vs NFD `a`+U+0308) — both accepted; NFD input is re-composed to NFC
  in `normalized_text`, no leftover combining mark.
- **Sample-boundary multibyte** — a 2-byte char straddling the 8192-byte sample boundary is tolerated;
  an invalid + control-heavy blob is still binary.
- **Text source** with umlauts → **201 + `processed`** (the previously failing case); **`.txt` upload**
  with umlauts → processed (not 415).
- **Round-trip exactness + stable hashes** — `normalized_text` and `SourceFragment`s preserve the exact
  characters; `original_content_hash` / `normalized_content_hash` are deterministic (identical across two
  ingests) 64-hex SHA-256.

## Test results
| Suite | Result |
|---|---|
| Backend `python -m pytest` | ✅ **95 passed** (81 M1–M4 + **14 new Unicode**) |
| Frontend `pnpm test` (vitest) | ✅ **41 passed** (unchanged) |
| `pnpm exec tsc --noEmit` / `pnpm lint` / `pnpm build` | ✅ exit 0 |
| `pnpm exec playwright test` | ✅ **4 passed** (3 existing + **umlaut round-trip**) |

## Manual check
Pasting `„Müller & Söhne prüfen Förderfähigkeit."` as a text source now yields `processed` with the
content preserved exactly (previously `failed`).

## Known limitations
- The cp1252 path is a best-effort acceptance of plausible Windows-1252 text; it intentionally relies on
  the control-character ratio (not a charset detector) to reject binary. NUL bytes and control-heavy
  content remain rejected.
- Source ingestion is unchanged otherwise (no OCR, no new formats).

## Readiness
Ingestion now **preserves Unicode end to end** (bytes → DB → BFF → UI), unblocking the upcoming
**deterministic Evidence milestone** (EvidenceCandidate / EvidenceAnchor / EvidenceLink + exact-quote
verification, no LLM): exact-quote verification depends on the frozen `normalized_text` containing the
real (umlaut-correct) characters, which it now does. **No implementation was auto-committed** (only the
STEP-0 tag + branch).
