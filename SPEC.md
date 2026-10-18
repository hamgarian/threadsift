# threadsift spec

## Goal

Let an AI agent (or a person at a terminal) research Reddit without an API key: find the right threads,
read them in full with scores, and look at what's attached. The output should be compact enough for an LLM's context.

## Inputs and outputs

- Input: CLI commands (`find`, `top`, `thread`, `search`, `latest`, `links`, `user`, `trend`, `subs`, `media`,
  `rules`, `wiki`, `doctor`) with filters. Optional `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`.
- Output: compact markdown by default, `--format json` for raw data. Downloaded media goes to a cache folder.
- Data sources: Reddit's public RSS (discovery and ranking only, 1 call per clock minute, honest User-Agent)
  and the Arctic Shift API (posts, comment trees, users, history). No scraping, no browser, no proxies.
- Runtime: Python ≥3.10 standard library only. Optional: ffmpeg (video frames, audio),
  faster-whisper via `uv` (transcription).

## Acceptance checklist

Each item names the evidence that checks it.

- [x] `test_threadsift.py` passes offline (id parsing, comment permalinks, media detection, filters,
      comment sort, per-command defaults). Evidence: `python test_threadsift.py` prints `ok`.
- [x] From a fresh clone with only the README's steps: `doctor` reports RSS and Arctic Shift ok.
      Evidence: `bench/clean-clone-2026-10-18.log` (re-run against the published repo at release).
- [x] From a fresh clone, all 9 benchmark tasks succeed. Evidence: `bench/clean-clone-2026-10-18.log`.
- [x] No credentials are needed for any of the above. Evidence: same log; `doctor` shows OAuth not configured.
- [x] The default User-Agent identifies the tool; no browser impersonation. Evidence: test asserts it, and the
      clean-clone run used it.
- [x] RSS is called at most once per clock minute, with pacing shared across processes. Evidence: a test with a fake clock
      checks that a second call from a "new process" (stamp file only) lands in the next minute.
- [x] SKILL.md frontmatter has `name` and a `description` that says what it does and when to trigger;
      every path in it is relative to the skill folder.
- [x] README: result first (benchmark table), quickstart, how it works, limits. Each number traces to `bench/`
      (`scores-2026-10-18.md`, `probe-2026-10-18.log`, `transcribe-check-2026-10-18.log`, `competitor-errors-2026-10-18.log`).
- [x] Benchmark harness in `bench/` reproduces the comparison and contains no third-party code (Hermes's script is
      downloaded at a pinned commit when the harness runs).
- [x] LICENSE (MIT); no secrets or personal paths. The repo owner's GitHub handle appears where a link needs it.
