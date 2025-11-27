#!/usr/bin/env python3
"""
Stream EZVIZ camera to a named pipe for MediaMTX
"""

import socket
import sys
import os
import struct
import threading
import time
from ezviz_stream import EzvizCamera, EzvizConfig, VTMPacket

def send_keepalive(sock, stop_event, interval=20):
    """Send keepalive packets periodically to prevent VTDU timeout"""
    seq = 0
    while not stop_event.is_set():
        # Wait first, then send keepalive
        stop_event.wait(interval)
        if stop_event.is_set():
            break

        try:
            # Send minimal keepalive - just the 8-byte header with no payload
            # Use stream channel (0x01) to keep stream connection alive
            header = struct.pack(
                '>BBHHH',
                0x24,  # Magic byte
                0x01,  # Stream channel
                0,     # Length (no payload)
                seq,   # Sequence
                0x135  # Keepalive request
            )
            sock.sendall(header)
            seq = (seq + 1) % 65536
            print(f"Keepalive sent (seq={seq})", file=sys.stderr)
        except Exception as e:
            print(f"Keepalive failed: {e}", file=sys.stderr)
            break


def stream_to_pipe(email, password, serial, pipe_path, region="Europe"):
    """Stream EZVIZ camera to a named pipe"""

    print("=" * 60, file=sys.stderr)
    print("EZVIZ to Pipe Streamer", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Connect to camera
    print("\n[1/3] Connecting to EZVIZ...", file=sys.stderr)
    camera = EzvizCamera(email, password, serial, region)
    camera.connect()
    print("✓ Connected\n", file=sys.stderr)

    # Get stream info
    print("[2/3] Getting stream information...", file=sys.stderr)
    vtdu_ip, vtdu_port, vtdu_url = camera._get_stream_info()
    print(f"✓ VTDU: {vtdu_ip}:{vtdu_port}\n", file=sys.stderr)

    # Connect to VTDU
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)

    # Enable TCP keepalive at OS level
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    # Linux TCP keepalive settings (Docker runs on Linux)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)   # Start after 10s idle
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)  # Probe every 5s
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)    # 6 probes before giving up
    except (AttributeError, OSError):
        pass  # macOS uses different constants

    try:
        sock.connect((vtdu_ip, vtdu_port))

        # Send stream request using the VTDU URL from VTM redirect
        request = camera._create_stream_request(vtdu_url)
        sock.sendall(request)

        # Read response header
        header = sock.recv(8)
        print(f"Initial response: {header.hex()}", file=sys.stderr)

        # Parse and read response body
        try:
            magic, channel, length, seq, msg_code = camera._parse_header(header)
            if length > 0:
                response_body = sock.recv(length)
                print(f"Read {len(response_body)} bytes of response", file=sys.stderr)
        except ValueError as e:
            print(f"Warning: {e}", file=sys.stderr)

        print("\n" + "=" * 60, file=sys.stderr)
        print("✓ STREAMING TO PIPE!", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"\nPipe: {pipe_path}", file=sys.stderr)
        print("\nPress Ctrl+C to stop\n", file=sys.stderr)

        # Keepalive disabled - EZVIZ rejects all keepalive packet formats
        # Using continuous HLS segments for seamless reconnection instead
        stop_keepalive = threading.Event()
        keepalive_thread = None
        print("Streaming (reconnects every ~30s)", file=sys.stderr)

        # Stream loop - write to stdout (which will be piped)
        packet_count = 0
        while True:
            # Read packet header
            header = sock.recv(8)
            if len(header) < 8:
                print(f"\n✗ Connection closed: received only {len(header)} bytes", file=sys.stderr)
                break

            try:
                magic, channel, length, seq, msg_code = camera._parse_header(header)
            except ValueError:
                # Not a valid header, continuation data - skip
                continue

            # Read packet data
            data = b''
            remaining = length
            while remaining > 0:
                chunk = sock.recv(min(remaining, 8192))
                if not chunk:
                    break
                data += chunk
                remaining -= len(chunk)

            # Send stream data to stdout (channel 0x01 = unencrypted stream)
            if channel == 0x01 and len(data) > 0:
                try:
                    # Write directly to stdout (binary mode)
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    packet_count += 1

                    if packet_count % 100 == 0:
                        print(f"Streaming... {packet_count} packets", file=sys.stderr)
                except BrokenPipeError:
                    print("\nPipe closed", file=sys.stderr)
                    break

    except KeyboardInterrupt:
        print("\n\nStopped by user", file=sys.stderr)
    except socket.timeout:
        print("\n✗ Socket timeout - no data received", file=sys.stderr)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up...", file=sys.stderr)
        # Stop keepalive thread if running
        try:
            stop_keepalive.set()
            if keepalive_thread:
                keepalive_thread.join(timeout=1)
        except:
            pass
        try:
            sock.close()
        except:
            pass
        print("✓ Stream ended", file=sys.stderr)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Stream EZVIZ to pipe for MediaMTX')
    parser.add_argument('--email', required=True, help='EZVIZ email')
    parser.add_argument('--password', required=True, help='EZVIZ password')
    parser.add_argument('--serial', required=True, help='Camera serial')
    parser.add_argument('--region', default='Europe', help='Region')
    parser.add_argument('--pipe', default='/tmp/ezviz_stream', help='Output pipe path')

    args = parser.parse_args()

    try:
        stream_to_pipe(args.email, args.password, args.serial, args.pipe, args.region)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
