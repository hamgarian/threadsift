---
title: "Reading Reddit without an API key in 2026: what still works, measured"
tags: reddit, python, ai, agents
---

I wanted my AI agent to research Reddit: find the threads, read the actual comments, and say what people agree on.
It turned out to be harder than it sounds in 2026, so I measured what still works and built a small tool around it.

## What's closed

- `reddit.com/anything.json` without a login: **403**. `old.reddit.com` redirects to a login page.
- New Reddit API apps: since November 2025 they need approval under Reddit's Responsible Builder Policy. You can't
  just create a key anymore.
- Generic web fetch tools in AI agents usually can't reach reddit.com at all.

## What still works

1. **Reddit's public RSS feeds**: search, top, hot and so on. The limit is exactly **one request per clock minute per IP**.
   I watched the `x-ratelimit-reset` header count down to the minute boundary, and blocked requests don't use up the
   allowance. One request can carry a lot, though: `limit=100`, and many subreddits at once (`r/a+b+c`). The
   catch is that RSS has no scores and only top-level comments.
2. **[Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift)**: a free, independent archive of Reddit run by one
   person. It isn't just history. The newest post and comment I checked had been captured 21 and 11 seconds after
   posting. It has full comment trees, scores, users, per-subreddit growth over time, and "which posts link this URL".

The trick is to combine them: RSS for *which* threads (Reddit's own relevance and ranking), then one batched Arctic Shift
call for *what's in them* (scores, comment counts, the nested replies).

## The tool: threadsift

`threadsift` is one standard-library Python file plus a `SKILL.md`, so Claude Code (or any agent that loads skills) knows
when and how to use it:

```bash
python threadsift.py find "secrets manager docker" --sub selfhosted
python threadsift.py thread 1ogtyds --max-comments 60
python threadsift.py links https://github.com/some/repo      # where was this discussed?
python threadsift.py trend --sub hermesagent                 # is this community growing?
python threadsift.py media <post> --transcribe               # what's in the video?
```

## How it compares

I ran the same 9 tasks, with no credentials, against every keyless Reddit tool I could find that actually runs:

| | passed | scores in output |
|---|---|---|
| threadsift | 9/9 | yes |
| Hermes Agent `reddit-reading` | 6/9 | no |
| arctic-shift-mcp | 2/9 | yes |
| reddit-mcp-buddy (no key) | 1/9 | no |
| reddit-no-auth-mcp-server | 0/9 | — |

Fair warnings: I picked the tasks, and four of them test features I built in on purpose. It's one run from one machine.
Hermes's skill is well made and honest about its limits; it simply doesn't use the archive. Everything (harness, pass
rules, raw outputs, the probe that measured the limits) is in the repo's `bench/` folder.

## Please be nice to Arctic Shift

It's a free service run by one person. threadsift paces itself, caches results for an hour, and retries politely, but if you
want years of data, use the Arctic Shift data dumps rather than the API.

Repo: https://github.com/hamgarian/threadsift (MIT)
