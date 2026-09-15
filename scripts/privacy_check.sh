#!/usr/bin/env bash
# Local privacy gate. Keep the concrete denylist out of the repository.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATTERN_FILE="${GITPULSE_PRIVACY_DENYLIST:-$HOME/.config/gitpulse/privacy-denylist.txt}"

if [[ ! -f "$PATTERN_FILE" ]]; then
  mkdir -p "$(dirname "$PATTERN_FILE")"
  cat > "$PATTERN_FILE" <<'EOF'
# one regex per line, case-insensitive; comments and blanks ignored
# populate locally — never commit this file into the public repository
EOF
  echo "privacy-check: denylist missing, wrote empty template at $PATTERN_FILE"
  echo "privacy-check: ok (empty denylist)"
  exit 0
fi

patterns=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  patterns+=("$line")
done < "$PATTERN_FILE"

if [[ ${#patterns[@]} -eq 0 ]]; then
  echo "privacy-check: ok (empty denylist)"
  exit 0
fi

joined="$(IFS='|'; echo "${patterns[*]}")"
hits="$(rg -in --glob '!.git/**' --glob '!dist/**' --glob '!**/node_modules/**' --glob '!**/.venv/**' -e "$joined" "$ROOT" || true)"
if [[ -n "$hits" ]]; then
  echo "privacy-check: FAILED — forbidden mentions found:" >&2
  echo "$hits" >&2
  exit 1
fi
echo "privacy-check: ok"
