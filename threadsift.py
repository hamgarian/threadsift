# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""threadsift: research Reddit without an API key. Compact, LLM-friendly output; no scraping.

Backends:
  arctic  - Arctic Shift API (free, no key, full archive + near-realtime, comment trees)
  oauth   - official Reddit API, used automatically when REDDIT_CLIENT_ID and
            REDDIT_CLIENT_SECRET are set (live scores, 100 req/min)

Commands:
  find    "<query>" [--sub S]     relevance-ranked discovery (Reddit public RSS search)
  top     <sub> [...] [--time day] top posts per subreddit, Reddit's own ranking
  thread  <url|id> [...]          post + comment tree (markdown or json)
  search  --sub S [--title|--query|--body|--author] [--after/--before]
  latest  <subreddit>             newest posts in a subreddit
  subs    <prefix> | --query T     find subreddits by name prefix or by topic
  media   <url|id>                download image/gallery/video (+ --comments images, --transcribe audio)
  user    <name>                  profile stats + recent posts and comments
  trend   --sub S [--query Q]     sub growth (posts/comments/subscribers), or keyword activity + top authors
  links   <url|post>              where on Reddit a URL was posted, busiest discussions first
  doctor                          which data paths work right now
  rules   <subreddit> [...]       subreddit rules
  wiki    <subreddit> [--page P]  subreddit wiki pages

Listing commands (find, top, latest, search, links) share filters: --min-score --min-comments --media --no-nsfw
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ARCTIC = "https://arctic-shift.photon-reddit.com"
VERSION = "0.1.0"
# Identifies the tool honestly; Reddit's RSS and media hosts serve it fine (no browser impersonation).
UA = os.environ.get("REDDIT_USER_AGENT", f"threadsift/{VERSION} (+https://github.com/hamgarian/threadsift)")
CACHE_DIR = Path(os.environ.get("REDDIT_CACHE_DIR", Path.home() / ".cache" / "threadsift"))
CACHE_TTL = int(os.environ.get("REDDIT_CACHE_TTL", "3600"))
MIN_INTERVAL = 1.0  # seconds between uncached requests to one host
HOST_INTERVAL = {"www.reddit.com": 60.0}  # public RSS: 1 call per clock minute (measured Oct 2026)

for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8")

_last_call: dict[str, float] = {}
_token: dict[str, object] = {}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------- http

def http_get(url: str, headers: dict | None = None, data: bytes | None = None,
             cache: bool = True, retries: int = 5) -> str:
    key = hashlib.sha1(url.encode()).hexdigest()
    path = CACHE_DIR / key
    if cache and data is None and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
        return path.read_text(encoding="utf-8")

    host = urllib.parse.urlparse(url).netloc
    delay = 3.0
    for attempt in range(retries + 1):
        stamp = CACHE_DIR / f"last-call-{host}"
        last = _last_call.get(host, 0)
        if host in HOST_INTERVAL and stamp.exists():  # pace across separate CLI runs too
            last = max(last, stamp.stat().st_mtime)
        interval = HOST_INTERVAL.get(host, MIN_INTERVAL)
        if interval == 60.0:  # window resets on the clock minute, so wait for the next one, not a full 60s
            wait = (last // 60 + 1) * 60 + 1 - time.time() if last else 0
        else:
            wait = interval - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()
        if host in HOST_INTERVAL:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            stamp.touch()
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")[:300]
            # Arctic Shift sheds load with 422 "Timeout. Maybe slow down a bit".
            transient = e.code in (422, 429, 500, 502, 503, 504) and (e.code != 422 or "Timeout" in err)
            if not transient or attempt == retries:
                raise SystemExit(f"HTTP {e.code} for {url}\n{err}")
            reset = e.headers.get("x-ratelimit-reset") or e.headers.get("retry-after")
            sleep_for = min(float(reset) + 1, 90) if reset and e.code == 429 else delay
            log(f"[retry {attempt + 1}/{retries}] HTTP {e.code}, sleeping {sleep_for:.0f}s")
            time.sleep(sleep_for)
            delay *= 2
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries:
                raise SystemExit(f"Network error for {url}: {e}")
            log(f"[retry {attempt + 1}/{retries}] {e}, sleeping {delay:.0f}s")
            time.sleep(delay)
            delay *= 2

    if cache and data is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


def http_json(url: str, **kw) -> dict:
    body = json.loads(http_get(url, **kw))
    if isinstance(body, dict) and body.get("error"):
        raise SystemExit(f"API error for {url}: {body['error']}")
    return body


def arctic(endpoint: str, retries: int = 5, **params) -> list | dict:
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "", False)})
    return http_json(f"{ARCTIC}{endpoint}?{q}", retries=retries)["data"]


# ---------------------------------------------------------------- official API (optional)

def oauth_enabled() -> bool:
    return bool(os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"))


def oauth(path: str, **params) -> dict | list:
    if not _token or time.time() > float(_token["exp"]):
        cred = f"{os.environ['REDDIT_CLIENT_ID']}:{os.environ['REDDIT_CLIENT_SECRET']}"
        tok = http_json(
            "https://www.reddit.com/api/v1/access_token",
            headers={"Authorization": "Basic " + base64.b64encode(cred.encode()).decode()},
            data=b"grant_type=client_credentials", cache=False)
        _token.update(tok=tok["access_token"], exp=time.time() + tok["expires_in"] - 60)
    q = urllib.parse.urlencode({"raw_json": 1, **{k: v for k, v in params.items() if v is not None}})
    return http_json(f"https://oauth.reddit.com{path}?{q}",
                     headers={"Authorization": f"bearer {_token['tok']}"})


# ---------------------------------------------------------------- ids

ID_RE = re.compile(r"/comments/([a-z0-9]+)", re.I)
COMMENT_RE = re.compile(r"/comments/[a-z0-9]+/[^/?#]*/([a-z0-9]+)", re.I)  # permalink to one comment


def resolve_id(ref: str) -> str:
    ref = ref.strip()
    if m := ID_RE.search(ref):
        return m.group(1).lower()
    if m := re.search(r"redd\.it/([a-z0-9]+)", ref, re.I):
        return m.group(1).lower()
    if m := re.search(r"(/r/[^/]+/s/[A-Za-z0-9]+)", ref):  # share links
        data = arctic("/api/short_links", paths=m.group(1))
        target = (data[0] or {}).get("url", "") if data else ""
        if m2 := ID_RE.search(target):
            return m2.group(1).lower()
        raise SystemExit(f"Could not resolve share link {ref}")
    ref = ref.removeprefix("t3_")
    if re.fullmatch(r"[a-z0-9]{4,10}", ref, re.I):
        return ref.lower()
    raise SystemExit(f"Not a Reddit post URL or id: {ref}")


# ---------------------------------------------------------------- rendering

def ts(epoch) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%d") if epoch else "?"


def clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip() + " …[truncated]"


INLINE_IMG_RE = re.compile(r"https://(?:preview|i)\.redd\.it/[^\s)\]]+")


def media_tag(p: dict) -> str:
    """Short marker of attached media, so listings show it without a `media` call."""
    if p.get("is_gallery") and p.get("media_metadata"):
        kind = f"gallery×{len(p['media_metadata'])}"
    elif ((p.get("secure_media") or p.get("media") or {}).get("reddit_video")):
        kind = "video"
    elif p.get("post_hint") == "image" or re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", p.get("url") or "", re.I):
        kind = "gif" if (p.get("url") or "").lower().endswith(".gif") else "image"
    elif p.get("post_hint") in ("rich:video", "hosted:video"):
        kind = "external video"  # e.g. YouTube embed: link only, not downloadable here
    else:
        kind = ""
    inline = len(INLINE_IMG_RE.findall(p.get("selftext") or ""))
    kind = ", ".join(x for x in (kind, f"{inline} inline image(s)" if inline else "") if x)
    return f" [media: {kind}]" if kind else ""


def render_post(p: dict, body_chars: int) -> str:
    lines = [f"# {p.get('title')}{media_tag(p)}",
             f"r/{p.get('subreddit')} · u/{p.get('author')} · {ts(p.get('created_utc'))} · "
             f"score {p.get('score')} · {p.get('num_comments')} comments · "
             f"https://www.reddit.com{p.get('permalink') or '/comments/' + p['id']}"]
    if p.get("url") and not p.get("is_self") and "reddit.com" not in p.get("url", ""):
        lines.append(f"link: {p['url']}")
    if p.get("selftext"):
        lines += ["", clip(p["selftext"], body_chars)]
    return "\n".join(lines)


COMMENT_SORTS = {"top": (lambda c: c.get("score") or 0, True),
                 "new": (lambda c: c.get("created_utc") or 0, True),
                 "old": (lambda c: c.get("created_utc") or 0, False)}


def flatten(nodes: list, depth: int, max_depth: int, out: list, sort: str = "top") -> None:
    """Sorted DFS into (depth, comment|more) rows."""
    comments = [n for n in nodes if n.get("kind") == "t1"]
    mores = [n for n in nodes if n.get("kind") == "more"]
    key, rev = COMMENT_SORTS[sort]
    comments.sort(key=lambda n: key(n["data"]), reverse=rev)
    for n in comments:
        c = n["data"]
        if c.get("body") in ("[deleted]", "[removed]") and not c.get("replies"):
            continue
        out.append((depth, c))
        rep = c.get("replies")
        if isinstance(rep, dict):
            kids = rep["data"]["children"]
            if depth + 1 <= max_depth:
                flatten(kids, depth + 1, max_depth, out, sort)
            elif kids:
                out.append((depth + 1, {"_more": len(kids)}))
    hidden = sum(len(m["data"].get("children", [])) for m in mores)
    if hidden:
        out.append((depth, {"_more": hidden}))


def render_comments(tree: list, max_comments: int, max_depth: int, body_chars: int, min_score: int,
                    sort: str = "top") -> str:
    rows: list = []
    flatten(tree, 0, max_depth, rows, sort)
    lines, shown, skipped = [], 0, 0
    cut_depth = None  # depth of a dropped comment whose subtree we are skipping
    for depth, c in rows:
        if cut_depth is not None and depth > cut_depth:
            skipped += "_more" not in c
            continue
        cut_depth = None
        pad = "  " * depth
        if "_more" in c:
            if shown < max_comments:
                lines.append(f"{pad}- …{c['_more']} more replies not loaded")
            continue
        if (c.get("score") or 0) < min_score or shown >= max_comments:
            skipped += 1
            cut_depth = depth
            continue
        body = clip(c.get("body", ""), body_chars).replace("\n", "\n" + pad + "  ")
        op = " (OP)" if c.get("is_submitter") else ""
        lines.append(f"{pad}- [{c.get('score')}] u/{c.get('author')}{op}: {body}")
        shown += 1
    if skipped:
        lines.append(f"\n({skipped} comments omitted by --max-comments/--min-score)")
    return "\n".join(lines)


def render_listing(posts: list, body_chars: int) -> str:
    out = []
    for p in posts:
        if "body" in p:  # comment search hit
            out.append(f"- [{p.get('score')}] u/{p.get('author')} in r/{p.get('subreddit')} "
                       f"{ts(p.get('created_utc'))} (post {str(p.get('link_id', '')).removeprefix('t3_')}, "
                       f"comment {p.get('id')}): {clip(p.get('body', ''), body_chars).replace(chr(10), ' ')}")
        else:
            out.append(f"- {p.get('id')} [{p.get('score')}↑ {p.get('num_comments')}💬] "
                       f"r/{p.get('subreddit')} {ts(p.get('created_utc'))}: {p.get('title')}{media_tag(p)}"
                       + (f"\n    {clip(p['selftext'], body_chars).replace(chr(10), ' ')}"
                          if body_chars and p.get("selftext") else ""))
    return "\n".join(out) or "(no results)"


def filter_posts(items: list, a) -> list:
    """Apply the shared listing filters (posts and comment hits)."""
    def ok(p: dict) -> bool:
        if (p.get("score") or 0) < a.min_score:
            return False
        if "body" in p:  # comment hits only take --min-score
            return True
        tag = media_tag(p)
        media_ok = (a.media is None or (a.media == "any" and tag) or (a.media == "none" and not tag)
                    or (a.media not in ("any", "none") and a.media in tag))
        return (bool(media_ok) and (p.get("num_comments") or 0) >= a.min_comments
                and not (a.no_nsfw and p.get("over_18")))
    return [p for p in items if ok(p)]


def emit(items: list, a) -> None:
    items = filter_posts(items, a)
    print(json.dumps(items, ensure_ascii=False) if a.format == "json" else render_listing(items, a.body_chars))


# ---------------------------------------------------------------- commands

def cmd_thread(a) -> None:
    ids = [resolve_id(r) for r in a.refs]
    # a link to one comment opens just that comment's sub-thread
    focus = {pid: (m.group(1).lower() if (m := COMMENT_RE.search(r)) else None) for pid, r in zip(ids, a.refs)}
    results = []
    if oauth_enabled() and a.backend != "arctic":
        for pid in ids:
            post_l, com_l = oauth(f"/comments/{pid}", limit=500, depth=a.depth + 1, sort=a.sort, comment=focus[pid])
            results.append((post_l["data"]["children"][0]["data"], com_l["data"]["children"]))
    else:
        posts = {p["id"]: p for p in arctic("/api/posts/ids", ids=",".join(ids))}
        for pid in ids:
            if pid not in posts:
                log(f"post {pid} not found in Arctic Shift")
                continue
            tree = arctic("/api/comments/tree", link_id=f"t3_{pid}", limit=a.fetch_limit,
                          start_breadth=a.breadth, start_depth=a.depth + 1,
                          parent_id=f"t1_{focus[pid]}" if focus[pid] else None)
            results.append((posts[pid], tree))

    if a.format == "json":
        print(json.dumps([{"post": p, "comments": t} for p, t in results], ensure_ascii=False))
        return
    for p, tree in results:
        print(render_post(p, a.body_chars))
        cid = focus.get(p["id"])
        print(f"\n## Comments (only the thread under comment {cid})\n" if cid else "\n## Comments\n")
        print(render_comments(tree, a.max_comments, a.depth, a.body_chars, a.min_score, a.sort))
        print("\n---\n")


def cmd_search(a) -> None:
    if oauth_enabled() and a.backend != "arctic" and a.kind == "posts" and a.query:
        path = f"/r/{a.sub}/search" if a.sub else "/search"
        data = oauth(path, q=a.query, restrict_sr=1 if a.sub else None, sort=a.sort or "relevance",
                     t=a.time or "all", limit=min(a.limit, 100))
        hits = [c["data"] for c in data["data"]["children"]]
    else:
        if not (a.sub or a.author or a.link):
            raise SystemExit("Arctic Shift keyword search needs --sub, --author or --link. "
                             "For open-ended discovery use `find \"<terms>\"`.")
        common = dict(author=a.author, after=a.after, before=a.before,
                      limit=a.limit, sort=a.sort if a.sort in ("asc", "desc") else None)
        subs = a.sub.split(",") if a.sub else [None]
        if a.kind == "comments" and len(subs) > 1:  # one search per sub, merged newest first
            hits = sorted((h for sub in subs for h in arctic(
                "/api/comments/search", body=a.query or a.body, subreddit=sub.strip(), **common)),
                key=lambda h: h.get("created_utc") or 0, reverse=a.sort != "asc")
            return emit(hits[:a.limit] if isinstance(a.limit, int) else hits, a)
        common["subreddit"] = a.sub
        if a.kind == "posts":
            keyword = a.title or a.selftext or a.query or a.flair
            try:
                # Post full-text search is the most overloaded Arctic endpoint: fail fast.
                hits = arctic("/api/posts/search", retries=3 if keyword else 5, title=a.title,
                              selftext=a.selftext, query=a.query, link_flair_text=a.flair, **common)
            except SystemExit as e:
                if not keyword:
                    raise
                raise SystemExit(f"{e}\nHint: post keyword search is overloaded. Discover threads with "
                                 "`find \"<terms>\" --sub <sub>` and pass the ids to `thread`, "
                                 "or search comments instead (--kind comments).")
        else:
            hits = arctic("/api/comments/search", body=a.query or a.body,
                          link_id=f"t3_{resolve_id(a.link)}" if a.link else None, **common)
    emit(hits, a)


def cmd_find(a) -> None:
    """Relevance-ranked discovery via Reddit's public RSS search, enriched from Arctic Shift."""
    base = f"https://www.reddit.com/r/{a.sub}/search.rss" if a.sub else "https://www.reddit.com/search.rss"
    q = urllib.parse.urlencode({"q": a.query, "sort": a.sort, "t": a.time, "limit": a.limit,
                                "restrict_sr": "on" if a.sub else None, "type": "link"} if a.sub else
                               {"q": a.query, "sort": a.sort, "t": a.time, "limit": a.limit, "type": "link"})
    emit(rss_posts(f"{base}?{q}"), a)


def cmd_top(a) -> None:
    """Top posts per subreddit for a period, in Reddit's own ranking order."""
    # One combined request (r/a+b+c) instead of one per sub: RSS allows a single call per minute.
    # Always ask for the max 100: same one request, and it leaves room for quiet subs next to busy ones.
    # shortcut: a quiet sub can still get fewer than --limit posts from the shared top 100; query it alone if that matters.
    posts = rss_posts(f"https://www.reddit.com/r/{'+'.join(a.subs)}/{a.sort}.rss?t={a.time}&limit=100")
    posts = filter_posts(posts, a)
    out = {sub: [p for p in posts if p.get("subreddit", "").lower() == sub.lower()][:a.limit] for sub in a.subs}
    if a.format == "json":
        print(json.dumps(out, ensure_ascii=False))
        return
    for sub, items in out.items():
        label = f"{a.sort}, {a.time}" if a.sort in ("top", "controversial") else a.sort
        print(f"## r/{sub} ({label})\n{render_listing(items, a.body_chars)}\n")


def rss_posts(url: str) -> list[dict]:
    """Posts from a Reddit Atom feed, enriched with Arctic Shift fields in one batched call."""
    root = ET.fromstring(http_get(url, headers={"User-Agent": UA}))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    found = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns).get("href")
        if m := ID_RE.search(link):
            found.append({"id": m.group(1).lower(), "title": e.findtext("a:title", namespaces=ns),
                          "permalink": urllib.parse.urlparse(link).path,
                          "subreddit": (e.find("a:category", ns).get("term")
                                        if e.find("a:category", ns) is not None else "?"),
                          "created_utc": datetime.fromisoformat(
                              e.findtext("a:published", namespaces=ns)).timestamp()})
    if found:
        try:  # one batched call adds score / comment counts / selftext
            extra = {p["id"]: p for p in arctic("/api/posts/ids", retries=2, ids=",".join(f["id"] for f in found))}
            found = [{**f, **extra.get(f["id"], {})} for f in found]
        except SystemExit as e:
            log(f"(enrichment skipped: {str(e).splitlines()[0]})")
    return found


def cmd_latest(a) -> None:
    if oauth_enabled() and a.backend != "arctic":
        data = oauth(f"/r/{a.sub}/{a.sort}", t=a.time, limit=min(a.limit, 100))
        hits = [c["data"] for c in data["data"]["children"]]
    else:
        hits = arctic("/api/posts/search", subreddit=a.sub, after=a.after, before=a.before,
                      limit=a.limit, sort="desc")
    emit(hits, a)


def cmd_subs(a) -> None:
    if a.query:  # topic search via Reddit's own subreddit search (one RSS call)
        root = ET.fromstring(http_get("https://www.reddit.com/subreddits/search.rss?" + urllib.parse.urlencode(
            {"q": a.query, "limit": a.limit}), headers={"User-Agent": UA}))
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns):
            link = e.find("a:link", ns).get("href")
            print(f"- {urllib.parse.urlparse(link).path.rstrip('/')[1:]}: {e.findtext('a:title', namespaces=ns)}")
        return
    if not a.prefix:
        raise SystemExit("give a name prefix or --query <topic>")
    hits = arctic("/api/subreddits/search", subreddit_prefix=a.prefix, limit=a.limit,
                  fields="display_name,subscribers,public_description")
    for s in hits:
        print(f"- r/{s.get('display_name')} ({s.get('subscribers')} subs): "
              f"{clip(s.get('public_description') or '', 160)}")


def cmd_user(a) -> None:
    name = a.name.removeprefix("u/").removeprefix("/u/")
    info = arctic("/api/users/search", author=name)
    posts = arctic("/api/posts/search", author=name, limit=a.limit, sort="desc")
    comments = arctic("/api/comments/search", author=name, limit=a.limit, sort="desc")
    if a.format == "json":
        print(json.dumps({"user": info, "posts": posts, "comments": comments}, ensure_ascii=False))
        return
    if info:
        m = info[0].get("_meta", {})
        print(f"# u/{name}\nkarma {m.get('total_karma')} (post {m.get('post_karma')}, comment {m.get('comment_karma')}) · "
              f"{m.get('num_posts')} posts, {m.get('num_comments')} comments · active "
              f"{ts(min(filter(None, [m.get('earliest_post_at'), m.get('earliest_comment_at')]), default=0))} → "
              f"{ts(max(filter(None, [m.get('last_post_at'), m.get('last_comment_at')]), default=0))} "
              "(stats refresh infrequently)")
    else:
        print(f"# u/{name}\n(no profile stats in Arctic Shift)")
    try:  # all-time posts + comments per subreddit, straight from the archive
        active = [(s["subreddit"], s["count"]) for s in arctic("/api/users/interactions/subreddits", retries=2,
                                                                author=name, limit=10)]
        label = "most active in (all time, posts + comments)"
    except SystemExit:  # times out for very active accounts: fall back to the recent items we already have
        counts: dict[str, int] = {}
        for x in posts + comments:
            counts[x.get("subreddit")] = counts.get(x.get("subreddit"), 0) + 1
        active, label = sorted(counts.items(), key=lambda kv: -kv[1])[:10], "most active in (recent items only)"
    print(f"{label}: " + ", ".join(f"r/{s} ({n})" for s, n in active))
    print(f"\n## Recent posts\n{render_listing(posts, a.body_chars)}\n\n## Recent comments\n{render_listing(comments, a.body_chars)}")


def cmd_trend(a) -> None:
    """Activity over time (and top authors) for a sub/author/keyword, counted from paged search results."""
    if a.sub and not (a.query or a.author):
        return subreddit_history(a)
    endpoint = "/api/posts/search" if a.kind == "posts" else "/api/comments/search"
    kw = {"query": a.query} if a.kind == "posts" else {"body": a.query}
    if not (a.sub or a.author):
        raise SystemExit("trend needs --sub or --author")
    items, before = [], a.before
    for _ in range(a.pages):  # newest first, walking back in time
        page = arctic(endpoint, subreddit=a.sub, author=a.author, after=a.after, before=before,
                      limit=100, sort="desc", fields="id,created_utc,author", **kw)
        items += page
        if len(page) < 100:
            break
        before = int(page[-1]["created_utc"])
    if not items:
        print("(no matches)")
        return
    fmt = {"day": "%Y-%m-%d", "week": "%G-W%V", "month": "%Y-%m"}[a.by]
    buckets: dict[str, int] = {}
    authors: dict[str, int] = {}
    for x in items:
        k = datetime.fromtimestamp(int(x["created_utc"]), timezone.utc).strftime(fmt)
        buckets[k] = buckets.get(k, 0) + 1
        authors[x.get("author")] = authors.get(x.get("author"), 0) + 1
    span = f"{ts(items[-1]['created_utc'])} → {ts(items[0]['created_utc'])}"
    complete = "" if len(items) < a.pages * 100 else f" (capped at {len(items)}; raise --pages or narrow --after for full history)"
    print(f"{len(items)} {a.kind} matching {a.query or '*'} in {('r/' + a.sub) if a.sub else ('u/' + a.author)}, "
          f"{span}{complete}\n")
    peak = max(buckets.values())
    for k in sorted(buckets):
        print(f"{k}  {buckets[k]:>5}  {'█' * max(1, round(30 * buckets[k] / peak))}")
    print("\ntop authors: " + ", ".join(f"u/{n} ({c})" for n, c in sorted(authors.items(), key=lambda kv: -kv[1])[:10]
                                       if n not in ("[deleted]", "AutoModerator")))


def subreddit_history(a) -> None:
    """Whole-subreddit growth from Arctic's precomputed time series: posts, comments, subscribers."""
    precision = {"day": "day", "week": "week", "month": "month"}[a.by]
    series = {}
    for key in ("posts/count", "comments/count", "subscribers"):
        try:
            series[key] = {int(p["date"]): p["value"] for p in arctic(
                "/api/time_series", retries=2, key=f"r/{a.sub}/{key}", precision=precision, after=a.after, before=a.before)}
        except SystemExit:
            series[key] = {}
    dates = sorted(set().union(*series.values()))
    if not dates:
        print(f"(no history for r/{a.sub})")
        return
    if a.format == "json":
        print(json.dumps([{"date": ts(d), **{k: series[k].get(d) for k in series}} for d in dates]))
        return
    peak = max(series["posts/count"].values(), default=0) or 1
    print(f"r/{a.sub} by {a.by} (Arctic Shift time series; recent buckets may still be filling)\n")
    print(f"{'date':<10} {'posts':>7} {'comments':>9} {'subscribers':>12}")
    for d in dates:
        p, c, s = (series[k].get(d) for k in ("posts/count", "comments/count", "subscribers"))
        print(f"{ts(d):<10} {p if p is not None else '-':>7} {c if c is not None else '-':>9} "
              f"{round(s) if s is not None else '-':>12}  {'█' * round(30 * (p or 0) / peak)}")


def cmd_links(a) -> None:
    """Where on Reddit a URL (article, repo, video...) was posted, busiest discussions first."""
    url = a.ref
    if not url.startswith("http") or "reddit.com" in url or "redd.it" in url:  # a Reddit post: use its link
        post = arctic("/api/posts/ids", ids=resolve_id(url))
        url = (post[0].get("url_overridden_by_dest") or post[0].get("url") or "") if post else ""
        if not url or "reddit.com" in url or "redd.it" in url:
            raise SystemExit("that post has no external link to look up")
    hits = arctic("/api/posts/search", url=url, url_exact=a.exact or None, limit=100, sort="desc")
    hits.sort(key=lambda p: (p.get("num_comments") or 0, p.get("score") or 0), reverse=True)
    log(f"{len(hits)} posts link to {url}{'' if a.exact else ' (prefix match)'}")
    emit(hits[:a.limit], a)


def cmd_doctor(a) -> None:
    """Which data paths work right now, and what the next RSS call will cost."""
    checks = []
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "last-call-www.reddit.com").touch()  # count this call so the next command waits for a new minute
    try:
        req = urllib.request.Request("https://www.reddit.com/r/announcements/new.rss?limit=1",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            checks.append(("reddit rss", f"ok, {r.headers.get('x-ratelimit-remaining')} left, "
                                         f"window resets in {r.headers.get('x-ratelimit-reset')}s"))
    except urllib.error.HTTPError as e:
        checks.append(("reddit rss", f"HTTP {e.code} (429 = this minute's call is used; resets in "
                                     f"{e.headers.get('x-ratelimit-reset')}s)"))
    except Exception as e:  # network down, DNS, ...
        checks.append(("reddit rss", f"FAIL {e}"))
    t0 = time.time()
    try:
        arctic("/api/posts/ids", retries=1, ids="x8i09x", fields="id")
        checks.append(("arctic shift", f"ok ({time.time() - t0:.1f}s)"))
    except SystemExit as e:
        checks.append(("arctic shift", f"FAIL {str(e).splitlines()[0]}"))
    checks.append(("reddit oauth", "credentials set (thread/search/latest use the official API)" if oauth_enabled()
                   else "not configured (fine: Arctic Shift + RSS cover everything)"))
    for tool in ("ffmpeg", "ffprobe", "uv"):
        checks.append((tool, shutil.which(tool) or "missing" + (" (needed for video frames/audio)" if tool != "uv" else "")))
    size = sum(f.stat().st_size for f in CACHE_DIR.rglob("*") if f.is_file()) if CACHE_DIR.exists() else 0
    checks.append(("cache", f"{CACHE_DIR} ({size / 1e6:.1f} MB)"))
    for k, v in checks:
        print(f"{k:<13} {v}")


def comment_images(pid: str) -> list[str]:
    """Image links posted in a thread's comments."""
    found: list[str] = []
    def walk(nodes: list) -> None:
        for n in nodes:
            if n.get("kind") == "t1":
                found.extend(INLINE_IMG_RE.findall(n["data"].get("body") or ""))
                rep = n["data"].get("replies")
                if isinstance(rep, dict):
                    walk(rep["data"]["children"])
    walk(arctic("/api/comments/tree", link_id=f"t3_{pid}", limit=2000))
    return list(dict.fromkeys(found))


def transcribe(p: dict, out: Path) -> None:
    """Speech-to-text of a Reddit-hosted video: audio from the post's HLS playlist, then local Whisper."""
    video = ((p.get("secure_media") or p.get("media") or {}).get("reddit_video") or {})
    if not video.get("fallback_url"):
        print("(no Reddit-hosted video to transcribe)")
        return
    # audio sits in the HLS playlist; newer posts sign it (hls_url) and serve video from packaged-media.redd.it
    vid = next((m.group(1) for u in (video.get("hls_url"), video.get("dash_url"), video["fallback_url"])
                if u and (m := re.search(r"redd\.it/(\w+)/", u))), None)
    playlists = [u.replace("&amp;", "&") for u in (video.get("hls_url"),) if u]
    playlists += [f"https://v.redd.it/{vid}/HLSPlaylist.m3u8"] if vid else []
    wav = out / "audio.wav"
    if not wav.exists():
        ok = False
        for playlist in playlists:  # signed URL first, then the plain one
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-user_agent", UA, "-i", playlist,
                                "-vn", "-ac", "1", "-ar", "16000", str(wav)], capture_output=True, text=True)
            if (ok := r.returncode == 0):
                break
        if not ok:
            wav.unlink(missing_ok=True)
            print("(audio unavailable: the video has no sound track, or it was removed; "
                  "many Reddit clips are silent)")
            return
    txt = out / "transcript.txt"
    if not txt.exists():
        r = subprocess.run(["uv", "run", "--script", str(Path(__file__).with_name("transcribe.py")), str(wav), str(txt)])
        if r.returncode != 0:
            print("(transcription failed)")
            return
    print(f"transcript: {txt}\n{txt.read_text(encoding='utf-8')}")


def prune_media(days: int = 14) -> None:
    root = CACHE_DIR / "media"
    for d in root.glob("*") if root.exists() else []:
        if time.time() - d.stat().st_mtime > days * 86400:
            shutil.rmtree(d, ignore_errors=True)


def media_urls(p: dict) -> list[str]:
    """Direct URLs for a post's image, gallery images or video (video = audio-less fallback mp4)."""
    if p.get("is_gallery") and p.get("media_metadata"):
        order = [i["media_id"] for i in (p.get("gallery_data") or {}).get("items", [])] or list(p["media_metadata"])
        return [p["media_metadata"][m]["s"].get("u") or p["media_metadata"][m]["s"].get("gif")
                for m in order if m in p["media_metadata"] and "s" in p["media_metadata"][m]]
    video = ((p.get("secure_media") or p.get("media") or {}).get("reddit_video") or {}).get("fallback_url")
    if video:
        return [video]
    inline = INLINE_IMG_RE.findall(p.get("selftext") or "")
    if inline:  # images pasted into a text post's body
        return inline
    url = p.get("url_overridden_by_dest") or p.get("url") or ""
    if re.search(r"\.(jpe?g|png|gif|webp|mp4)(\?|$)", url, re.I):
        return [url]
    preview = ((p.get("preview") or {}).get("images") or [{}])[0].get("source", {}).get("url")
    return [preview] if preview else []  # link posts: the thumbnail/preview image


def cmd_media(a) -> None:
    pid = resolve_id(a.ref)
    posts = arctic("/api/posts/ids", ids=pid)
    if not posts:
        raise SystemExit(f"post {pid} not found")
    prune_media()
    out = Path(a.out or CACHE_DIR / "media" / pid)
    out.mkdir(parents=True, exist_ok=True)
    urls = media_urls(posts[0])
    if a.comments:
        urls += [u for u in comment_images(pid) if u not in urls]
    urls = urls[:a.max_files]
    if not urls:
        print("(post has no media)")
    for i, url in enumerate(urls):
        url = url.replace("&amp;", "&")
        ext = re.search(r"\.(jpe?g|png|gif|webp|mp4)", url, re.I)
        path = out / f"{i:02d}.{ext.group(1).lower() if ext else 'jpg'}"
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    path.write_bytes(resp.read())
            except (urllib.error.URLError, TimeoutError) as e:  # deleted/blocked file: skip, keep the rest
                print(f"(skipped {url[:80]}: {e})")
                continue
        if path.suffix in (".mp4", ".gif") and a.frames and shutil.which("ffmpeg"):
            print("\n".join(str(f) for f in extract_frames(path, a.frames)))
        else:
            print(path)
    if a.transcribe:
        transcribe(posts[0], out)


def extract_frames(video: Path, n: int) -> list[Path]:
    """n evenly spaced stills (768px wide) so a model can look at a video or gif."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(video)], capture_output=True, text=True)
    dur = float(probe.stdout.strip() or 0) or 1.0
    frames = []
    for k in range(n):
        f = video.with_name(f"{video.stem}_frame{k}.jpg")
        if not f.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * (k + 0.5) / n:.2f}", "-i", str(video),
                            "-frames:v", "1", "-vf", "scale=768:-2", str(f)], check=True)
        frames.append(f)
    return frames


def cmd_rules(a) -> None:
    print(json.dumps(arctic("/api/subreddits/rules", subreddits=",".join(a.subs)), ensure_ascii=False, indent=1))


def cmd_wiki(a) -> None:
    if not a.page:
        print("\n".join(arctic("/api/subreddits/wikis/list", subreddit=a.sub)))
        return
    for w in arctic("/api/subreddits/wikis", paths=f"/r/{a.sub}/wiki/{a.page}"):
        print(w.get("content", ""))


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--backend", choices=["auto", "arctic"], default="auto",
                        help="force Arctic Shift even when Reddit OAuth credentials exist")
    common.add_argument("--format", choices=["md", "json"], default="md")
    common.add_argument("--body-chars", type=int, default=None,
                        help="truncate each body to N chars (0 = titles only in listings)")
    common.add_argument("--no-cache", action="store_true")
    filters = argparse.ArgumentParser(add_help=False)
    filters.add_argument("--min-score", type=int, default=-999, help="snapshot score; unreliable on posts < ~2 days old")
    filters.add_argument("--min-comments", type=int, default=0)
    filters.add_argument("--media", choices=["any", "none", "image", "gif", "video", "gallery"],
                         help="only posts with (a kind of) media, or without any")
    filters.add_argument("--no-nsfw", action="store_true")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    _add = sp.add_parser
    sp.add_parser = lambda *x, listing=False, **k: _add(*x, parents=[common, filters] if listing else [common], **k)

    t = sp.add_parser("thread", help="post + comment tree")
    t.add_argument("refs", nargs="+", help="post URLs, share links, redd.it links or ids")
    t.add_argument("--max-comments", type=int, default=150)
    t.add_argument("--min-score", type=int, default=-999)
    t.add_argument("--depth", type=int, default=6, help="max reply depth to render")
    t.add_argument("--breadth", type=int, default=50, help="arctic: siblings expanded per level")
    t.add_argument("--fetch-limit", type=int, default=2000, help="arctic: max comments fetched")
    t.add_argument("--sort", choices=list(COMMENT_SORTS), default="top", help="comment order at each level")
    t.set_defaults(fn=cmd_thread)

    s = sp.add_parser("search", help="keyword search posts or comments", listing=True)
    s.add_argument("--kind", choices=["posts", "comments"], default="posts")
    s.add_argument("--sub", help="comments: comma-separate several subs to search them all")
    s.add_argument("--author"); s.add_argument("--link", help="comments: restrict to a post")
    s.add_argument("--query", help="posts: title+selftext; comments: body")
    s.add_argument("--title"); s.add_argument("--selftext"); s.add_argument("--body"); s.add_argument("--flair")
    s.add_argument("--after", help="YYYY-MM-DD or epoch"); s.add_argument("--before")
    s.add_argument("--sort", help="arctic: asc|desc by date; oauth: relevance|top|new|comments")
    s.add_argument("--time", help="oauth only: hour|day|week|month|year|all")
    s.add_argument("--limit", default=25, type=lambda v: v if v == "auto" else int(v))
    s.set_defaults(fn=cmd_search)

    f = sp.add_parser("find", help="relevance-ranked thread discovery (Reddit RSS search)", listing=True)
    f.add_argument("query"); f.add_argument("--sub", help="restrict to a subreddit")
    f.add_argument("--sort", default="relevance", choices=["relevance", "top", "new", "comments"])
    f.add_argument("--time", default="all", choices=["hour", "day", "week", "month", "year", "all"])
    f.add_argument("--limit", type=int, default=25, help="max 100")
    f.set_defaults(fn=cmd_find)

    tp = sp.add_parser("top", help="top posts of the day/week/... per subreddit (Reddit's ranking)", listing=True)
    tp.add_argument("subs", nargs="+")
    tp.add_argument("--time", default="day", choices=["hour", "day", "week", "month", "year", "all"])
    tp.add_argument("--sort", default="top", choices=["top", "hot", "new", "rising", "controversial"])
    tp.add_argument("--limit", type=int, default=10)
    tp.set_defaults(fn=cmd_top)

    l = sp.add_parser("latest", help="newest posts in a subreddit", listing=True)
    l.add_argument("sub"); l.add_argument("--after"); l.add_argument("--before")
    l.add_argument("--limit", type=int, default=25)
    l.add_argument("--sort", default="new", help="oauth only: new|hot|top|rising")
    l.add_argument("--time", default="week", help="oauth only, with --sort top")
    l.set_defaults(fn=cmd_latest)

    su = sp.add_parser("subs", help="find subreddits by name prefix")
    su.add_argument("prefix", nargs="?"); su.add_argument("--query", help="find subreddits by topic instead")
    su.add_argument("--limit", type=int, default=15)
    su.set_defaults(fn=cmd_subs)

    m = sp.add_parser("media", help="download a post's image/gallery/video; videos & gifs -> still frames")
    m.add_argument("ref"); m.add_argument("--out", help="folder (default ~/.cache/threadsift/media/<id>)")
    m.add_argument("--frames", type=int, default=6, help="stills per video/gif (0 = keep the file only)")
    m.add_argument("--max-files", type=int, default=20)
    m.add_argument("--comments", action="store_true", help="also images posted in the comments")
    m.add_argument("--transcribe", action="store_true",
                   help="speech-to-text of a Reddit video (local Whisper; best effort, often blocked on recent videos)")
    m.set_defaults(fn=cmd_media)

    u = sp.add_parser("user", help="profile stats + recent posts and comments")
    u.add_argument("name"); u.add_argument("--limit", type=int, default=15)
    u.set_defaults(fn=cmd_user)

    lk = sp.add_parser("links", help="where on Reddit a URL was posted (or another Reddit post's link)", listing=True)
    lk.add_argument("ref", help="any URL, or a Reddit post whose link to look up")
    lk.add_argument("--exact", action="store_true", help="exact URL only (default: prefix match)")
    lk.add_argument("--limit", type=int, default=25)
    lk.set_defaults(fn=cmd_links)

    dr = sp.add_parser("doctor", help="check which data paths work right now (uses 1 RSS call)")
    dr.set_defaults(fn=cmd_doctor)

    tr = sp.add_parser("trend", help="sub growth over time, or keyword/author activity + top authors")
    tr.add_argument("--sub"); tr.add_argument("--author"); tr.add_argument("--query", help="keyword filter")
    tr.add_argument("--kind", choices=["posts", "comments"], default="posts")
    tr.add_argument("--by", choices=["day", "week", "month"], default="week")
    tr.add_argument("--after", help="YYYY-MM-DD"); tr.add_argument("--before")
    tr.add_argument("--pages", type=int, default=10, help="100 items per page, newest first")
    tr.set_defaults(fn=cmd_trend)

    r = sp.add_parser("rules"); r.add_argument("subs", nargs="+"); r.set_defaults(fn=cmd_rules)
    w = sp.add_parser("wiki"); w.add_argument("sub"); w.add_argument("--page"); w.set_defaults(fn=cmd_wiki)

    a = ap.parse_args()
    if a.body_chars is None:  # per-command default; set_defaults would leak across subparsers sharing `common`
        a.body_chars = {"find": 0, "top": 0, "user": 200, "links": 200}.get(a.cmd, 1200)
    if a.no_cache:
        global CACHE_TTL
        CACHE_TTL = 0
    a.fn(a)


if __name__ == "__main__":
    main()
