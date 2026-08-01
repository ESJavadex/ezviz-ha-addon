#!/usr/bin/env python3
"""Simple HTTP server with CORS support for HLS streaming"""

import http.server
import socketserver
import os
import sys
import time
import urllib.parse

# Un reproductor pide el playlist varias veces por segundo. Cuando no hay stream
# eso son cientos de 404 por minuto, que llenan el log del add-on y esconden los
# errores que de verdad importan: así pasó inadvertido 16 horas que EZVIZ había
# dejado de autenticar. Los repetidos se agrupan en un resumen periódico.
SUMMARY_INTERVAL_SECONDS = 60


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS headers for cross-origin HLS playback"""

    _suppressed = 0
    _last_summary = 0.0

    def translate_path(self, path):
        """Sanitize path - strip trailing whitespace/control chars like \\r"""
        # URL decode and strip control characters
        path = urllib.parse.unquote(path)
        path = path.rstrip('\r\n\t ')
        return super().translate_path(path)

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

    def _emit(self, message):
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.address_string(),
            self.log_date_time_string(),
            message,
        ))

    @staticmethod
    def _is_routine(message):
        """Tráfico normal de un reproductor HLS, incluido el 404 de un playlist
        que aún no existe. Nada de esto merece una línea por petición."""
        return any(token in message for token in (
            " 200 ", " 206 ", " 304 ", " 404 ",
            "code 404", "code 200", "File not found",
        ))

    def _log(self, message):
        if not self._is_routine(message):
            self._emit(message)
            return

        cls = CORSRequestHandler
        now = time.monotonic()

        # La primera se registra tal cual: confirma que alguien está mirando.
        if cls._last_summary == 0.0:
            cls._last_summary = now
            self._emit(message)
            return

        cls._suppressed += 1
        if now - cls._last_summary >= SUMMARY_INTERVAL_SECONDS:
            self._emit("%d peticiones rutinarias en %ds (última: %s)" % (
                cls._suppressed, int(now - cls._last_summary), message))
            cls._last_summary = now
            cls._suppressed = 0

    def log_message(self, format, *args):
        """Log to stderr for HA addon logs"""
        self._log(format % args)

    def log_error(self, format, *args):
        """SimpleHTTPRequestHandler manda aquí los 404, que también son ruido."""
        self._log(format % args)


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
