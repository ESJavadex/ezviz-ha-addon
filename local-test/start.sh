#!/bin/bash

# Local EZVIZ Stream Test - Start Script
# Usage: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDON_DIR="$(dirname "$SCRIPT_DIR")/ezviz-camera"

echo "============================================"
echo "EZVIZ Local Stream Test"
echo "============================================"
echo ""

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Creating .env file from template..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo ""
    echo "Please edit .env file with your credentials:"
    echo "  $SCRIPT_DIR/.env"
    echo ""
    exit 1
fi

# Copy Python files from ezviz-camera to local-test
echo "Copying Python files from addon..."
cp "$ADDON_DIR/ezviz_stream.py" "$SCRIPT_DIR/"
cp "$ADDON_DIR/stream_to_pipe.py" "$SCRIPT_DIR/"
echo "✓ Files copied"
echo ""

# Build and start Docker container
echo "Building and starting Docker container..."
cd "$SCRIPT_DIR"
docker compose up --build

# Cleanup on exit
echo ""
echo "Cleaning up copied files..."
rm -f "$SCRIPT_DIR/ezviz_stream.py" "$SCRIPT_DIR/stream_to_pipe.py"
