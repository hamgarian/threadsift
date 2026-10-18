# Offline self-check: python test_threadsift.py
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("threadsift", Path(__file__).with_name("threadsift.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

assert r.resolve_id("https://www.reddit.com/r/x/comments/1x8lalp/title/") == "1x8lalp"
assert r.resolve_id("https://redd.it/abc123") == "abc123"
assert r.resolve_id("t3_ZZ99aa") == "zz99aa"
m = r.COMMENT_RE.search("https://www.reddit.com/r/x/comments/1x6ywou/some_title/ph3hykz/?context=3")
assert m and m.group(1) == "ph3hykz"
assert r.COMMENT_RE.search("https://www.reddit.com/r/x/comments/1x6ywou/some_title/") is None  # post link: whole thread

gallery = {"is_gallery": True, "media_metadata": {"a": {"s": {"u": "https://i.redd.it/a.jpg"}},
                                                  "b": {"s": {"u": "https://i.redd.it/b.png"}}},
           "gallery_data": {"items": [{"media_id": "b"}, {"media_id": "a"}]}}
assert r.media_tag(gallery) == " [media: gallery×2]"
assert r.media_urls(gallery) == ["https://i.redd.it/b.png", "https://i.redd.it/a.jpg"]  # gallery order kept

video = {"secure_media": {"reddit_video": {"fallback_url": "https://v.redd.it/x/CMAF_720.mp4"}}}
assert r.media_tag(video) == " [media: video]" and r.media_urls(video)[0].endswith(".mp4")

text = {"is_self": True, "selftext": "see ![img](https://preview.redd.it/q.png?width=640&amp;s=1) ok"}
assert r.media_tag(text) == " [media: 1 inline image(s)]"
assert r.media_urls(text) == ["https://preview.redd.it/q.png?width=640&amp;s=1"]

assert r.media_tag({"is_self": True, "selftext": "plain"}) == ""
assert r.media_tag({"url": "https://i.redd.it/z.gif", "post_hint": "image"}) == " [media: gif]"

# shared listing filters
from types import SimpleNamespace as NS
f = lambda **k: NS(**{"min_score": -999, "min_comments": 0, "media": None, "no_nsfw": False, **k})
posts = [gallery | {"id": "g", "num_comments": 50, "score": 9}, {"id": "t", "is_self": True, "num_comments": 2,
         "score": 1, "over_18": True}, video | {"id": "v", "num_comments": 10, "score": 3}]
ids = lambda xs: [x["id"] for x in xs]
assert ids(r.filter_posts(posts, f(media="gallery"))) == ["g"]
assert ids(r.filter_posts(posts, f(media="none"))) == ["t"]
assert ids(r.filter_posts(posts, f(media="any", min_comments=20))) == ["g"]
assert ids(r.filter_posts(posts, f(no_nsfw=True, min_score=2))) == ["g", "v"]
assert ids(r.filter_posts([{"id": "c", "body": "x", "score": 5}], f(min_comments=99))) == ["c"]  # comments ignore post-only filters

# comment ordering
c = lambda i, s, t: {"kind": "t1", "data": {"id": i, "score": s, "created_utc": t, "body": i, "replies": ""}}
tree = [c("a", 5, 300), c("b", 50, 100), c("d", 1, 200)]
order = lambda sort: [row[1]["id"] for row in (lambda out: (r.flatten(tree, 0, 3, out, sort), out)[1])([])]
assert order("top") == ["b", "a", "d"] and order("new") == ["a", "d", "b"] and order("old") == ["b", "d", "a"]

# per-command --body-chars defaults must not leak between subcommands (argparse shares parent actions)
import sys
for argv, want in ((["find", "q"], 0), (["user", "x"], 200), (["thread", "abcd"], 1200), (["top", "a"], 0),
                   (["links", "https://example.com"], 200)):
    sys.argv = ["threadsift.py", *argv]
    seen = {}
    real = {k: getattr(r, k) for k in ("cmd_find", "cmd_user", "cmd_thread", "cmd_top", "cmd_links")}
    for k in real:
        setattr(r, k, lambda a, k=k: seen.setdefault("bc", a.body_chars))
    r.main()
    for k, v in real.items():
        setattr(r, k, v)
    assert seen["bc"] == want, (argv, seen)
print("ok")
