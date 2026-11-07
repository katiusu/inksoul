"""命令行测试：入口、退出码、中文错误提示。"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from inksoul.cli import main

TEXT = "他推开门，走进屋里。\n\n桌面很干净，什么也没有。\n"


def run(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCLI(unittest.TestCase):
    def test_doctor(self):
        code, out, _ = run(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("jieba", out)

    def test_analyze_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_text(TEXT, encoding="utf-8")
            code, out, _ = run(["analyze", str(p)])
            self.assertEqual(code, 0, out)
            self.assertIn("句法", out)

    def test_analyze_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_text(TEXT, encoding="utf-8")
            code, out, _ = run(["analyze", str(p), "--json"])
            self.assertEqual(code, 0)
            self.assertIn('"fingerprint"', out)

    def test_missing_file(self):
        code, _out, err = run(["analyze", "/nope/none.txt"])
        self.assertNotEqual(code, 0)
        self.assertIn("不存在", err)

    def test_plan_offline(self):
        code, out, _ = run(["plan", "雨夜重逢"])
        self.assertEqual(code, 0)
        self.assertIn("voice", out)
        self.assertIn("小说", out)

    def test_generate_without_key(self):
        code, _out, err = run(["generate", "雨夜重逢", "--target-chars", "100"])
        self.assertNotEqual(code, 0)
        self.assertTrue("api_key" in err or "API" in err)

    def test_version_flag(self):
        import inksoul
        self.assertTrue(inksoul.__version__)
        with self.assertRaises(SystemExit) as ctx:
            run(["--version"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
