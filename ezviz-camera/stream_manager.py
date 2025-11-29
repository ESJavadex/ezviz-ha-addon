#!/usr/bin/env python3
"""
On-demand stream manager for EZVIZ cameras.
Starts streaming only when requested, stops after idle timeout to save battery.
"""

import http.server
import socketserver
import os
import sys
import time
import threading
import subprocess
import signal
import urllib.parse
import argparse
from pathlib import Path


class StreamManager:
    """Manages the streaming pipeline lifecycle"""

    def __init__(self, email, password, serial, region, hls_time, hls_list_size,
                 hls_dir, idle_timeout=30):
        self.email = email
        self.password = password
        self.serial = serial
        self.region = region
        self.hls_time = hls_time
        self.hls_list_size = hls_list_size
        self.hls_dir = Path(hls_dir)
        self.idle_timeout = idle_timeout

        self.process = None
        self.last_activity = 0
        self.restart_count = 0
        self.lock = threading.Lock()
        self.running = False
        self.monitor_thread = None
        self._stop_event = threading.Event()

    def start_stream(self):
        """Start the streaming pipeline if not already running"""
        with self.lock:
            if self.running and self.process and self.process.poll() is None:
                self.last_activity = time.time()
                return True

            self.restart_count += 1
            session_id = f"{int(time.time())}_{self.restart_count}"

            print(f"[{self.restart_count}] Starting stream (on-demand)...", file=sys.stderr)

            # Build the pipeline command
            python_cmd = [
                'python3', '-u', '/app/stream_to_pipe.py',
                '--email', self.email,
                '--password', self.password,
                '--serial', self.serial,
                '--region', self.region
            ]

            ffmpeg_cmd = [
                'ffmpeg', '-re', '-i', 'pipe:0',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-crf', '23',
                '-g', '30',
                '-f', 'hls',
                '-hls_time', str(self.hls_time),
                '-hls_list_size', str(self.hls_list_size),
                '-hls_flags', 'append_list+omit_endlist+discont_start',
                '-hls_segment_filename', str(self.hls_dir / f'seg_{session_id}_%03d.ts'),
                str(self.hls_dir / 'stream.m3u8')
            ]

            # Start pipeline: python | ffmpeg
            python_proc = subprocess.Popen(
                python_cmd,
                stdout=subprocess.PIPE,
                stderr=sys.stderr
            )

            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=python_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=sys.stderr
            )

            # Store reference to python process for cleanup
            self._python_proc = python_proc

            self.running = True
            self.last_activity = time.time()

            # Start monitor thread if not running
            if self.monitor_thread is None or not self.monitor_thread.is_alive():
                self._stop_event.clear()
                self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()

            return True

    def stop_stream(self):
        """Stop the streaming pipeline"""
        with self.lock:
            if not self.running:
                return

            print("Stopping stream (idle timeout)...", file=sys.stderr)
            self.running = False

            # Terminate processes
            if hasattr(self, '_python_proc') and self._python_proc:
                try:
                    self._python_proc.terminate()
                    self._python_proc.wait(timeout=5)
                except:
                    self._python_proc.kill()

            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    self.process.kill()

            self.process = None
            self._python_proc = None

    def touch_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()

    def _monitor_loop(self):
        """Monitor stream health and idle timeout"""
        while not self._stop_event.is_set():
            time.sleep(1)

            with self.lock:
                if not self.running:
                    continue

                # Check idle timeout
                idle_time = time.time() - self.last_activity
                if idle_time > self.idle_timeout:
                    print(f"Stream idle for {idle_time:.0f}s, stopping to save battery",
                          file=sys.stderr)
                    self.running = False

                    # Stop processes outside lock

            # Check if we need to stop (outside lock to avoid deadlock)
            if not self.running and self.process:
                self.stop_stream()

                # Clean up old segments
                self._cleanup_segments()

    def _cleanup_segments(self):
        """Remove old .ts segments"""
        try:
            segments = sorted(self.hls_dir.glob('*.ts'), key=lambda p: p.stat().st_mtime)
            for seg in segments[:-30]:  # Keep last 30
                seg.unlink()
        except:
            pass

    def is_streaming(self):
        """Check if currently streaming"""
        with self.lock:
            return self.running and self.process and self.process.poll() is None


class OnDemandHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that triggers streaming on demand"""

    stream_manager = None  # Set by server

    def translate_path(self, path):
        """Sanitize path"""
        path = urllib.parse.unquote(path)
        path = path.rstrip('\r\n\t ')
        return super().translate_path(path)

    def handle(self):
        """Handle request with error suppression"""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        """Handle GET - trigger stream if requesting m3u8 or ts"""
        path = self.path.lower()

        # Trigger streaming for HLS requests
        if '.m3u8' in path or '.ts' in path:
            if self.stream_manager:
                self.stream_manager.touch_activity()
                if not self.stream_manager.is_streaming():
                    self.stream_manager.start_stream()
                    # Give stream time to start and create initial segments
                    time.sleep(2)

        # Serve status endpoint
        if path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            streaming = self.stream_manager.is_streaming() if self.stream_manager else False
            self.wfile.write(f'{{"streaming": {str(streaming).lower()}}}'.encode())
            return

        super().do_GET()

    def end_headers(self):
        """Add CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """Log to stderr"""
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.address_string(),
            self.log_date_time_string(),
            format % args
        ))


def run_on_demand_server(port, directory, email, password, serial, region,
                         hls_time, hls_list_size, idle_timeout):
    """Run the on-demand streaming server"""
    os.chdir(directory)

    # Create stream manager
    manager = StreamManager(
        email=email,
        password=password,
        serial=serial,
        region=region,
        hls_time=hls_time,
        hls_list_size=hls_list_size,
        hls_dir=directory,
        idle_timeout=idle_timeout
    )

    # Configure handler
    OnDemandHandler.stream_manager = manager

    # Handle shutdown
    def shutdown(signum, frame):
        print("\nShutting down...", file=sys.stderr)
        manager.stop_stream()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print(f"On-demand streaming server running on port {port}", file=sys.stderr)
    print(f"Idle timeout: {idle_timeout} seconds", file=sys.stderr)
    print("Stream will start when first client connects", file=sys.stderr)

    with socketserver.TCPServer(("", port), OnDemandHandler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='On-demand EZVIZ stream manager')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--directory', default='/share/ezviz_hls')
    parser.add_argument('--email', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--region', default='Europe')
    parser.add_argument('--hls-time', type=int, default=2)
    parser.add_argument('--hls-list-size', type=int, default=10)
    parser.add_argument('--idle-timeout', type=int, default=30)

    args = parser.parse_args()

    run_on_demand_server(
        port=args.port,
        directory=args.directory,
        email=args.email,
        password=args.password,
        serial=args.serial,
        region=args.region,
        hls_time=args.hls_time,
        hls_list_size=args.hls_list_size,
        idle_timeout=args.idle_timeout
    )
