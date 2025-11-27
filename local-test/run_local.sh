#!/bin/bash

# Get credentials from environment
EMAIL="${EZVIZ_EMAIL}"
PASSWORD="${EZVIZ_PASSWORD}"
SERIAL="${EZVIZ_SERIAL}"
REGION="${EZVIZ_REGION:-Europe}"
HLS_TIME="${HLS_TIME:-2}"
HLS_LIST_SIZE="${HLS_LIST_SIZE:-10}"

echo "============================================"
echo "EZVIZ Local Stream Test"
echo "============================================"
echo "Email: ${EMAIL}"
echo "Serial: ${SERIAL}"
echo "Region: ${REGION}"
echo ""

# Start HTTP server in background
cd /hls
python3 -m http.server 8080 &
HTTP_PID=$!
echo "HTTP server started on port 8080"

echo ""
echo "============================================"
echo "Stream URL for VLC:"
echo "  http://localhost:8080/stream.m3u8"
echo "============================================"
echo ""

# Main streaming loop
RESTART_COUNT=0
while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))
    echo "[${RESTART_COUNT}] Starting stream..."

    # Clean old segments
    rm -f /hls/*.ts /hls/*.m3u8

    # Start streaming
    python3 -u /app/stream_to_pipe.py \
        --email "${EMAIL}" \
        --password "${PASSWORD}" \
        --serial "${SERIAL}" \
        --region "${REGION}" | \
    ffmpeg -re -i pipe:0 \
        -c:v libx264 \
        -preset ultrafast \
        -tune zerolatency \
        -crf 23 \
        -f hls \
        -hls_time "${HLS_TIME}" \
        -hls_list_size "${HLS_LIST_SIZE}" \
        -hls_flags delete_segments+append_list \
        -hls_segment_filename '/hls/segment%d.ts' \
        /hls/stream.m3u8 2>&1

    echo "Stream ended. Restarting in 5 seconds..."
    sleep 5
done
