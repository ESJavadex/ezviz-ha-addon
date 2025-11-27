#!/bin/bash

# Stop the local test container

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping EZVIZ local test..."
cd "$SCRIPT_DIR"
docker compose down

# Cleanup copied files
rm -f "$SCRIPT_DIR/ezviz_stream.py" "$SCRIPT_DIR/stream_to_pipe.py"

echo "✓ Stopped"
