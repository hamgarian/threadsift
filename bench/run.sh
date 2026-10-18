#!/bin/bash
# Reproduce the README comparison: the same 9 tasks (tasks.json) for 5 tools, no credentials.
# The tools run one at a time with pauses, because they all share one IP's 1-call-per-minute Reddit RSS quota.
# Failed tasks are retried once after 90s. Takes ~30-40 min. Needs: node, npx, uv, curl.
# Results land in ./results/; summarize with: python summarize.py results
set -u
cd "$(dirname "$0")"
mkdir -p results && cd results
OURS=../../threadsift.py
MCP=../mcp.mjs
HERMES_SHA=d76cce4f1161bdac895f7e373ce41cbd04e7c2f2  # NousResearch/hermes-agent reddit-reading skill, MIT
curl -sSfo hermes_reddit.py "https://raw.githubusercontent.com/NousResearch/hermes-agent/$HERMES_SHA/optional-skills/social-media/reddit-reading/scripts/reddit.py"

mcp_tool() { # name, launch json
  python -c "import json;json.dump(json.load(open('../tasks.json'))['$1'],open('calls_$1.json','w'))"
  timeout 1200 node $MCP "$2" calls_$1.json 2>/dev/null > out_$1.json
  python -c "
import json
calls={c['task']:c for c in json.load(open('calls_$1.json'))}
failed=[r['task'] for r in json.load(open('out_$1.json',encoding='utf-8')) if r['error']]
json.dump([calls[t] for t in failed],open('retry_$1.json','w'))"
  sleep 90
  timeout 1200 node $MCP "$2" retry_$1.json 2>/dev/null > retry_out_$1.json
  sleep 60
}

cli() { # tool, task, command...
  local tool=$1 task=$2; shift 2
  local s=$(date +%s%N)
  "$@" > ${tool}_$task.out 2> ${tool}_$task.err; local code=$?
  echo "{\"tool\":\"$tool\",\"task\":\"$task\",\"exit\":$code,\"ms\":$(( ($(date +%s%N)-s)/1000000 ))}" >> cli_runs.jsonl
}

rm -f cli_runs.jsonl
mcp_tool buddy '["npx","-y","reddit-mcp-buddy@1.1.14"]'
mcp_tool elias '["uvx","--with","httpx","reddit-no-auth-mcp-server"]'  # httpx: missing from the package's deps
mcp_tool arctic '["npx","-y","arctic-shift-mcp@1.0.2"]'

H="python hermes_reddit.py --json"
cli hermes T1 $H search "claude code tips" --limit 10
cli hermes T2 $H search "secrets manager docker" --sub selfhosted --limit 10
cli hermes T3 $H thread https://www.reddit.com/r/selfhosted/comments/1ogtyds/managing_secrets_and_credentials_in_docker_best/ --limit 500
cli hermes T4 $H sub LocalLLaMA --sort top --time week --limit 10
cli hermes T5 $H user spez --limit 10
cli hermes T6 $H thread https://www.reddit.com/r/homelab/comments/1x8lalp/enterprise_n00b/
cli hermes T7 $H search "url:github.com/NousResearch/hermes-agent" --limit 10
cli hermes T9 $H thread https://www.reddit.com/r/ClaudeAI/comments/1uc7izy/i_added_a_clause_to_andrej_karpathys_4_claudemd/ot1ybwk/
sleep 60

O="python $OURS"
cli ours T1 $O find "claude code tips" --limit 10 --no-cache --format json
cli ours T2 $O find "secrets manager docker" --sub selfhosted --limit 10 --no-cache --format json
cli ours T3 $O thread 1ogtyds --max-comments 500 --depth 10 --no-cache --format json
cli ours T4 $O top LocalLLaMA --time week --limit 10 --no-cache --format json
cli ours T5 $O user spez --limit 10 --no-cache --format json
cli ours T6 $O media 1x8lalp --no-cache
cli ours T7 $O links https://github.com/NousResearch/hermes-agent --limit 10 --no-cache --format json
cli ours T8 $O trend --sub hermesagent --by month --after 2026-03-01 --no-cache --format json
cli ours T9 $O thread https://www.reddit.com/r/ClaudeAI/comments/1uc7izy/i_added_a_clause_to_andrej_karpathys_4_claudemd/ot1ybwk/ --no-cache --format json

# T4 ground truth: Reddit's own top-of-week list, fetched straight from Reddit (one more RSS call)
sleep 60
curl -s -A "threadsift-bench" "https://www.reddit.com/r/LocalLLaMA/top.rss?t=week&limit=25" > reference_top_week.xml
# T7 ground truth: every archived post whose link (url field) is the repo
curl -s "https://arctic-shift.photon-reddit.com/api/posts/search?url=https://github.com/NousResearch/hermes-agent&limit=100&fields=id" > reference_links.json
echo done
