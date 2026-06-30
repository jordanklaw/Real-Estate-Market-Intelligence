# Decision Log

A record of the human judgment calls that shaped this project — reconstructed from git
history, the README's revision trail, `LINUX_SETUP.md`, and `TASK_PROPOSALS.md`. The intent
is to capture the *why* and the tradeoffs behind decisions, not just the *what* in the diffs.

Each entry is flagged:

- **Harder / non-default path** — a deliberately steeper or unconventional route.
- **Mixed** — partly a real judgment call, partly routine.
- **Routine** — normal implementation, bug fix, or doc truing-up.

**Meta-decision (the thread behind several entries):** a comment introduced in #1 calls this
a *"Multi-provider pattern for portfolio demo."* Decisions #1, #3, #5, #7, and #11 only fully
make sense as *"make a private work project safe to publish."* That intent is the backdrop.

---

## 1. Remove Anthropic API as the default LLM fallback — Ollama-only, fail loud
- **Commit:** `d105b62` — 2026-03-25 (orig. PR #3; re-affirmed in `cedb232` / PR #18)
- **Flag:** Harder / non-default path
- **What changed:** `LLMClient` was rewritten so that, with no Ollama running, it **raises
  `RuntimeError`** instead of silently falling back to the Anthropic API. The "auto" provider
  mode and the auto-detect-then-fallback logic were deleted. Anthropic is now reachable
  **only** via explicit `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`, behind a lazy import.
  The `anthropic` dependency and `ANTHROPIC_MODEL` constant were removed; `OLLAMA_MODEL`
  default bumped `qwen2.5:7b → qwen3:14b`.
- **Why:** Local-first / privacy conviction — no external API keys required for core
  functionality, no silent data egress to a paid cloud API, deterministic failure over a
  hidden cloud call. Working fallback code was deleted to get there.

## 2. Replace the web scraper with an anti-blocking escalation strategy (rewrite of working code)
- **Commit:** `1bfb539` — 2026-03-27 (PR #20); selector follow-up `e3ac8ec` same day
- **Flag:** Harder / non-default path
- **What changed:** A ~491-line rewrite of `web_scraper.py`. `scrape_news_sources()` →
  `scrape_all_sources()` returning structured `ScrapeResult` objects (per-source
  success/failure). New escalation ladder: `httpx` + session cookies → **`curl_cffi` TLS
  fingerprint impersonation** → graceful degradation. Added 2–8s randomized request spacing,
  a fallback CSS-selector chain, and a CPE source migration (`cpexecutive.com` →
  `commercialsearch.com/news/`). Also fixed a markdown→HTML bold bug.
- **Why:** The two news sources began returning `403` to automated requests. Rather than drop
  the source or pay for a scraping API, the author chose to impersonate a real browser's TLS
  fingerprint and pace requests to evade bot detection — and took a return-type (architecture)
  change along the way.

## 3. De-brand from "Yardi" and rename the project to "Real Estate Market Intelligence"
- **Commits:** `1cb89e7` (rename `yardi_resources.json` → `product marketing_resources.json`),
  `7c987f7` / `901d2de` / `7d37826` (README name + description revisions) — all 2026-03-25
- **Flag:** Harder / non-default path (executed partially)
- **What changed:** Public-facing "Yardi" branding was genericized and the title became
  "Real Estate Market Intelligence." The de-brand is presentation-layer only: the package
  directory is still `sales_prospector_mcp`, and tool docstrings/data still reference Yardi
  products (Breeze, Voyager).
- **Why:** Make a real work/employer project safe to share publicly (portfolio) without
  foregrounding the specific vendor.

## 4. Territory hard-exclusions (IL, MN, MI, WI) enforced at the data layer, from inception
- **Commit:** `07f7a13` — 2026-03-25 (initial build)
- **Flag:** Harder / non-default path (architecturally)
- **What changed:** `EXCLUDED_STATES = {"IL","MN","MI","WI"}` with the comment
  *"Hard exclusions - never surface these states in any tool."* The rule is enforced across
  all six tools as an unconditional invariant, not as a per-call filter option.
- **Why:** Those states are out of the rep's territory; the author wanted them structurally
  impossible to surface rather than filterable-but-default-on.

## 5. Downsize default model in docs: Qwen3 14B → 1.7B (unresolved tradeoff)
- **Commit:** `0f6b65b` — 2026-04-17 (README only)
- **Flag:** Mixed
- **What changed:** README default model went `qwen3:14b → qwen3:1.7b`; the RAM figure became
  a literal `(x)GB` placeholder and "runs comfortably" softened to "runs at tolerable speed."
- **Drift to note:** `config.py` still defaults `OLLAMA_MODEL` to `qwen3:14b`, and
  `LINUX_SETUP.md` still says pull `qwen3:14b`, so README and code disagree.
- **Why:** Real hardware (the 11GB, CPU-only IdeaPad — see #6) can't run 14B comfortably, so
  the recommended default was cut to fit. The `(x)` placeholder + "tolerable" wording shows
  this was an in-progress, not-yet-measured decision that was never fully propagated.

## 6. Raise Ollama timeout 120s → 600s for low-RAM, CPU-only hardware
- **Commit:** part of `3e266dc` / PR #19 — 2026-03-27
- **Flag:** Mixed
- **What changed:** Inference timeout 5×'d.
- **Why:** The IdeaPad has 11GB RAM and CPU-only inference, so `qwen3:4b` exceeds the 2-minute
  timeout on longer generations (e.g. daily-brief talking points). The author chose to tolerate
  slow local generation rather than force a smaller/worse model or require a GPU — consistent
  with the local-first stance in #1.

## 7. Move the hardcoded recipient email into `.env` with a graceful no-send fallback
- **Commit:** `cf03bda` — 2026-03-25 (PR #5; re-affirmed in #18)
- **Flag:** Routine (in service of the public-demo intent)
- **What changed:** `DAILY_BRIEF_RECIPIENT` moved from a hardcoded address to an env var;
  sending is skipped with a clear message when unset; the personal email was removed from a
  docstring; `briefs/` was added to `.gitignore`.
- **Why:** Remove PII before publishing; make the project shareable/reusable.

## 8. Ambiguous-city region detection: dict → ordered list, run disambiguation first
- **Commit:** `6f8d809` — 2026-03-25 (PR #9); case-insensitivity follow-up in `7f5d915` / PR #10
- **Flag:** Routine (with a deliberate data-model choice)
- **What changed:** `CITY_STATE_PATTERNS` converted from a `dict` to a list of
  `(pattern, state)` tuples, and the explicit disambiguation patterns (e.g. "Charleston, WV"
  vs "Charleston, SC") are now checked *before* the generic city→state map. Regex loosened to
  a proximity match.
- **Why:** Python dicts silently drop duplicate keys, so `charleston` defined twice was
  dropping the WV mapping. The dict→list change preserves both and imposes priority ordering.
  (Pre-identified as a tradeoff in `TASK_PROPOSALS.md`, items #1–2.)

## 9. CSS selectors corrected by live HTML inspection (`.post` over `article`, `h3 a` over `h2 a`)
- **Commit:** `e3ac8ec` — 2026-03-27
- **Flag:** Routine (evidence-based)
- **What changed:** Article selectors changed after inspecting live HTML: `article` matched
  only 1 hero element per site, whereas `.post` matched 13 (MHN) / 9 (CPE) real news items;
  titles use `h3 a`, not `h2 a`.
- **Why:** Empirical correction grounded in observed counts rather than assumed page structure.

## 10. Google Drive API dropped from scope (never built)
- **Commit:** `901d2de` — 2026-03-25 (README stack line)
- **Flag:** Routine (scope-down / doc truing)
- **What changed:** "Google Drive API" removed from the tech-stack list. No Drive code ever
  existed — it was an aspirational dependency in the README only.
- **Why:** A planned integration deferred/abandoned; README trued-up to reality.

## 11. Reposition as vendor-neutral / model-agnostic; demote Claude Desktop to "reference example"
- **Commits:** `901d2de` — 2026-03-25 (broadened client list, "build once, works everywhere");
  `b177e85` — 2026-06-24 (removed the Windsurf reference)
- **Flag:** Routine (presentation/positioning)
- **What changed:** README shifted from a Claude-Desktop-centric framing to "any
  MCP-compatible client" (ChatGPT, Gemini, Copilot, Cursor, Goose, custom SDKs), with Claude
  Desktop kept only as a config example. Later, Windsurf was dropped from the client list.
- **Why:** Present the work as portable/standards-based rather than tied to one vendor; the
  2026-06 edit is light maintenance of that client list.

---

## Summary

| # | Decision | Flag |
|---|----------|------|
| 1 | Ollama-only, remove Anthropic fallback, fail loud | Harder / non-default |
| 2 | Anti-blocking scraper rewrite (curl_cffi impersonation) | Harder / non-default |
| 3 | De-brand Yardi → "Real Estate Market Intelligence" | Harder / non-default (partial) |
| 4 | Territory hard-exclusions baked into the data layer | Harder / non-default |
| 5 | Default model downsized 14B → 1.7B in docs | Mixed |
| 6 | Ollama timeout 120s → 600s for low-RAM hardware | Mixed |
| 7 | Hardcoded email → `.env` + graceful no-send | Routine |
| 8 | Ambiguous-city detection: dict → ordered list | Routine |
| 9 | CSS selectors corrected by live HTML inspection | Routine |
| 10 | Google Drive API dropped from scope | Routine |
| 11 | Reposition as vendor-neutral / model-agnostic | Routine |

## Open loose ends

- **Three+ files disagree on the default model:** README says `qwen3:1.7b`, `config.py`
  defaults to `qwen3:14b`, `LINUX_SETUP.md` says pull `qwen3:14b`, and PR #19's commit message
  references `qwen3:4b`. Decision #5 was never fully propagated.
- **The de-brand (#3) is partial** — the package dir `sales_prospector_mcp`, the Yardi product
  data, and tool docstrings still reveal the origin.
- **`TASK_PROPOSALS.md` is itself a decision artifact** — a triage doc that names tradeoffs and
  acceptance criteria; its items #1–3 directly motivated decisions #8 and #1.
