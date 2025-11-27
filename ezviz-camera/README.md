# EZVIZ Camera HLS Stream Add-on

Stream your EZVIZ camera directly to Home Assistant using HLS (HTTP Live Streaming) with automatic reconnection.

## Features

- HLS streaming with H.265/HEVC codec support
- Automatic reconnection when stream drops (every ~27 seconds)
- Runs 24/7 on your Home Assistant OS
- Configurable via Home Assistant UI
- No external dependencies needed

## Installation

### Method 1: Local Add-on (Recommended for Testing)

1. Copy the `ezviz-camera-addon` folder to your Home Assistant:
   ```bash
   scp -r ezviz-camera-addon root@YOUR_HA_IP:/addons/
   ```

2. In Home Assistant, go to **Settings** > **Add-ons** > **Add-on Store**

3. Click the three dots menu (top right) > **Repositories**

4. Add your local repository: `/addons/ezviz-camera-addon`

5. Find "EZVIZ Camera HLS Stream" in the add-on store and click **INSTALL**

### Method 2: Manual Installation via SSH/Terminal

1. Access Home Assistant via SSH or Terminal add-on

2. Create addon directory:
   ```bash
   mkdir -p /addons/local/ezviz-camera-addon
   ```

3. Copy all files from this folder to `/addons/local/ezviz-camera-addon/`

4. Restart Home Assistant or reload add-ons

## Configuration

After installation, configure the add-on with your EZVIZ credentials:

```yaml
email: your-ezviz-email@example.com
password: your-ezviz-password
serial: YOUR_CAMERA_SERIAL
region: Europe  # Options: Europe, Americas, Asia, Russia
hls_time: 2  # Segment duration in seconds (1-10)
hls_list_size: 10  # Number of segments to keep (5-20)
```

### Configuration Options

- **email** (required): Your EZVIZ account email
- **password** (required): Your EZVIZ account password
- **serial** (required): Your camera's serial number (found on the camera or in the EZVIZ app)
- **region** (optional): Your EZVIZ region, default: "Europe"
  - Options: `Europe`, `Americas`, `Asia`, `Russia`
- **hls_time** (optional): HLS segment duration in seconds, default: 2
  - Range: 1-10 seconds
  - Lower = more responsive but more CPU usage
- **hls_list_size** (optional): Number of HLS segments to keep, default: 10
  - Range: 5-20 segments
  - Higher = more buffer but more storage

## Usage

1. **Start the add-on** from the Add-on page

2. **Check the logs** to ensure it's streaming correctly:
   - You should see "Starting stream..." messages
   - The stream will auto-restart every ~27 seconds (this is normal)

3. **Add the camera to Home Assistant**:

   Edit your `configuration.yaml`:
   ```yaml
   camera:
     - platform: ffmpeg
       name: EZVIZ Camera
       input: http://YOUR_HA_IP:8080/stream.m3u8
   ```

   Or use the generic camera integration via UI:
   - Go to **Settings** > **Devices & Services**
   - Click **+ ADD INTEGRATION**
   - Search for "Generic Camera"
   - Stream URL: `http://YOUR_HA_IP:8080/stream.m3u8`

4. **Restart Home Assistant** to load the camera

## Troubleshooting

### Add-on won't start
- Check the logs for error messages
- Verify your EZVIZ credentials are correct
- Ensure your camera serial number is correct

### Stream not working
- Check that port 8080 is not blocked
- Verify the stream URL is accessible: `http://YOUR_HA_IP:8080/stream.m3u8`
- Check add-on logs for connection errors

### Camera not appearing in Home Assistant
- Restart Home Assistant after adding camera configuration
- Check Home Assistant logs for FFmpeg errors
- Verify the stream URL is correct

### Stream keeps disconnecting
- This is normal! EZVIZ closes the connection every ~27 seconds
- The add-on automatically restarts the stream
- Home Assistant's FFmpeg integration should handle this automatically

## Technical Details

- **Protocol**: HLS (HTTP Live Streaming)
- **Codec**: H.265/HEVC
- **Resolution**: 1920x1080
- **Frame Rate**: 15fps
- **Port**: 8080 (HTTP)
- **Auto-restart**: Yes

## Support

For issues or questions, check the add-on logs first. The logs will show:
- Connection status
- Stream restarts
- Any error messages from EZVIZ or FFmpeg

## License

This add-on is provided as-is for personal use.
