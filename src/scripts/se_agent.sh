#!/usr/bin/env bash
set -e
echo "Cloning $GIT_URL..."
git clone "$GIT_URL" project
cd project
echo "Running Claude-Code..."
# Create a temporary file to store error output
error_log=$(mktemp)

# Run the claude command and check its exit status
if ! result=$(timeout "$TIME_OUT" claude -p "$USER_INPUT" --system-prompt "$SYSTEM_PROMPT" --output-format json 2> "$error_log"); then
    echo "Error: The 'claude' command failed." >&2
    echo "--- Error Log ---" >&2
    cat "$error_log" >&2
    rm "$error_log" # Clean up the temporary file
    exit 1
fi

rm "$error_log" # Clean up the temporary file on success

code=$(echo "$result" | jq -r '.code')
cost=$(echo "$result" | jq -r '.cost_usd')