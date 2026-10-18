---
name: threadsift
description: Research Reddit without an API key - find relevant threads, read full comment trees with scores, search comments, check users, subreddit growth and where a link was discussed, and look at attached images and videos. Use whenever a question benefits from what Reddit users say ("what does Reddit think of X", "real-world experiences with Y", "community consensus on Z", "search r/sub for ...") or when given a reddit.com / redd.it link. Generic web fetch and search tools usually cannot reach reddit.com; use this instead.
---

# threadsift

`threadsift.py` lives in this skill's folder. It is Python 3.10+ standard library only and returns compact markdown
(`--format json` for raw data). Run it with any Python, or with `uv run --script` if there is no system Python:

```bash
python <skill-folder>/threadsift.py <command> [options]
```

## Why this stack (do not swap in scrapers)

- Anonymous `reddit.com/*.json` returns 403 and old.reddit redirects to login (measured Oct 2026).
  New official API keys need manual approval under Reddit's Responsible Builder Policy (since Nov 2025).
- **Arctic Shift** (free, keyless) has the full archive, captured new posts and comments 11-21 seconds after posting in one probe, and serves full
  comment trees, users and subreddit history.
- **Reddit's public RSS** is the only relevance-ranked discovery that works without a key. It allows exactly
  1 call per clock minute per IP; failed calls don't count. The script waits for the next minute and caches results
  for an hour, so put more into each call: `limit=100` and combined subs (`r/a+b+c`).
- If `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are set (an approved app), `thread`, `search --query` and `latest`
  use the official API automatically for live vote counts (untested by the author). `--backend arctic` forces Arctic.
- Do not use browser automation or stealth scrapers to get around Reddit's blocks.

## Workflow

1. **Discover** with `find`. It is relevance-ranked. Prefer 2-4 targeted queries over many broad ones, because each
   uncached call may wait up to a minute:
   ```bash
   threadsift.py find "secrets manager docker" --sub selfhosted --limit 15
   threadsift.py find "best budget mechanical keyboard" --sort top --time year
   ```
   The output is `id [score↑ comments💬] r/sub date: title [media: ...]`. Pick on-topic threads with many comments.
   Unsure which subreddits matter? Use `subs --query "<topic>"`.
2. **Read** the best 3-8 threads. Pass several in one call (URLs, share links, `redd.it/...`, or ids):
   ```bash
   threadsift.py thread 1x12pld 1ogtyds --max-comments 80 --min-score 2 --depth 4
   ```
   Comments are sorted by score at each level (`--sort new|old` for chronology), OP replies are marked `(OP)`,
   and `…N more replies` marks collapsed branches. A link to one comment shows only that comment and its replies.
   For long threads, keep `--max-comments` at 60-150 and `--body-chars` at 600-1200.
3. **Dig for specifics** with comment search. It returns newest first and needs `--sub` (comma-separate several),
   `--author` or `--link`:
   ```bash
   threadsift.py search --kind comments --sub selfhosted,homelab --query vaultwarden --after 2026-01-01 --limit 50
   threadsift.py search --kind comments --link 1ogtyds --query sops
   ```
4. **Synthesize.** Separate consensus from minority views, and weight by score and by how many independent users agree.
   Note the dates (advice goes stale) and cite permalinks `https://www.reddit.com/comments/<id>`.

## Media

- Listings and thread headers tag attached media: `[media: image | gif | video | gallery×N | external video |
  N inline image(s)]`. When a post's point is in the media, look at it instead of guessing from the title:
  `threadsift.py media <url|id>` downloads it and prints local paths. Videos and gifs become still frames
  (`--frames 6`, needs ffmpeg). Open the paths with your image-reading tool.
- `--comments` also fetches images posted in the comments.
- `--transcribe` transcribes a Reddit video's speech with local Whisper (`transcribe.py`, run via `uv`; the first run
  downloads the model, about 480 MB). Many clips are silent or removed; the script says so when there is no audio.
  Shouting and music come out as junk, so check the stated language and confidence.
- Media is cached in `~/.cache/threadsift/media/<id>/`, and folders older than 14 days are deleted automatically.

## Other commands

- `top <sub...> [--sort top|hot|new|rising|controversial] [--time day|week|...]` gives listings for several subs
  in ONE request (top 100 combined, split per sub). Use it for daily digests.
- `latest <sub>` lists the newest posts. `links <url | post>` shows where on Reddit a URL was posted, busiest first
  (prefix match; `--exact` turns that off).
- `user <name>` gives karma, the all-time most active subreddits, and recent posts and comments. Use it to check a commenter's credibility.
- `trend --sub S` (no keyword) shows subreddit growth: posts, comments and subscribers per day, week or month.
  `trend --sub S --query Q [--kind comments]` counts keyword activity over time and lists the top authors.
- `subs <prefix>` / `subs --query <topic>`, `rules <sub...>`, `wiki <sub> [--page P]`.
- `doctor` checks RSS quota, Arctic Shift, OAuth, ffmpeg and cache size. Run it first when something fails.
- Filters on listing commands (`find`, `top`, `latest`, `search`, `links`): `--min-comments`, `--min-score`,
  `--media any|none|image|gif|video|gallery`, `--no-nsfw`.

## Caveats

- Arctic Shift scores and comment counts are snapshots. Posts under ~2 days old often show `1↑ 0💬`,
  so judge them by reading them. The order from `top`/`find` is Reddit's own ranking and can be trusted.
- Arctic's search endpoints can shed load (HTTP 422). The script retries with backoff. Huge comment trees take 5-10s.
- Not possible: comment search across all of Reddit, and live vote counts without an approved app.
- Deleted or removed posts are often still in Arctic, because they were captured before removal.
- Be polite: run sequentially. For bulk analysis (whole subreddits, years), use the Arctic Shift data dumps instead of the API.
