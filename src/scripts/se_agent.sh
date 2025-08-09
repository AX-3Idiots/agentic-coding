#!/usr/bin/env bash
set -e
echo "Cloning $GIT_URL..."
if [[ -n "$GITHUB_TOKEN" ]]; then
    GIT_URL_WITH_TOKEN=$(echo "$GIT_URL" | sed "s|https://|https://oauth2:${GITHUB_TOKEN}@|")
    git clone "$GIT_URL_WITH_TOKEN" project
else
    git clone "$GIT_URL" project
fi
cd project
echo "Running Claude-Code..."
error_log=$(mktemp)
trap 'rm -f "$error_log"' EXIT # Clean up on exit

# Run the claude command and check its exit status
if ! result=$(timeout "$TIME_OUT" claude -p "$USER_INPUT" --append-system-prompt "$SYSTEM_PROMPT" --output-format json 2> "$error_log"); then
    error_content=$(cat "$error_log")
    echo "Error: The 'claude' command failed." >&2
    echo "--- Stderr ---" >&2
    echo "$error_content" >&2

    if [[ -n "$result" ]]; then
        echo "--- Stdout ---" >&2
        echo "$result" >&2
    fi

    full_error_message="Stderr: $error_content\nStdout: $result"
    jq -n --arg error "$full_error_message" '{code: null, cost_usd: null, error: $error}'
    exit 1
fi

# At the end of the script, output the final result as a single JSON line
# so it can be captured by the container logs.
echo "$result" | jq -c '{code: .result, cost_usd: .total_cost_usd}'