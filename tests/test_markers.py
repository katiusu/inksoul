"""AI 味标记族（中文 Biber 清单）测试：密度、基线对比、内置闸门、审查接入。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from inksoul import markers
from inksoul import reviewer
from inksoul.analyzer import analyze_text
from inksoul.agent import STATUS_ERROR, STATUS_FAIL, STATUS_PASS, run_gate
from inksoul.text_processor import process

# 刻意堆满名词化 / 连接词 / 定语链 / 并列 / 被动 / 抽象词的段落
STIFF = """对这段记忆的重新审视，使得他内心深处产生了一种难以言说的复杂情绪。
然而，这种情绪的表达方式，在很大程度上受到了来自童年时期家庭环境的影响。
因此，通过对自我认知的不断调整与修正，他逐渐形成了一套属于自己的价值体系。
此外，在关于时间与空间的哲学性思考方面，他所进行的探索具有着某种程度的必然性。
同时，这种对于意义本身的追问，也使得他不得不面对那些被反复讨论过的问题。
换言之，对现状的分析与对未来可能性的评估，构成了他所能够做出的全部判断的基础。
值得注意的是，在被要求作出回应的那个瞬间，他选择了一种近乎沉默的处理方式。
从某种意义上看，这种沉默本身也构成了一种态度，并被周围的人理解为拒绝。
也就是说，对沉默的解读，往往取决于解读者的立场与所处的位置。
综上所述，对个体行为的分析，必须被置于具体的语境之中，才能够获得相对合理的解释。
不可否认的是，这种分析框架的有效性，在相当程度上依赖于对概念的清晰界定。
由此可以看出，对复杂情感的处理，需要一种更为细致的、被反复检验过的方法。
"""

PLAIN = """他推开门，风灌进来。屋里没人，桌上放着半碗凉了的面。
他把面端起来吃了两口，放下。外面有人在喊什么，他没听清。
"""


class TestMarkerAnalysis(unittest.TestCase):
    def test_counts_and_density(self):
        rep = markers.analyze_markers(process(STIFF))
        self.assertGreater(rep.chars, 0)
        self.assertEqual(rep.counts.get("NOM", 0), rep.narrative_counts.get("NOM", 0))
        self.assertGreater(rep.per_1000.get("NOM", 0), 0)
        self.assertTrue(set(rep.per_1000) == set(markers.KINDS))

    def test_quoted_sentences_counted_as_dialogue(self):
        text = "\u201c\u4f60\u5bf9\u8fd9\u4ef6\u4e8b\u60c5\u8fdb\u884c\u4e86\u5904\u7406\u5417\uff1f\u201d\u4ed6\u70b9\u4e86\u70b9\u5934\u3002\n"
        rep = markers.analyze_markers(process(text))
        self.assertGreater(rep.dialogue_chars, 0)

    def test_hits_carry_label_and_text(self):
        rep = markers.analyze_markers(process(STIFF))
        self.assertTrue(rep.hits)
        for hit in rep.hits[:5]:
            self.assertIn(hit.kind, markers.KINDS)
            self.assertTrue(hit.label)

    def test_as_dict_roundtrip(self):
        rep = markers.analyze_markers(process(STIFF))
        data = rep.as_dict()
        json.dumps(data)
        self.assertIn("per_1000", data)
        self.assertIn("counts", data)


class TestBaseline(unittest.TestCase):
    def test_bundled_baseline_loads(self):
        base = markers.load_baseline()
        rows = markers.baseline_rows(base, "\u7f51\u6587")
        self.assertIsNotNone(rows)
        for kind in markers.KINDS:
            self.assertIn(kind, rows)
            self.assertLessEqual(rows[kind]["p50"], rows[kind]["p90"] + 1e-9)

    def test_stiff_text_scores_higher_than_plain(self):
        base = markers.load_baseline()
        stiff = markers.compare_to_baseline(markers.analyze_markers(process(STIFF)), base)
        plain = markers.compare_to_baseline(markers.analyze_markers(process(PLAIN)), base)
        stiff_bad = sum(1 for r in stiff if r["level"] != "ok")
        plain_bad = sum(1 for r in plain if r["level"] != "ok")
        self.assertGreater(stiff_bad, plain_bad)

    def test_levels_ok_high_very_high(self):
        rep = markers.analyze_markers(process(STIFF))
        fake = {"genres": {"\u7f51\u6587": {"per_1000": {
            k: {"p50": 0.0, "p90": 0.0001, "p99": 0.0002} for k in markers.KINDS}}}}
        rows = markers.compare_to_baseline(rep, fake)
        levels = {r["level"] for r in rows}
        self.assertIn("very_high", levels)
        fake2 = {"genres": {"\u7f51\u6587": {"per_1000": {
            k: {"p50": 0.0, "p90": 999.0, "p99": 9999.0} for k in markers.KINDS}}}}
        self.assertTrue(all(r["level"] == "ok"
                            for r in markers.compare_to_baseline(rep, fake2)))


class TestBuiltinGate(unittest.TestCase):
    def _run(self, text):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        try:
            return run_gate("__inksoul__:markers", __import__("pathlib").Path(path))
        finally:
            os.unlink(path)

    def test_skip_short_text(self):
        res = self._run(PLAIN)
        self.assertEqual(res.status, STATUS_PASS)
        self.assertEqual(res.verdict, "VERDICT: SKIP")
        self.assertIn("SKIP", res.receipt)

    def test_pass_long_plain_text(self):
        res = self._run(PLAIN * 12)
        self.assertEqual(res.status, STATUS_PASS)
        self.assertIn("PASS", res.verdict)
        self.assertIn("rc=0", res.receipt)

    def test_fail_stiff_text(self):
        res = self._run(STIFF)
        self.assertEqual(res.status, STATUS_FAIL)
        self.assertIn("FAIL", res.verdict)
        self.assertTrue(res.findings)
        self.assertTrue(res.receipt.startswith("RECEIPT"))

    def test_unknown_builtin_gate(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            res = run_gate("__inksoul__:nope", __import__("pathlib").Path(path))
        finally:
            os.unlink(path)
        self.assertEqual(res.status, STATUS_ERROR)


class TestIntegration(unittest.TestCase):
    def test_analyzer_includes_markers(self):
        rep = analyze_text(STIFF)
        self.assertTrue(hasattr(rep.markers, "per_1000"))
        self.assertIn("markers", rep.as_dict())

    def test_reviewer_reports_marker_issue(self):
        rep = reviewer.review(process(STIFF))
        kinds = [i.kind for i in rep.issues]
        self.assertIn(reviewer.KIND_MARKER, kinds)
        marker_issues = [i for i in rep.issues if i.kind == reviewer.KIND_MARKER]
        for issue in marker_issues:
            self.assertTrue(issue.suggestion)
            self.assertEqual(issue.evidence.get("metric"), "marker_per_1000")

    def test_cli_markers_subcommand(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.write(fd, STIFF.encode("utf-8"))
        os.close(fd)
        try:
            out = subprocess.run(
                [sys.executable, "-m", "inksoul.cli", "markers", path],
                capture_output=True, text=True, timeout=180,
                env=dict(os.environ, PYTHONPATH=os.path.join(os.getcwd(), "src")),
            )
        finally:
            os.unlink(path)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("\u5343\u5b57", out.stdout)

    def test_gate_preset_registered(self):
        from inksoul.config import resolve_gate
        self.assertEqual(resolve_gate("markers"), "__inksoul__:markers")


if __name__ == "__main__":
    unittest.main()

FILLER = "他推开门，风灌进来。屋里没人，桌上放着半碗凉了的面。"
PASSIVE_LINE = "窗子被风吹得响了一下。"


class TestShortSamplePoisson(unittest.TestCase):
    """400–1200 字之间：以 p99 为泊松均值判断，少量出现不构成证据。"""

    def _text(self, passive_count):
        body = [FILLER] * 25
        for i in range(passive_count):
            body.insert(i * 2 + 1, PASSIVE_LINE)
        return "".join(body)

    def test_one_passive_is_not_evidence(self):
        rep = markers.analyze_markers(process(self._text(1)))
        self.assertGreaterEqual(rep.narrative_chars, 400)
        self.assertLess(rep.narrative_chars, markers.SHORT_WINDOW_CHARS)
        rows = {r["kind"]: r for r in markers.compare_to_baseline(rep, markers.load_baseline())}
        row = rows["PASSIVE"]
        self.assertEqual(row["method"], "poisson")
        self.assertEqual(row["count"], 1)
        self.assertEqual(row["level"], "ok")

    def test_pileup_fails(self):
        passed, lines = markers.gate_text(self._text(16))
        self.assertFalse(passed)
        self.assertTrue(any("VERDICT: FAIL" in l for l in lines))

    def test_poisson_thresholds(self):
        self.assertEqual(markers._poisson_level(1, 5.74, 600)[0], "ok")
        self.assertEqual(markers._poisson_level(6, 5.74, 600)[0], "ok")
        self.assertEqual(markers._poisson_level(8, 5.74, 600)[0], "high")
        self.assertEqual(markers._poisson_level(10, 5.74, 600)[0], "very_high")

