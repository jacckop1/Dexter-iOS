"""Simulate a Telegram upload socket failure without any real account."""
import tempfile
import unittest
from pathlib import Path

from resilient_transfer import upload_big_parts, PART_SIZE


class FakeTelegram:
    def __init__(self):
        self.calls = []
        self.failed_once = False

    def is_connected(self):
        return True

    async def connect(self):
        pass

    async def __call__(self, request):
        self.calls.append((request.file_part, request.file_total_parts, len(request.bytes)))
        if request.file_part == 0 and not self.failed_once:
            self.failed_once = True
            raise TimeoutError("Simulated one dropped MTProto part")
        return True


class UploadResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_only_failed_part_without_restarting(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "sample.ipa"
            file.write_bytes(b"x" * (10 * 1024 * 1024 + 1234))
            fake = FakeTelegram()
            handle = await upload_big_parts(fake, file, concurrency=2, max_seconds=30)
            parts = (file.stat().st_size + PART_SIZE - 1) // PART_SIZE
            self.assertEqual(handle.parts, parts)
            self.assertEqual(handle.name, "sample.ipa")
            uploaded_indexes = [item[0] for item in fake.calls]
            self.assertEqual(uploaded_indexes.count(0), 2)
            self.assertEqual(uploaded_indexes.count(1), 1)
            self.assertEqual(set(uploaded_indexes), set(range(parts)))
            self.assertTrue(all(part_count == parts for _, part_count, _ in fake.calls))


if __name__ == "__main__":
    unittest.main()
