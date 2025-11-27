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

# Start HTTP server in background
cd /share/ezviz_hls
python3 -m http.server 8080 &
HTTP_PID=$!
bashio::log.info "HTTP server started on port 8080 (PID: ${HTTP_PID})"

# Main streaming loop with auto-restart
RESTART_COUNT=0
while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))
    bashio::log.info "[${RESTART_COUNT}] Starting stream..."

    # Clean old segments
    rm -f /share/ezviz_hls/*.ts /share/ezviz_hls/*.m3u8

    # Start streaming
    python3 -u /app/stream_to_pipe.py \
        --email "${EMAIL}" \
        --password "${PASSWORD}" \
        --serial "${SERIAL}" \
        --region "${REGION}" 2>&1 | \
    ffmpeg -re -i pipe:0 \
        -c:v copy \
        -f hls \
        -hls_time "${HLS_TIME}" \
        -hls_list_size "${HLS_LIST_SIZE}" \
        -hls_flags delete_segments+append_list \
        -hls_segment_filename '/share/ezviz_hls/segment%d.ts' \
        /share/ezviz_hls/stream.m3u8 2>&1 | grep --line-buffered "frame="

    # Stream ended, wait before restart
    bashio::log.warning "Stream ended. Restarting in 5 seconds..."
    sleep 5
done
