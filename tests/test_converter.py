import tempfile
import unittest
from pathlib import Path

from openclaw_session_md.converter import ConvertOptions, convert_file, find_session_files


class ConverterTests(unittest.TestCase):
    def test_convert_regular_session_fixture(self):
        md, meta = convert_file(Path("tests/fixtures/session.jsonl"), options=ConvertOptions(redact_metadata=True))
        self.assertIn("# OpenClaw session", md)
        self.assertIn("## Transcript", md)
        self.assertIn("### User", md)
        self.assertIn("### Assistant", md)
        self.assertNotIn("Conversation info", md)
        self.assertIn("Hello", md)
        self.assertIn("Usage:", md)
        self.assertIn("input=10", md)
        self.assertIn("output=3", md)
        self.assertIn("totalTokens=20", md)
        self.assertEqual(meta.message_count, 2)

    def test_convert_trajectory_fixture(self):
        md, meta = convert_file(Path("tests/fixtures/trace.trajectory.jsonl"))
        self.assertIn("## Timeline", md)
        self.assertIn("### User Prompt", md)
        self.assertIn("### Assistant", md)
        self.assertIn("Usage:", md)
        self.assertEqual(meta.model_id, "gpt-5.4")

    def test_find_session_files_filters(self):
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            (tmp_path / "a.jsonl").write_text("{}\n")
            (tmp_path / "b.trajectory.jsonl").write_text("{}\n")
            (tmp_path / "c.checkpoint.123.jsonl").write_text("{}\n")
            self.assertEqual([p.name for p in find_session_files(tmp_path)], ["a.jsonl"])
            self.assertEqual(
                sorted(p.name for p in find_session_files(tmp_path, include_trajectory=True, include_checkpoints=True)),
                ["a.jsonl", "b.trajectory.jsonl", "c.checkpoint.123.jsonl"],
            )


if __name__ == "__main__":
    unittest.main()
