"""CLI: style 子命令（段级距离）与预设分段流水线的守卫测试。"""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from inksoul.cli import main


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


class TestStyleCommand(unittest.TestCase):
    def _tmp(self, text):
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.unlink, path)
        return path

    def test_short_text_says_short(self):
        path = self._tmp("她醒了。")
        code, out = _run(["style", path])
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: SHORT", out)

    def test_reports_distance_and_verdict(self):
        seg = (
            "她把窗帘拉开一条缝，海是灰的，海面上浮着雾，雾里那道白线是防波堤，"
            "房子太大，一早上没人说话，这种空反而让她踏实。"
            "台灯拧开，昨晚熨过一遍的裙子又拿出来，垫布压上熨衣板，"
            "蒸汽升起来的时候她用掌心把前褶从腰头抹到裙摆，抹了三遍。"
        ) * 6
        path = self._tmp(seg)
        code, out = _run(["style", path])
        self.assertEqual(code, 0)
        self.assertIn("距离", out)
        self.assertIn("VERDICT:", out)
        self.assertIn("骨架复用率", out)

    def test_threshold_flag(self):
        seg = "长句子要多一点，逗号连接起来，读着才像人写的散文那样绵长，" * 40
        path = self._tmp(seg)
        code, out = _run(["style", path, "--threshold", "0.01"])
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: FAR", out)

    def test_missing_path(self):
        code, _out = _run(["style", "/tmp/__no_such_file__.md"])
        self.assertEqual(code, 1)


class TestPresetPipeline(unittest.TestCase):
    """预设里必须有死命令与分段流水线，否则分段验收形同虚设。"""

    def _preset(self):
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "cordis.patch.yml"
        return p.read_text(encoding="utf-8")

    def test_mandatory_skill_load(self):
        text = self._preset()
        self.assertIn("死命令", text)
        self.assertIn("prose-deai", text)
        self.assertIn("已载入", text)

    def test_segmented_pipeline(self):
        text = self._preset()
        self.assertIn("分段流水线", text)
        self.assertIn("inksoul_style", text)
        self.assertIn("800–1000", text)

    def test_no_whole_chapter_single_shot(self):
        self.assertIn("禁止一次性出整章", self._preset())


if __name__ == "__main__":
    unittest.main()
