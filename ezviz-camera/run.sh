#!/usr/bin/with-contenv bashio

# Get configuration from options
EMAIL=$(bashio::config 'email')
PASSWORD=$(bashio::config 'password')
SERIAL=$(bashio::config 'serial')
REGION=$(bashio::config 'region')
HLS_TIME=$(bashio::config 'hls_time')
HLS_LIST_SIZE=$(bashio::config 'hls_list_size')

# Create HLS directory
mkdir -p /share/ezviz_hls

bashio::log.info "Starting EZVIZ Camera HLS Stream..."
bashio::log.info "Email: ${EMAIL}"
bashio::log.info "Serial: ${SERIAL}"
bashio::log.info "Region: ${REGION}"

# Function to start HTTP server
start_http_server() {
    python3 /app/http_server.py --port 8080 --directory /share/ezviz_hls &
    HTTP_PID=$!
    bashio::log.info "HTTP server (CORS enabled) started on port 8080 (PID: ${HTTP_PID})"
}

# Function to check and restart HTTP server if needed
check_http_server() {
    if ! kill -0 "$HTTP_PID" 2>/dev/null; then
        bashio::log.warning "HTTP server died, restarting..."
        start_http_server
    fi
}

# Start HTTP server with CORS support in background
cd /share/ezviz_hls
start_http_server

# Print access instructions
bashio::log.info "============================================"
bashio::log.info "HLS Stream URL: http://homeassistant.local:8080/stream.m3u8"
bashio::log.info ""
bashio::log.info "To add camera in Home Assistant UI:"
bashio::log.info "1. Go to Settings -> Devices & Services"
bashio::log.info "2. Add Integration -> Generic Camera"
bashio::log.info "3. Stream Source: http://homeassistant.local:8080/stream.m3u8"
bashio::log.info "4. Or use your HA IP: http://<HA_IP>:8080/stream.m3u8"
bashio::log.info "============================================"

# Clean start - only on first boot
rm -f /share/ezviz_hls/*.ts /share/ezviz_hls/*.m3u8

# Use timestamp for unique session IDs
TIMESTAMP=$(date +%s)

# Main streaming loop with auto-restart
RESTART_COUNT=0
while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))
    bashio::log.info "[${RESTART_COUNT}] Starting stream..."

    # Unique segment prefix per session to avoid overwrites during reconnect
    SESSION_ID="${TIMESTAMP}_${RESTART_COUNT}"

    # Start streaming (stderr goes to log, stdout pipes to ffmpeg)
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
        -hls_segment_filename "/share/ezviz_hls/seg_${SESSION_ID}_%03d.ts" \
        /share/ezviz_hls/stream.m3u8 2>&1

    # Clean up old segments (keep last 30)
    ls -1t /share/ezviz_hls/*.ts 2>/dev/null | tail -n +31 | xargs -r rm -f

    # Check if HTTP server is still alive, restart if needed
    check_http_server

    # Stream ended, quick restart
    bashio::log.warning "Stream ended. Quick restart..."
    sleep 0.5
done
