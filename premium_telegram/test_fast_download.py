"""Test parallel download: two simultaneous ranges, interrupted stream and 503."""
import http.server
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from fast_download import fast_download


class Server(http.server.BaseHTTPRequestHandler):
    data = bytes(range(256)) * 16384
    received = []
    first_drop = True
    first_error = True
    lock = threading.Lock()

    def do_GET(self):
        value = self.headers.get("Range", "")
        match = __import__("re").fullmatch(r"bytes=(\d+)-(\d+)", value)
        if not match:
            self.send_error(400)
            return
        low, high = map(int, match.groups())
        with self.lock:
            type(self).received.append((low, high))
            drop = low == 0 and type(self).first_drop
            fail = low >= 1048576 and type(self).first_error
            if drop:
                type(self).first_drop = False
            if fail:
                type(self).first_error = False
        if fail:
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = self.data[low:high + 1]
        self.send_response(206)
        self.send_header("Content-Range", f"bytes {low}-{high}/{len(self.data)}")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        if drop:
            self.wfile.write(body[:262144])
            self.wfile.flush()
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        else:
            self.wfile.write(body)

    def log_message(self, *_):
        pass


class ParallelRangeTests(unittest.TestCase):
    def test_parallel_resume_at_exact_offset(self):
        Server.first_drop = True
        Server.first_error = True
        Server.received = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "output.ipa"
                fast_download(
                    f"http://127.0.0.1:{server.server_port}/file", output,
                    len(Server.data), label="test", connections=4,
                    block_size=1048576, max_seconds=30, idle_seconds=2,
                )
                self.assertEqual(output.read_bytes(), Server.data)
                self.assertIn((0, 1048575), Server.received)
                self.assertIn((262144, 1048575), Server.received)
                self.assertIn((1048576, 2097151), Server.received)
                self.assertTrue(any(start >= 2097152 for start, _ in Server.received))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
