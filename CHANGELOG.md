# Changelog

## 0.1.0 (2026-10-18)

First release.

- `find`, `top` (top/hot/new/rising/controversial), `latest`, `search` (posts, and comments across several subs), `thread`
  (nested comments with scores; comment permalinks open just that sub-thread), `links`, `user`, `trend` (subreddit
  growth or keyword activity), `subs`, `rules`, `wiki`, `media` (images, galleries, comment images, video frames,
  best-effort transcription) and `doctor`.
- Shared listing filters: `--min-score`, `--min-comments`, `--media`, `--no-nsfw`.
- No API key. Uses Reddit's public RSS (1 call per clock minute, paced across processes) plus the Arctic Shift archive,
  and the official API when `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are set.
- Benchmark against four keyless alternatives in `bench/` (9/9 tasks; the closest alternative passed 6/9).
