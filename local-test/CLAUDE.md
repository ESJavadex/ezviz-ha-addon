# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a local testing environment for the EZVIZ Camera HLS Stream Add-on. It runs the streaming pipeline in Docker on a local Mac for development and testing before deploying to Home Assistant.

## Commands

### Start the local test environment
```bash
./start.sh
```
This builds the Docker image, copies Python files from `../ezviz-camera/`, and starts the container.

### Stop the test environment
```bash
./stop.sh
```
Stops the container and cleans up copied Python files.

### View stream in VLC
Open `http://localhost:8080/stream.m3u8` in VLC after waiting ~30 seconds for buffer to fill.

## Architecture

### Streaming Pipeline
1. `stream_to_pipe.py` connects to EZVIZ VTDU server and outputs raw H.265 video to stdout
2. ffmpeg transcodes to H.264, creates HLS segments (`.ts` files) and playlist (`stream.m3u8`)
3. Python HTTP server serves HLS files on port 8080
4. `run_local.sh` manages auto-reconnection loop when EZVIZ disconnects (~30s timeout)

### EZVIZ Protocol Flow
1. Login to EZVIZ API, get session JWT
2. Get VTM server info and VTDU tokens
3. Connect to VTM, receive VTDU redirect URL
4. Connect to VTDU, send StreamInfoReq protobuf message
5. Receive continuous video stream on channel 0x01

### Key Protocol Details
- VTM packet header: 8 bytes - magic (0x24), channel, length, sequence, message code
- Channel 0x00 = unencrypted messages, 0x01 = unencrypted stream
- EZVIZ enforces ~30 second connection timeout (server-side, cannot be bypassed)

## Configuration

Copy `.env.example` to `.env` and set:
- `EZVIZ_EMAIL` - EZVIZ account email
- `EZVIZ_PASSWORD` - EZVIZ account password
- `EZVIZ_SERIAL` - Camera serial number
- `EZVIZ_REGION` - Region (Europe, Americas, Asia, Russia)
- `HLS_TIME` - Segment duration in seconds
- `HLS_LIST_SIZE` - Number of segments to keep in playlist

## Known Limitations

- EZVIZ disconnects every ~30 seconds - handled via auto-reconnection with seamless HLS segments
- Uses unique session-based segment names to prevent video looping during reconnects
- `discont_start` flag marks discontinuities for player compatibility
