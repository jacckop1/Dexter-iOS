"""Offline resilience tests: simulate a drop and 503, then Range resume."""
import http.server
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path

import requests

from resilient_transfer import download_resumable


class RangeHandler(http.server.BaseHTTPRequestHandler):
    blob = b"A" * (1024 * 1024) + b"B" * (1024 * 1024) + b"C" * 781
    hits = []
    lock = threading.Lock()
    first_drop = True
    first_503 = True

    def do_GET(self):
        range_header = self.headers.get("Range", "")
        with self.lock:
            self.hits.append(range_header)
            if self.first_drop:
                type(self).first_drop = False
                drop = True
                error = False
            elif self.first_503:
                type(self).first_503 = False
                drop = False
                error = True
            else:
                drop = error = False
        if error:
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not range_header.startswith("bytes="):
            self.send_error(400)
            return
        start = int(range_header[6:].split("-")[0])
        data = self.blob[start:]
        self.send_response(206)
        self.send_header("Content-Range", f"bytes {start}-{len(self.blob) - 1}/{len(self.blob)}")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        if drop:
            # Return a valid first megabyte then abruptly hang up.
            self.wfile.write(data[:1024 * 1024])
            self.wfile.flush()
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        else:
            self.wfile.write(data)

    def log_message(self, *_):
        pass


class ResumeTests(unittest.TestCase):
    def test_continues_at_byte_offset_after_disconnect_and_503(self):
        RangeHandler.hits = []
        RangeHandler.first_drop = True
        RangeHandler.first_503 = True
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder, requests.Session() as session:
                target = Path(folder) / "large.ipa"
                url = f"http://127.0.0.1:{server.server_port}/test.ipa"
                download_resumable(session, url, target, len(RangeHandler.blob),
                                   max_seconds=20, idle_seconds=2)
                self.assertEqual(target.read_bytes(), RangeHandler.blob)
                self.assertGreaterEqual(len(RangeHandler.hits), 3)
                self.assertEqual(RangeHandler.hits[0], "bytes=0-")
                self.assertTrue(any(r.startswith("bytes=1048576-") for r in RangeHandler.hits[1:]))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
