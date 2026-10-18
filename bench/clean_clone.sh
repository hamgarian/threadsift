#!/bin/bash
# Clean-clone check: clone the repo into an empty folder and run the offline tests plus the 9 benchmark tasks
# with the README's commands only. Usage: bash bench/clean_clone.sh <repo url or path> [python command]
set -u
REPO=$1
PY=${2:-python}
DIR=$(mktemp -d)
git clone -q "$REPO" "$DIR/threadsift" && cd "$DIR/threadsift" || exit 1
echo "clone: $(git log --oneline -1)"
T=threadsift.py
run() { local name=$1; shift; local s=$(date +%s); if "$@" > "out_$name" 2>&1; then r=PASS; else r=FAIL; fi
        echo "$r $name ($(( $(date +%s)-s ))s) $(head -c 90 "out_$name" | tr '\n' ' ')"; }
run tests     $PY test_threadsift.py
run doctor    $PY $T doctor
run T1-find   $PY $T find "claude code tips" --limit 10
run T2-find   $PY $T find "secrets manager docker" --sub selfhosted --limit 10
run T3-thread $PY $T thread 1ogtyds --max-comments 500 --depth 10
run T4-top    $PY $T top LocalLLaMA --time week --limit 10
run T5-user   $PY $T user spez --limit 10
run T6-media  $PY $T media 1x8lalp
run T7-links  $PY $T links https://github.com/NousResearch/hermes-agent --limit 10
run T8-trend  $PY $T trend --sub hermesagent --by month --after 2026-03-01
run T9-comment $PY $T thread https://www.reddit.com/r/ClaudeAI/comments/1uc7izy/i_added_a_clause_to_andrej_karpathys_4_claudemd/ot1ybwk/
echo "--- checks"
grep -c '\[media: gallery×4\]' out_T6-media >/dev/null; echo "T6 files: $(grep -c '\.jpg' out_T6-media)"
echo "T9 target shown: $(grep -c 'I like the intent' out_T9-comment), other top-level shown: $(grep -c itprobablynothingbut out_T9-comment)"
echo "T1 results with scores: $(grep -cE '\[[0-9]+↑' out_T1-find)"
rm -rf "$DIR"
