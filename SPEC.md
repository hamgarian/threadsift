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

- [ ] `test_threadsift.py` passes offline (id parsing, comment permalinks, media detection, filters,
      comment sort, per-command defaults).
- [ ] From a fresh clone with only the README's steps: `doctor` reports RSS and Arctic Shift ok.
- [ ] From a fresh clone, all 9 benchmark tasks succeed (search all Reddit, search a sub, read thread,
      top of week, user, gallery media, links for a URL, sub growth, comment permalink).
- [ ] No credentials are needed for any of the above.
- [ ] The default User-Agent identifies the tool; no browser impersonation.
- [ ] RSS is never called more than once per clock minute (pacing shared across processes).
- [ ] SKILL.md frontmatter has `name` + a `description` that says what it does and when to trigger;
      every path in it is relative to the skill folder.
- [ ] README: result first (benchmark table), quickstart, how it works, limits; every number traceable to `bench/`.
- [ ] Benchmark harness in `bench/` reproduces the comparison and contains no third-party code.
- [ ] LICENSE (MIT); no personal paths, names or secrets in any file.
