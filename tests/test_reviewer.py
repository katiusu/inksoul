"""审查器测试：机械复用、J3 豁免、情绪直陈、无总分。"""
import unittest

from inksoul import reviewer
from inksoul.config import InkSoulConfig
from inksoul.text_processor import process

REPEAT = """他慢慢地推开了房门，走进屋里。她没有回答，只是看着窗外。

他慢慢地推开了房门，走进屋里。她轻轻地关上了窗户。

他慢慢地推开了房门，走进屋里。她感到很难过，心里一阵酸楚。
"""


class TestReview(unittest.TestCase):
    def test_mechanical_issues_found(self):
        rep = reviewer.review(process(REPEAT))
        kinds = [i.kind for i in rep.issues]
        self.assertIn(reviewer.KIND_MECHANICAL, kinds)
        self.assertTrue(rep.blocking)
        self.assertIn("建议局部修订", rep.verdict)

    def test_issues_have_explanations(self):
        rep = reviewer.review(process(REPEAT))
        for issue in rep.issues:
            self.assertTrue(issue.suggestion)
            self.assertTrue(issue.evidence)
            self.assertGreaterEqual(issue.severity, 0.0)
            self.assertLessEqual(issue.severity, 1.0)

    def test_j3_exemption(self):
        class StubCluster:
            signature = "PRON ADV V"
            freq = 4
            para_spread = 3
            gap_cv = 0.2
            members = []
            evidence = ["J3 出现显式修辞标记「一遍又一遍」→ 倾向修辞性重复"]

        class StubReport:
            suspects = [StubCluster()]

        rep = reviewer.review(process(REPEAT), fingerprint_report=StubReport())
        mechanical = [i for i in rep.issues if i.kind == reviewer.KIND_MECHANICAL]
        self.assertEqual(mechanical, [])
        self.assertEqual(len(rep.exempted), 1)
        self.assertIn("一遍又一遍", rep.exempted[0]["reason"])

    def test_emotion_direct_statement(self):
        rep = reviewer.review(process("她感到很难过。他觉得很委屈。"))
        kinds = [i.kind for i in rep.issues]
        self.assertIn(reviewer.KIND_EMOTION, kinds)

    def test_no_single_score(self):
        rep = reviewer.review(process(REPEAT))
        d = rep.as_dict()
        self.assertNotIn("score", d)
        self.assertNotIn("ai_probability", d)

    def test_empty_raises(self):
        from inksoul.errors import InkSoulError
        with self.assertRaises(InkSoulError):
            reviewer.review(process("。"))

    def test_clean_text_no_blocking(self):
        text = ("黄昏的时候，巷子里的光变得很薄。老周蹲在门槛上抽烟，"
                "烟灰积了很长一段也没弹。\n\n"
                "「你回来了。」他抬了抬眼皮，声音被咳嗽截成两半。")
        rep = reviewer.review(process(text))
        self.assertEqual(rep.blocking, [])


if __name__ == "__main__":
    unittest.main()

STIFF_TEXT = (
    "他对这个问题进行了长时间的思考，并且对结果作出了判断。"
    "通过对现场的调查，他发现了一个问题，并且对问题进行了一次处理。"
    "经过对资料的整理，他对这部分内容进行了调整，也对结构作出了安排。"
    "在这种情况之下，他不得不对计划进行修改，同时对细节进行了检查。"
    "通过对现场的调查，他发现了一个问题，并且对问题进行了一次处理。"
    "经过对资料的整理，他对这部分内容进行了调整，也对结构作出了安排。"
)


class TestMarkerIssueAnchor(unittest.TestCase):
    """标记族问题句必须能定位到正文里的真实句子，否则修订器永远跳过。"""

    def test_marker_issue_quotes_real_sentence(self):
        from inksoul import markers as mk

        doc = process(STIFF_TEXT * 6)  # 叙述要 >400 字才判定标记族
        report = reviewer.review(doc, markers_report=mk.analyze_markers(doc))
        marker_issues = [i for i in report.issues if i.kind == reviewer.KIND_MARKER]
        self.assertTrue(marker_issues)
        for issue in marker_issues:
            self.assertIn(issue.text, STIFF_TEXT * 6)
            self.assertNotEqual(issue.clause_id, "")
            self.assertIn("method", issue.evidence)

