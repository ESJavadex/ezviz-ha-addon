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

# Main streaming loop with auto-restart
RESTART_COUNT=0
while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))
    bashio::log.info "[${RESTART_COUNT}] Starting stream..."

    # Clean old segments
    rm -f /share/ezviz_hls/*.ts /share/ezviz_hls/*.m3u8

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
        -keyint_min 30 \
        -force_key_frames "expr:gte(t,n_forced*2)" \
        -f hls \
        -hls_time "${HLS_TIME}" \
        -hls_list_size "${HLS_LIST_SIZE}" \
        -hls_flags delete_segments+append_list \
        -hls_segment_filename '/share/ezviz_hls/segment%d.ts' \
        /share/ezviz_hls/stream.m3u8 2>&1

    # Stream ended, quick restart to minimize gap
    bashio::log.warning "Stream ended. Restarting in 2 seconds..."
    sleep 2
done
