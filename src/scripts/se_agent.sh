#!/usr/bin/env bash
set -e
echo "Cloning $GIT_URL..."
if [[ -z "$GITHUB_TOKEN" || -z "$GIT_URL" ]]; then
  echo "Error: GITHUB_TOKEN or GIT_URL is not set" >&2; exit 1
fi
CLEAN_URL="${GIT_URL#http://}"; CLEAN_URL="${CLEAN_URL#https://}"
AUTH_URL="https://x-access-token:${GITHUB_TOKEN}@${CLEAN_URL}"
git clone "$AUTH_URL" project
cd project
# Configure Git user details
git config --global user.name "Agentic-Coding-app"
git config --global user.email "$INSTALLATION_ID+Agentic-Coding-app@users.noreply.github.com"

# Set the remote URL to include the GitHub App token
git remote set-url origin "$AUTH_URL"

echo "Running Claude-Code..."

# Create a temporary file to store the output with .log extension
output_log=$(mktemp)
trap 'rm -f "$output_log"' EXIT # Clean up on exit

# Run the claude command and capture combined output, then check exit status
if ! timeout "$TIME_OUT" claude --verbose -p "$USER_INPUT" --system-prompt "$SYSTEM_PROMPT" --output-format json 2>"$output_log"; then
    echo "Error: The 'claude' command failed." >&2
    echo "--- Full output ---" >&2
    cat "$output_log" >&2
    jq -n --arg error_msg "$(cat "$output_log")" '{code: null, cost_usd: null, error: $error_msg}'
    exit 1
fi

cd ~/.claude/projects

# Always cd into the "-workspace-project" directory
if [[ ! -d "-workspace-project" ]]; then
  echo "Error: Directory '-workspace-project' not found in $(pwd)" >&2
  exit 1
fi
cd -- -workspace-project

# If the directory has exactly one regular file, jq that file
files_list=$(find . -maxdepth 1 -type f -print 2>/dev/null | sed '/^$/d')
files_count=$(printf '%s\n' "$files_list" | sed '/^$/d' | wc -l | tr -d ' ')
if [[ "$files_count" == "1" ]]; then
  only_file=$(printf '%s\n' "$files_list" | head -n1)
  jq -c '{type, message, timestamp}' "$only_file"
fi

# Print the final summarized result via jq only
jq -c '{code: .result, cost_usd: .total_cost_usd}' "$output_log"