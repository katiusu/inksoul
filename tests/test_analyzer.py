"""分析器集成测试：一次跑通全部分析模块。"""
import json
import tempfile
import unittest
from pathlib import Path

from inksoul.analyzer import Analyzer
from inksoul.config import InkSoulConfig
from inksoul.errors import InputTooLarge

TEXT = """他推开门，走进屋里。屋里没有人，桌上放着一碗凉了的粥。

「你回来了。」母亲从里屋出来，手里还捏着针。

他没说话，把包放在椅子上。窗外的天色正在往下沉。
"""


class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.az = Analyzer(InkSoulConfig())

    def test_all_reports_present(self):
        rep = self.az.analyze(TEXT)
        self.assertIsNotNone(rep.fingerprint)
        self.assertIsNotNone(rep.diversity)
        self.assertIsNotNone(rep.style)
        self.assertIsNotNone(rep.narrative)
        self.assertIsNotNone(rep.review)
        self.assertGreater(rep.fingerprint.clause_count, 0)

    def test_as_dict_serializable(self):
        rep = self.az.analyze(TEXT)
        blob = json.dumps(rep.as_dict(), ensure_ascii=False)
        self.assertIn("fingerprint", blob)
        self.assertNotIn("score", blob.lower().replace("scores", ""))

    def test_without_review(self):
        rep = self.az.analyze(TEXT, with_review=False)
        self.assertIsNone(rep.review)

    def test_input_too_large(self):
        cfg = InkSoulConfig()
        cfg.analysis.max_chars = 10
        with self.assertRaises(InputTooLarge):
            Analyzer(cfg).analyze(TEXT)

    def test_works_when_model_api_down(self):
        """模型接口不可用（错误地址 + 无 Key）不得影响本地分析。"""
        cfg = InkSoulConfig()
        cfg.model.base_url = "http://127.0.0.1:9/v1"
        cfg.model.api_key = ""
        rep = Analyzer(cfg).analyze("他把伞收好，走进屋里。雨还在下。")
        self.assertGreater(rep.meta["clauses"], 0)
        self.assertIn("未见", rep.review.verdict)

    def test_review_gets_narrative(self):
        rep = self.az.analyze(TEXT)
        self.assertFalse([n for n in rep.review.notes if "未提供" in n], rep.review.notes)

    def test_analyze_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_text(TEXT, encoding="utf-8")
            rep = self.az.analyze_file(p)
            self.assertGreater(rep.fingerprint.clause_count, 0)

    def test_missing_file(self):
        with self.assertRaises(Exception):
            self.az.analyze_file("/nope/none.txt")


if __name__ == "__main__":
    unittest.main()
