#!/bin/bash

# Get credentials from environment
EMAIL="${EZVIZ_EMAIL}"
PASSWORD="${EZVIZ_PASSWORD}"
SERIAL="${EZVIZ_SERIAL}"
REGION="${EZVIZ_REGION:-Europe}"
HLS_TIME="${HLS_TIME:-4}"
HLS_LIST_SIZE="${HLS_LIST_SIZE:-20}"

echo "============================================"
echo "EZVIZ Local Stream Test (Buffered)"
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
echo ""
echo "TIP: Wait 30s after start before opening VLC"
echo "============================================"
echo ""

# Clean start
rm -f /hls/*.ts /hls/*.m3u8

# Use timestamp-based segment names to avoid overwrites
TIMESTAMP=$(date +%s)

# Main streaming loop
RESTART_COUNT=0
while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))
    echo "[${RESTART_COUNT}] Starting stream..."

    # Use unique segment prefix per session to avoid conflicts
    SESSION_ID="${TIMESTAMP}_${RESTART_COUNT}"

    # Stream with unique segment names per session
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
        -g 30 \
        -f hls \
        -hls_time "${HLS_TIME}" \
        -hls_list_size "${HLS_LIST_SIZE}" \
        -hls_flags append_list+omit_endlist+discont_start \
        -hls_segment_filename "/hls/seg_${SESSION_ID}_%03d.ts" \
        /hls/stream.m3u8 2>&1

    echo "Stream ended. Quick restart..."

    # Clean up old segments (keep last 30)
    ls -1t /hls/*.ts 2>/dev/null | tail -n +31 | xargs -r rm -f

    sleep 0.5
done
