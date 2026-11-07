
"""P0 守卫：单一判定源（D3）、修订局部复检（D1）、restyle 保真（D2）。"""
import json
import unittest
from unittest import mock

from inksoul import markers as mk
from inksoul.config import InkSoulConfig, ModelConfig
from inksoul.generation import (CreationBrief, build_plan, restyle, revise,
                                _fidelity_checks)
from inksoul.llm import LLMClient
from inksoul.reviewer import review, KIND_MARKER
from inksoul.text_processor import process

BASE = ("他推开门，风灌进来。她把外套挂好，坐到桌边。窗外的雨还没停，屋檐下滴着水。"
        "他说了句什么，她没听清。炉子上的水开了，白汽一阵阵往上冒。") * 10


def fake_client(text):
    def transport(method, url, headers, body, timeout):
        return 200, json.dumps({"choices": [{"message": {"content": text}}],
                                "usage": {"total_tokens": 10}}, ensure_ascii=False)
    return LLMClient(ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m"),
                     transport=transport, sleep=lambda s: None)


def rows_of(**levels):
    out = []
    for kind in mk.KINDS:
        lvl = levels.get(kind, "ok")
        out.append({"kind": kind, "name": mk.KIND_NAMES[kind], "value": 1.0,
                    "count": 1, "method": "quantile", "p50": 0.1, "p90": 0.5,
                    "p99": 5.0, "ratio_p90": 2.0, "level": lvl,
                    "insufficient": False})
    return out


class TestVerdict(unittest.TestCase):
    def test_single_high_passes(self):
        v, failing = mk.verdict_of(rows_of(NOM="high"))
        self.assertEqual(v, "PASS")
        self.assertEqual(failing, [])

    def test_two_high_fails(self):
        v, failing = mk.verdict_of(rows_of(NOM="high", ATTR="high"))
        self.assertEqual(v, "FAIL")
        self.assertEqual({r["kind"] for r in failing}, {"NOM", "ATTR"})

    def test_very_high_fails_alone(self):
        v, failing = mk.verdict_of(rows_of(SIMILE="very_high"))
        self.assertEqual(v, "FAIL")
        self.assertEqual(len(failing), 1)

    def test_insufficient_skips(self):
        rows = rows_of()
        for r in rows:
            r["insufficient"] = True
            r["level"] = "ok"
        self.assertEqual(mk.verdict_of(rows)[0], "SKIP")

    def test_no_baseline(self):
        self.assertEqual(mk.verdict_of([])[0], "NO_BASELINE")


class TestSingleSource(unittest.TestCase):
    """v0.4.3 曾按「闸门判 FAIL 的族」分派 severity；40 对配对评测（AUC 0.29-0.52）
    证伪了该前提，已回退到 v0.4.2 口径：只看单族落在哪个分位区间。"""

    def test_reviewer_severity_follows_gate_rule(self):
        rep = mk.MarkerReport(chars=3000, narrative_chars=2500,
                              counts={k: 0 for k in mk.KINDS},
                              narrative_counts={k: 0 for k in mk.KINDS},
                              per_1000={k: 0.0 for k in mk.KINDS})
        rep.per_1000["NOM"] = 6.0
        rep.narrative_counts["NOM"] = 3
        rep.per_1000["ATTR"] = 3.0
        rep.narrative_counts["ATTR"] = 8
        baseline = {"genres": {"网文": {"per_1000": {
            k: {"mean": 0.0, "p50": 0.1, "p90": 0.5, "p99": 5.0} for k in mk.KINDS}}}}
        with mock.patch.object(mk, "load_baseline", return_value=baseline):
            rows = mk.compare_to_baseline(rep, baseline)
            verdict, failing = mk.verdict_of(rows)
            out = review(process(BASE), markers_report=rep)
        self.assertEqual(verdict, "FAIL")
        marker_issues = [i for i in out.issues if i.kind == KIND_MARKER]
        self.assertTrue(marker_issues)
        # NOM 6.0 超过 p99=5.0 → very_high → 0.6；ATTR 3.0 只在 p90 与 p99 之间 → 0.35
        self.assertEqual(sorted({i.severity for i in marker_issues}), [0.35, 0.6])
        self.assertEqual({r["kind"] for r in failing}, {"NOM"})


class TestReviseRecheck(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(CreationBrief(theme="雨夜", genre="小说"), InkSoulConfig())

    def review_one(self, text, severity=0.8):
        from inksoul.reviewer import LiteraryIssue, ReviewReport
        return ReviewReport(issues=[LiteraryIssue(kind="机械复用", clause_id="c1",
                                                  text=text, severity=severity,
                                                  suggestion="换个结构")],
                            verdict="建议修订")

    def test_rejects_rewrite_with_more_tags(self):
        res = revise("他推开门。", self.review_one("他推开门。"),
                     fake_client("他对着门进行了推开，门被风打开。"), self.plan)
        self.assertEqual(res.applied, 0)
        self.assertIn("改写不合格", res.notes[0])

    def test_accepts_single_tag_noise(self):
        res = revise("他推开门。", self.review_one("他推开门。"),
                     fake_client("门被他推开了。"), self.plan)
        self.assertEqual(res.applied, 1)
        self.assertIn("门被他推开了。", res.text)


class TestFidelity(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(CreationBrief(theme="雨夜", genre="小说"), InkSoulConfig())

    def test_fidelity_flags_loss(self):
        checks = _fidelity_checks(BASE, BASE[:200])
        self.assertTrue(checks["violations"])

    def test_restyle_rejects_short_output(self):
        res = restyle(BASE, ["名词化过多"], fake_client("他走了。"), self.plan)
        self.assertEqual(res.applied, 0)
        self.assertIn("保留原稿", res.notes[0])

    def test_restyle_rejects_drift(self):
        drift = ("合同条款约定，双方应就交付周期与验收标准另行协商。" * 20)
        res = restyle(BASE, ["名词化过多"], fake_client(drift), self.plan)
        self.assertEqual(res.applied, 0)
        self.assertIn("保留原稿", res.notes[0])

    def test_restyle_accepts_faithful(self):
        out = BASE.replace("风灌进来", "风灌进屋").replace("坐到桌边", "坐到桌旁")
        res = restyle(BASE, ["名词化过多"], fake_client(out), self.plan)
        self.assertEqual(res.applied, 1)
        self.assertTrue(any("保真" in n for n in res.notes))


if __name__ == "__main__":
    unittest.main()
