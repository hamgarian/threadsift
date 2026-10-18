#!/bin/bash
# Re-measure the access facts the README states. Writes a log; takes ~5 min (RSS waits). Needs curl, python.
# Usage: bash bench/probe.sh > bench/probe-<date>.log
UA="threadsift-probe"
B=https://arctic-shift.photon-reddit.com
TMP=$(mktemp -d)
echo "# probe run $(date -u +%Y-%m-%dT%H:%MZ)"

echo "## 1. Anonymous JSON endpoints (expect 403) and old.reddit (expect redirect to login)"
for u in "https://www.reddit.com/r/LocalLLaMA/top.json?t=week&limit=2" "https://www.reddit.com/search.json?q=test&limit=2" \
         "https://api.reddit.com/r/LocalLLaMA/hot?limit=2"; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$u")  $u"; done
echo "$(curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}' -A "$UA" "https://old.reddit.com/r/LocalLLaMA/top.json?limit=1")"

echo "## 2. RSS rate limit: 6 requests ~4s apart (expect 200, then 429s until the clock minute turns, then 200)"
sleep 61
for i in 1 2 3 4 5 6; do
  h=$(curl -s -o /dev/null -D - -A "$UA" "https://www.reddit.com/r/LocalLLaMA/new.rss?limit=1&n=$i" | tr -d '\r')
  echo "$(date -u +%H:%M:%S) $(echo "$h" | head -1 | cut -d' ' -f2) $(echo "$h" | grep -i '^x-ratelimit' | tr '\n' ' ')"
  sleep 4
done

echo "## 3. Arctic Shift capture lag: newest post and comment in r/AskReddit (created -> retrieved_on)"
for k in posts comments; do
  curl -s "$B/api/$k/search?subreddit=AskReddit&limit=1&sort=desc&fields=id,created_utc,retrieved_on" | python -c "
import json,sys,time; d=json.load(sys.stdin).get('data') or []
print('$k', 'unavailable (archive busy)' if not d else f\"captured {d[0]['retrieved_on']-d[0]['created_utc']}s after posting; newest is {int(time.time())-d[0]['created_utc']}s old\")"
  sleep 2
done

echo "## 4. Reddit-hosted video: video file and audio playlist, using the URLs from each post's metadata"
echo "##    (newer posts: signed packaged-media.redd.it video + signed hls_url; older posts: v.redd.it)"
curl -s "$B/api/posts/search?subreddit=nextfuckinglevel&limit=60&sort=desc" > "$TMP/recent.json"
curl -s "$B/api/posts/search?subreddit=nextfuckinglevel&before=2026-05-01&limit=60&sort=desc" > "$TMP/older.json"
python -c "
import json, sys
for label in ('recent', 'older'):
    n = 0
    for p in json.load(open(sys.argv[1] + '/' + label + '.json', encoding='utf-8')).get('data') or []:
        v = (p.get('secure_media') or p.get('media') or {}).get('reddit_video')
        if v and v.get('hls_url') and n < 5:
            n += 1
            print(label, p['id'], v['fallback_url'].replace('&amp;', '&'), v['hls_url'].replace('&amp;', '&'))
" "$TMP" | tr -d '\r' > "$TMP/videos.txt"
while read -r label id video hls; do
  echo "$label $id video=$(curl -s -o /dev/null -r 0-1000 -w '%{http_code}' -A "$UA" "$video") audio_playlist=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$hls")"
done < "$TMP/videos.txt"
rm -rf "$TMP"
echo "# done"
