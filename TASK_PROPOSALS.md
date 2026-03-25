# Codebase Issue Triage: Proposed Tasks

## 1) Typo/Data-quality task
**Task:** Fix the `CITY_TO_STATE` mapping typo/ambiguity around `charleston` by splitting into unambiguous keys (for example `charleston wv` and `charleston sc`) so one entry does not overwrite the other.

**Why:** Python dictionaries keep only the last duplicate key. The current map defines `charleston` twice, which silently drops the West Virginia mapping.

**Acceptance criteria:**
- `CITY_TO_STATE` has no duplicate semantic keys for city names that exist in multiple states.
- Region detection can represent both Charleston, WV and Charleston, SC through explicit patterns.

## 2) Bug-fix task
**Task:** Make state-abbreviation detection case-insensitive in `detect_regions`.

**Why:** `detect_regions` lowercases text into `text_lower`, but the abbreviation regex currently runs against the original `text` with uppercase state codes (`\bNY\b`, etc.). Lowercase article text (for example `ny`) will be missed.

**Acceptance criteria:**
- Regex matching for abbreviations works for `ny`, `Ny`, and `NY`.
- Add regression coverage for mixed/lowercase abbreviation inputs.

## 3) Comment/Documentation discrepancy task
**Task:** Reconcile LLM fallback documentation with implementation.

**Why:** The MCP README says the server "tries Ollama ... first, then falls back to Anthropic API," but current config/comments and `LLMClient` behavior are explicit opt-in for Anthropic with no automatic fallback.

**Acceptance criteria:**
- Update docs to match current behavior **or** implement true fallback in `LLMClient`.
- Quick Start / configuration docs and runtime behavior are aligned.

## 4) Test-improvement task
**Task:** Add focused unit tests for region detection and provider selection behavior.

**Why:** Core parsing and provider-selection paths are vulnerable to silent regressions and currently lack tests.

**Suggested tests:**
- `detect_regions` handles duplicate-city scenarios and case-insensitive abbreviations.
- `LLMClient` provider detection errors are deterministic when Ollama is unavailable and `LLM_PROVIDER` is unset.
- `LLMClient` selects Anthropic only when `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` is present.

**Acceptance criteria:**
- New tests run in CI/local without network calls (mock `httpx.get` and env vars).
- At least one regression test fails on current main and passes with the fix.
