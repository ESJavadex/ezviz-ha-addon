#!/usr/bin/env python3
"""Simple HTTP server with CORS support for HLS streaming"""

import http.server
import socketserver
import os
import sys

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS headers for cross-origin HLS playback"""

    def handle(self):
        """Handle request, suppressing BrokenPipeError (client disconnected)"""
        try:
            super().handle()
        except BrokenPipeError:
            # Client disconnected mid-transfer - harmless during stream restarts
            pass
        except ConnectionResetError:
            # Client reset connection - also harmless
            pass

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """Log to stderr for HA addon logs"""
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.address_string(),
            self.log_date_time_string(),
            format % args
        ))


def run_server(port=8080, directory='.'):
    """Start the HTTP server"""
    os.chdir(directory)

    with socketserver.TCPServer(("", port), CORSRequestHandler) as httpd:
        print(f"CORS HTTP server running on port {port}", file=sys.stderr)
        httpd.serve_forever()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--directory', default='.')
    args = parser.parse_args()

    run_server(args.port, args.directory)
