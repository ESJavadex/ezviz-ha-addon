# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant add-on that streams EZVIZ cameras via HLS. Primary target platform is **Raspberry Pi 4** running Home Assistant OS. The addon reverse-engineers the EZVIZ proprietary protocol to capture unencrypted video streams without cloud dependencies.

## Architecture

### Streaming Pipeline
1. `ezviz_stream.py` - EZVIZ protocol implementation (API auth, VTM/VTDU connection)
2. `stream_to_pipe.py` - Connects to VTDU, outputs raw H.265 video to stdout
3. `run.sh` - Orchestrates pipeline: Python → ffmpeg (H.265→H.264) → HLS segments
4. Python HTTP server serves HLS on port 8080

### EZVIZ Protocol Flow
1. Login to EZVIZ API (`/v3/users/login/v5`), receive session JWT
2. Get server info for AUTH_URL
3. Request VTDU tokens from AUTH_URL
4. Connect to VTM server, send StreamInfoReq, receive VTDU redirect
5. Connect to VTDU, receive continuous video on channel 0x01

### VTM Packet Format
- 8-byte header: magic (0x24), channel, length (u16), sequence (u16), message code (u16)
- Channel 0x00 = messages, 0x01 = video stream
- MSG_STREAMINFO_REQ = 0x13b, MSG_KEEPALIVE_REQ = 0x135

### HLS Configuration
- `append_list+omit_endlist+discont_start` flags for seamless reconnection
- Unique segment names per session prevent video looping during reconnects
- Transcodes HEVC to H.264 for browser compatibility

## Key Limitations

- **EZVIZ enforces ~30 second connection timeout** (server-side, cannot be bypassed)
- Handled via auto-reconnection loop with 0.5s restart delay
- Keepalive packets (0x135) are rejected by server - do not attempt

## Local Development

### Test without Home Assistant
```bash
cd local-test
cp .env.example .env  # Edit with your credentials
./start.sh            # Start Docker container
# Stream at http://localhost:8080/stream.m3u8
./stop.sh             # Cleanup
```

### Deploy to Home Assistant
1. Push changes to GitHub
2. In HA: Settings → Add-ons → Repositories → Refresh
3. Reinstall/update the add-on

## File Structure

```
ezviz-camera/           # The actual HA add-on
├── config.yaml         # Add-on metadata, options schema
├── build.yaml          # Docker base images per architecture
├── Dockerfile          # Container build (Alpine + ffmpeg + Python)
├── run.sh              # Main entrypoint, streaming loop
├── ezviz_stream.py     # EZVIZ API/protocol library
└── stream_to_pipe.py   # Stream capture to stdout

local-test/             # Development environment
├── docker-compose.yml
├── .env.example
└── start.sh/stop.sh
```

## Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| email | string | EZVIZ account email |
| password | password | EZVIZ account password |
| serial | string | Camera serial number |
| region | list | Europe, Americas, Asia, Russia |
| hls_time | int(1-10) | Segment duration in seconds |
| hls_list_size | int(5-20) | Segments in playlist |
