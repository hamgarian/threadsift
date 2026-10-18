"""Score a bench run: python summarize.py <results dir>. Same pass rule per task for every tool.

T1/T2 search      pass: >=5 posts returned           quality: share with a numeric score
T3 thread         pass: >=10 comments                quality: scores shown, reply depth
T4 top of week    pass: >=5 posts AND >=50% overlap with Reddit's own top-of-week list (reference_top_week.xml)
T5 user           pass: >=1 post or comment by the user
T6 gallery        pass: the 4 gallery images are reachable (4 direct image URLs or downloaded files)
T7 links          pass: >=1 returned post is among the posts that link the repo (reference_links.json, archive url field)
T8 sub growth     pass: >=3 periods of subscriber or post counts
T9 comment link   pass: shows the target comment AND not the rest of the thread (no other top-level comment)
"""
import json
import re
import sys
from pathlib import Path

R = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
TOOLS = ["ours", "hermes", "arctic", "buddy", "elias"]
NAMES = {"ours": "threadsift", "hermes": "Hermes reddit-reading (anonymous)", "arctic": "arctic-shift-mcp 1.0.2",
         "buddy": "reddit-mcp-buddy 1.1.14 (anonymous)", "elias": "reddit-no-auth-mcp-server"}
TASKS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
REPO = "github.com/NousResearch/hermes-agent"
TARGET, OTHER_TOP = "I like the intent", "itprobablynothingbut"  # T9: target comment text vs another top-level commenter


def load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def raw_outputs(tool):
    """task -> (text or parsed json, error) for each tool, preferring a successful retry."""
    out = {}
    if tool in ("buddy", "elias", "arctic"):
        for f in (f"out_{tool}.json", f"retry_out_{tool}.json"):
            for r in load(R / f) or []:
                if r["task"] not in out or (out[r["task"]][1] and not r["error"]):
                    out[r["task"]] = (r["text"], r["error"])
    else:
        for t in TASKS:
            p = R / f"{tool}_{t}.out"
            if p.exists():
                txt = p.read_text(encoding="utf-8", errors="replace")
                err = (R / f"{tool}_{t}.err").read_text(encoding="utf-8", errors="replace") if not txt.strip() else None
                out[t] = (load(p) if txt.strip().startswith(("{", "[")) else txt, err)
    return out


def posts_of(x):
    """Best-effort list of post dicts from any tool's JSON; None for prose."""
    if isinstance(x, str):
        x = load_str(x)
    if isinstance(x, dict):
        for k in ("posts", "results", "data", "items"):
            if isinstance(x.get(k), list):
                return x[k]
        vals = [v for v in x.values() if isinstance(v, list)]
        return [p for v in vals for p in v] if vals else None
    return x if isinstance(x, list) else None


def load_str(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def post_id(p):
    """Post id from an id field or a permalink/url (tools differ)."""
    if p.get("id") and "body" not in p:
        return str(p["id"]).removeprefix("t3_")
    m = re.search(r"/comments/(\w+)/", str(p.get("permalink") or p.get("url") or ""))
    return m.group(1) if m else None


def count_tree(nodes):
    n = 0
    for c in nodes:
        if c.get("kind") == "t1":
            rep = c["data"].get("replies")
            n += 1 + (count_tree(rep["data"]["children"]) if isinstance(rep, dict) else 0)
    return n


def text_posts(s):  # arctic-shift-mcp prose: "[id] title\nr/sub • u/x • score: N • comments: M"
    return [{"id": i, "score": int(sc)} for i, sc in re.findall(r"\[(\w+)\][^\n]*\n[^\n]*score: (-?\d+)", s or "")]


def as_text(x):
    return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)


def reference_top():
    p = R / "reference_top_week.xml"
    return set(re.findall(r"/comments/(\w+)/", p.read_text(encoding="utf-8"))) if p.exists() else set()


def score(tool, task, val):
    """-> (passed: bool, note: str)"""
    x, err = val
    if err and not x:
        return False, re.sub(r"\s+", " ", err.strip().splitlines()[-1])[:70]
    txt = as_text(x)
    posts = posts_of(x) if not isinstance(x, str) else (posts_of(x) or text_posts(x))
    if task in ("T1", "T2", "T4", "T5", "T7"):
        if task == "T5" and isinstance(x, dict) and ("posts" in x or "comments" in x):
            posts = (x.get("posts") or []) + (x.get("comments") or [])
        if task == "T4" and isinstance(x, dict) and "LocalLLaMA" in x:
            posts = x["LocalLLaMA"]
        posts = [p for p in (posts or []) if isinstance(p, dict)]
        scored = sum(isinstance(p.get("score"), (int, float)) for p in posts)
        note = f"{len(posts)} items, {scored} with score"
        if task in ("T1", "T2"):
            return len(posts) >= 5, note
        ids = {post_id(p) for p in posts} - {None}
        if task == "T4":
            ref = reference_top()
            overlap = len(ids & ref) / max(1, min(len(ids), len(ref)))
            return len(posts) >= 5 and overlap >= 0.5, f"{note}, {overlap:.0%} match Reddit's top-of-week"
        if task == "T5":
            return len(posts) >= 1, note
        ref = {p["id"] for p in (load(R / "reference_links.json") or {}).get("data", [])}
        hits = ids & ref
        return len(hits) >= 1, f"{len(hits)} of {len(posts)} results link the repo"
    if task == "T3":
        if isinstance(x, dict) and isinstance(x.get("comments"), list):  # flat comment list
            n = len(x["comments"])
        elif isinstance(x, list) and x and isinstance(x[0], dict) and "comments" in x[0]:  # nested tree
            n = count_tree(x[0]["comments"])
        else:  # prose, one "(score: N" per comment
            n = len(re.findall(r"\(score: -?\d+", txt))
        has_scores = bool(re.search(r'"score": ?-?\d+|score: -?\d+|\[\d+\]', txt))
        return n >= 10, f"{n} comments, scores {'yes' if has_scores else 'no'}"
    if task == "T6":
        files = re.findall(r"\.(?:jpe?g|png|webp)\b", txt) if isinstance(x, str) and "media" in txt else []
        urls = set(re.findall(r"https://(?:i|preview)\.redd\.it/[\w.?=&%-]+", txt))
        n = max(len(files), len(urls))
        return n >= 4, f"{n} images reachable"
    if task == "T8":
        rows = x if isinstance(x, list) else []
        return len(rows) >= 3, f"{len(rows)} periods"
    if task == "T9":
        has_target, has_other = TARGET in txt, OTHER_TOP in txt
        return has_target and not has_other, ("target comment only" if has_target and not has_other else
                                               "whole thread returned" if has_target else "target comment missing")
    return False, "?"


def main():
    rows, totals = {}, {}
    for tool in TOOLS:
        outs = raw_outputs(tool)
        rows[tool] = {t: (score(tool, t, outs[t]) if t in outs else (None, "no tool for this")) for t in TASKS}
        totals[tool] = sum(1 for v in rows[tool].values() if v[0])
    print("| Task | " + " | ".join(NAMES[t] for t in TOOLS) + " |")
    print("|---|" + "---|" * len(TOOLS))
    for t in TASKS:
        cells = []
        for tool in TOOLS:
            ok, note = rows[tool][t]
            cells.append(("—" if ok is None else "✅" if ok else "❌") + f" {note}")
        print(f"| {t} | " + " | ".join(cells) + " |")
    print("| **passed** | " + " | ".join(f"**{totals[t]}/9**" for t in TOOLS) + " |")


if __name__ == "__main__":
    main()
