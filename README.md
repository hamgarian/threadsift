<p align="center"><img src="assets/social-preview.png" width="640" alt="threadsift: research Reddit without an API key"></p>

<h1 align="center"><img src="assets/logo.svg" width="32" alt=""> threadsift</h1>

<p align="center">
  <b>Ask Reddit questions without an API key.</b><br>
  Find the right threads, read every comment with its score, and see what people actually agree on,<br>
  from your terminal or from an AI agent like Claude Code.
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#use-it">Use it</a> ·
  <a href="#use-it-from-an-ai-agent">AI agents</a> ·
  <a href="#how-it-compares">How it compares</a> ·
  <a href="#how-it-works">How it works</a>
</p>

---

## What is threadsift?

Reddit is where people tell you what actually happened: which tool broke, which setup worked, what they'd buy again.
Getting at it programmatically has become hard. Anonymous `.json` access now returns 403, new API keys need Reddit's
approval, and most "no key" Reddit tools quietly stopped working in 2026.

**threadsift is a single Python file that still gets you real Reddit data, with no key, no login and no browser.**
It asks Reddit's public feeds which threads matter, then pulls the full threads, scores and history from the
[Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) archive. It also ships as an agent skill, so Claude Code
(or any agent that loads `SKILL.md` folders) can research Reddit for you and cite what it found.

## What it does

- 🔎 **Finds the threads that matter.** Reddit's own relevance search and rankings, with scores and comment counts.
- 💬 **Reads whole conversations.** Nested comments with scores, the original poster marked, and comment links open just that sub-thread.
- 🧭 **Searches inside communities.** Find every comment mentioning X across several subreddits.
- 🔗 **Traces a link.** Where on Reddit was this article, repo or video discussed?
- 👤 **Checks people.** Karma, all-time active subreddits and recent posts, to spot experts and shills.
- 📈 **Shows trends.** Is a subreddit growing? Is a topic getting more attention, and who's driving it?
- 🖼️ **Looks at the media.** Downloads images and galleries, turns videos into still frames, and transcribes speech with local Whisper.
- 🤖 **Fits LLM context.** Compact markdown by default, `--format json` when you want raw data.

## Install

**Requirements:** Python 3.10 or newer. That's it; threadsift uses only the standard library.

```bash
git clone https://github.com/hamgarian/threadsift
cd threadsift
python threadsift.py doctor        # checks Reddit's feeds and the archive are reachable
```

Optional extras:
- [ffmpeg](https://ffmpeg.org) to turn videos into still frames.
- [uv](https://docs.astral.sh/uv/) for `--transcribe`. It installs Whisper on first use; the model is about 480 MB.

## Use it

**1. Find threads about your question**

```bash
python threadsift.py find "secrets manager docker" --sub selfhosted
```
```
- 1s2f17m [370↑ 91💬] r/selfhosted 2026-03-24: Komodo 🦎 Container manager 🦎 v2: Docker Swarm
- 1thrv82 [93↑ 60💬] r/selfhosted 2026-05-19: [ Removed by moderator ]
- 1vuaqh5 [783↑ 204💬] r/selfhosted 2026-08-21: Put Self Hosting on Your CV
- 1ogtyds [60↑ 30💬] r/selfhosted 2025-10-26: Managing Secrets and Credentials in Docker: Best Practices
```

**2. Read the ones that look useful**

```bash
python threadsift.py thread 1ogtyds --max-comments 60
```
```
# Managing Secrets and Credentials in Docker: Best Practices
r/selfhosted · u/SudoMason · 2025-10-26 · score 60 · 30 comments · https://www.reddit.com/r/selfhosted/comments/1ogtyds/...

## Comments

- [41] u/LGX550: I opted for Infisical (self hosted) ...
  - [6] u/SudoMason (OP): Hey, that seems pretty cool. Can you link me to this service?
    - [3] u/xaijian: Try SOPS/age. Integrates nicely if you use terragrunt.
```

**3. Go deeper as needed**

```bash
python threadsift.py search --kind comments --sub selfhosted,homelab --query vaultwarden   # who mentions it?
python threadsift.py top ClaudeAI LocalLLaMA --time day                                   # today's top posts
python threadsift.py links https://github.com/NousResearch/hermes-agent                   # where was it posted?
python threadsift.py user spez                                                            # who is this?
python threadsift.py trend --sub hermesagent                                              # is it growing?
python threadsift.py media 1x8lalp --transcribe                                           # what's in the post's media?
```

<details>
<summary><b>All commands</b></summary>

| Command | What it answers |
|---|---|
| `find "<query>" [--sub S]` | Which threads are about this? Relevance-ranked, with scores and comment counts |
| `thread <url\|id> ...` | What did people say? Nested comments with scores; a comment link shows just that sub-thread |
| `search --kind comments --sub a,b --query Q` | Who mentioned X in these communities? |
| `top <subs...> [--sort hot\|new\|rising\|controversial]` | What matters today here? All subreddits in one request |
| `latest <sub>` | What's new in this subreddit? |
| `links <url>` | Where on Reddit was this article, repo or video discussed? |
| `user <name>` | Is this commenter credible? |
| `trend --sub S [--query Q]` | Is this community or topic growing? Who drives it? |
| `media <url\|id> [--comments] [--transcribe]` | What's in the image, gallery or video? |
| `subs [prefix] [--query topic]`, `rules`, `wiki` | Which communities exist, and what are their rules and FAQs? |
| `doctor` | Is everything reachable right now? |

Every listing takes `--min-comments`, `--min-score`, `--media any|none|image|gif|video|gallery` and `--no-nsfw`.
Add `--format json` to any command for raw data. Run `python threadsift.py <command> --help` for every option.
</details>

> Commands that ask Reddit itself (`find`, `top`, `doctor`) can pause for up to a minute. Reddit allows one feed request
> per minute per IP, and threadsift waits its turn instead of getting blocked. Everything else answers in seconds,
> and results are cached for an hour.

## Use it from an AI agent

threadsift is also a ready-made [agent skill](SKILL.md). For Claude Code, clone it into your skills folder:

```bash
git clone https://github.com/hamgarian/threadsift ~/.claude/skills/threadsift
```

Then just ask:

> *"What does Reddit think of Bitwarden Secrets Manager for a homelab?"*
> *"Find real-world experiences with running Qwen locally on a 6 GB GPU."*
> *"Summarize this thread and tell me if the top answer is right: https://www.reddit.com/r/..."*

The skill tells the agent which commands to run, how to stay inside the rate limit, when to look at an image or video
instead of guessing from the title, and to cite permalinks. Other agents that load `SKILL.md` folders work the same way.

## How it compares

The same 9 research tasks, run without credentials against every keyless Reddit tool I could find that runs:

| | Passed | Scores in results | Nested comments | Media |
|---|---|---|---|---|
| **threadsift** | **9/9** | ✅ | ✅ | ✅ |
| Hermes Agent `reddit-reading` | 6/9 | ❌ | ❌ | ❌ |
| arctic-shift-mcp | 2/9 | ✅ | ✅ | ❌ |
| reddit-mcp-buddy (no key) | 1/9 | ❌ | ❌ | ❌ |
| reddit-no-auth-mcp-server | 0/9 | — | — | — |

<details>
<summary><b>Per-task results, method and caveats</b></summary>

| Task | **threadsift** | Hermes `reddit-reading` | arctic-shift-mcp | reddit-mcp-buddy | reddit-no-auth-mcp-server |
|---|---|---|---|---|---|
| Search all of Reddit | ✅ 10 results, all with scores | ✅ 10, no scores | ❌ needs a subreddit | ❌ forbidden | ❌ |
| Search one subreddit | ✅ 10, all with scores | ✅ 10, no scores | ❌ archive timeout ×2 | ❌ | ❌ |
| Read a thread | ✅ 43 comments, nested, scores | ✅ 37, flat, no scores | ✅ 43, scores | ❌ | ❌ |
| Top posts of the week | ✅ matches Reddit's ranking, scores | ✅ matches, no scores | ❌ returned newest, not top | ✅ matches, no scores | ❌ |
| User activity | ✅ 20 items + karma + all-time subs | ✅ 10, no scores | ✅ 10 posts | ❌ | ❌ |
| Get a gallery's 4 images | ✅ 4 downloaded | ❌ | ❌ | ❌ | ❌ |
| Where a GitHub repo was posted | ✅ 9 posts | ✅ 8 posts | — | ❌ | ❌ |
| Subreddit growth by month | ✅ 8 months | — | — | — | — |
| Open a link to one comment | ✅ that sub-thread only | ❌ whole thread | ❌ whole thread | ❌ | ❌ |

- Run on 2026-10-18, one machine, no credentials, identical inputs. Competitor tasks that failed were retried once after a
  90-second pause (threadsift had no failures). The tools share one IP's Reddit allowance, so they ran one at a time.
- I picked the tasks, and the last four test features threadsift was built to have. Read those rows as "can it do this
  at all". The first five are plain research tasks every tool claims to handle.
- Hermes and reddit-mcp-buddy say in their READMEs that they get scores and deeper threads with an approved Reddit app.
  I didn't test that.
- Versions: Hermes reddit-reading @ d76cce4, arctic-shift-mcp 1.0.2, reddit-mcp-buddy 1.1.14, reddit-no-auth-mcp-server
  from PyPI on the same day. reddit-no-auth-mcp-server crashed on install as its README describes, then failed every call. Hermes's
  script crashed on Windows printing emoji until UTF-8 output was forced; that isn't counted against it
  ([error log](bench/competitor-errors-2026-10-18.log)).
- Pass rules: [`bench/summarize.py`](bench/summarize.py). Scores as computed: [`bench/scores-2026-10-18.md`](bench/scores-2026-10-18.md).
  Raw outputs aren't published because they contain other people's Reddit posts; [`bench/run.sh`](bench/run.sh) regenerates them.
</details>

## How it works

Since Reddit's 2025-2026 lockdown, anonymous `reddit.com/*.json` returns 403, old.reddit redirects to a login page
([probe log](bench/probe-2026-10-18.log)), and new API apps need approval under Reddit's
[Responsible Builder Policy](https://www.reddit.com/r/redditdev/comments/1oug31u/). Two keyless paths still work, and
threadsift combines them:

1. **Reddit's public RSS feeds decide *which* threads.** You get Reddit's own relevance search and rankings. The limit is
   exactly **one request per clock minute per IP** (blocked requests don't count against it), so threadsift waits for the
   next minute, even across separate processes, and packs each call: up to 100 results, many subreddits at once.
2. **The Arctic Shift archive says *what's in them*.** It's a free, independent Reddit archive that captured new posts
   and comments 11-21 seconds after posting in our probe. One batched call adds scores, comment counts and post bodies; other
   calls fetch nested comment trees, users, subreddit history and "who linked this URL".

Have an approved Reddit app? Set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`, and `thread`, `search` and `latest`
switch to the official API for live vote counts. I couldn't test that path.

## Limits

- Archive scores are snapshots. Posts under ~2 days old often show `1↑`, but Reddit's own ranking order is still right.
- No comment search across all of Reddit at once (the archive needs a subreddit, author or thread).
- Many Reddit clips are silent or get removed; `--transcribe` says so. In the probe, 9 of 10 sampled videos had reachable
  audio, and the one that didn't had been removed.
- Arctic Shift is run by one person, for free, with no uptime guarantee. threadsift paces and caches its requests; please
  don't hammer it. For bulk analysis (whole subreddits, years of data), use its data dumps.

## Development

```bash
python test_threadsift.py                                            # offline self-check
bash bench/clean_clone.sh https://github.com/hamgarian/threadsift     # the 9 tasks from a fresh clone
bash bench/run.sh                                                    # full comparison (slow: rate-limit waits)
```

Logs from the release checks: [clean clone](bench/clean-clone-2026-10-18.log),
[transcription](bench/transcribe-check-2026-10-18.log), [probe](bench/probe-2026-10-18.log).

## License

MIT. Not affiliated with Reddit or Arctic Shift.
