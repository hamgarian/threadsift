# Launch drafts. Do not post automatically; review and post by hand.

## Show HN

Title: Show HN: threadsift – research Reddit without an API key (scores, full threads, media)

Reddit closed anonymous .json access and new API keys now need approval, so most "no key" Reddit tools broke.
I measured what still works: public RSS (exactly 1 request per clock minute per IP) and the Arctic Shift archive
(it captured new posts in about 10-20 seconds when I probed). threadsift combines them: RSS for Reddit's own ranking, then one batched
archive call for scores and nested comments. It's one stdlib Python file plus a SKILL.md for AI agents.

On 9 tasks without credentials it passed 9/9; the closest alternative passed 6/9 (no scores). I picked the tasks, so the
harness, pass rules and raw outputs are in bench/ if you want to check or rerun them.

https://github.com/hamgarian/threadsift

## X / Bluesky (one post)

Reddit's anonymous .json is dead (403) and new API keys need approval. What still works: RSS at 1 request per minute,
plus the Arctic Shift archive. I built threadsift to combine them for AI agents: scores, full comment trees, users,
subreddit growth, media. 9/9 vs 6/9 for the closest tool. MIT: https://github.com/hamgarian/threadsift

## Reddit (r/ClaudeAI or r/LocalLLaMA; check each sub's self-promotion rules first)

Title: I measured what still works for reading Reddit without an API key, and made a skill for it

Body: what's closed (.json 403, API approvals), what works (RSS 1 request per minute, Arctic Shift archive), how threadsift
combines them, the 9-task comparison table with its caveats (I chose the tasks; one run on one machine), and a link to bench/.
Ask for feedback on which tasks to add.
