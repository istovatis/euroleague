#!/bin/bash
# Publish one story to every Instagram account (EN, then EL) and commit the publish records.
# Usage: scripts/publish_story.sh rounds/E2026/round-06/02-vezenkov [--dry-run]
# Safe to re-run: publish_instagram.py refuses to post a story twice to the same account.
set -u
cd "$(dirname "$0")/.."
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin"
story=$1
flag=--yes
[ "${2:-}" = "--dry-run" ] && flag=

echo "== $(date '+%Y-%m-%d %H:%M:%S %Z') publishing $story ${flag:-(dry run)}"
status=0
for lang in en el; do
  python3 scripts/publish_instagram.py "$story" "$lang" $flag || status=1
done

if [ -n "$flag" ] && ls "$story"/published.*.json >/dev/null 2>&1; then
  git add "$story"/published.*.json
  if ! git diff --cached --quiet; then
    git commit -q -m "Published $(basename "$story") on Instagram

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q origin main || echo "warning: could not push the publish record"
  fi
fi
echo "== done (exit $status)"
exit $status
