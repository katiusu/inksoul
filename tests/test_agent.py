"""Agent 闭环测试：假模型 + 假闸门，不联网、不起子进程。"""
import json
import unittest
from pathlib import Path

from inksoul.agent import (RoundRecord, STATUS_FAIL, STATUS_PASS, STATUS_SKIPPED,
                           WritingAgent, run_gate)
from inksoul.config import InkSoulConfig, ModelConfig
from inksoul.errors import ConfigError
from inksoul.llm import LLMClient

DRAFT = ("他把门推开。\n\n她把窗关上。\n\n猫把桌上的杯子碰倒。\n\n"
         "雨敲着铁皮棚子，一阵紧一阵松，像有人在上面来回走。\n\n"
         "他没说话，把伞收拢，靠在门边，水滴顺着伞骨滴到水泥地上。\n")
FIXED = "他推门进去时，屋里的钟正敲到第七下，没人应声。"
PLAN = json.dumps({"voice": "冷调第三人称", "rhythm": "长短交替", "dialogue": "少标签",
                   "sentence_policy": ["a", "b"], "forbidden": ["c"]}, ensure_ascii=False)


def fake_client(draft=DRAFT, revised=FIXED, status=200):
    def transport(method, url, headers, body, timeout):
        if status != 200:
            return status, "err"
        payload = json.loads(body) if isinstance(body, str) else {}
        prompt = " ".join(m.get("content", "") for m in payload.get("messages", []))
        if "文体策略" in prompt:
            content = PLAN
        elif "只改写" in prompt:
            content = revised
        else:
            content = draft
        return 200, json.dumps({"choices": [{"message": {"content": content}}],
                                "usage": {"total_tokens": 5}}, ensure_ascii=False)
    cfg = ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m")
    return LLMClient(cfg, transport=transport, sleep=lambda s: None)


class TestGate(unittest.TestCase):
    def test_no_cmd_skipped(self):
        g = run_gate("", Path("/tmp/x.txt"))
        self.assertEqual(g.status, STATUS_SKIPPED)
        self.assertFalse(g.blocked)

    def test_parses_pass_and_receipt(self):
        def runner(line, timeout):
            return 0, "some log\nVERDICT: PASS\nRECEIPT: a.txt rc=0 VERDICT: PASS @ now"
        g = run_gate("bash gate.sh {file}", Path("/tmp/a.txt"), runner=runner)
        self.assertEqual(g.status, STATUS_PASS)
        self.assertIn("RECEIPT", g.receipt)

    def test_parses_fail(self):
        g = run_gate("bash gate.sh {file}", Path("/tmp/a.txt"),
                     runner=lambda line, timeout: (1, "VERDICT: FAIL"))
        self.assertEqual(g.status, STATUS_FAIL)
        self.assertTrue(g.blocked)

    def test_error_is_blocking(self):
        def runner(line, timeout):
            raise OSError("no such script")
        g = run_gate("nope {file}", Path("/tmp/a.txt"), runner=runner)
        self.assertEqual(g.status, "error")
        self.assertTrue(g.blocked)

    def test_placeholder_substituted(self):
        seen = {}
        def runner(line, timeout):
            seen["line"] = line
            return 0, "VERDICT: PASS"
        run_gate("bash g.sh {file}", Path("/tmp/a b.txt"), runner=runner)
        self.assertNotIn("{file}", seen["line"])
        self.assertIn("a b.txt", seen["line"])


class TestRank(unittest.TestCase):
    def test_gate_beats_counts(self):
        clean_but_failed = RoundRecord("x", 1, 100, 0, 0, gate_status=STATUS_FAIL)
        dirty_but_passed = RoundRecord("y", 1, 100, 3, 5, gate_status=STATUS_PASS)
        self.assertGreater(clean_but_failed.rank(), dirty_but_passed.rank())

    def test_counts_ordered(self):
        a = RoundRecord("a", 1, 100, 1, 9)
        b = RoundRecord("b", 1, 100, 2, 3)
        self.assertLess(a.rank(), b.rank())


class TestAgent(unittest.TestCase):
    def test_requires_api(self):
        cfg = InkSoulConfig()
        with self.assertRaises(ConfigError):
            WritingAgent(cfg).run("x", offline=True)

    def test_run_writes_output_and_report(self):
        cfg = InkSoulConfig()
        cfg.model.api_key = "sk-t"
        with __import__("tempfile").TemporaryDirectory() as td:
            out = Path(td) / "draft.txt"
            rep = Path(td) / "report.json"
            res = WritingAgent(cfg, client=fake_client(), gate_cmd="",
                               gate_timeout=1).run(
                "雨夜重逢", candidates=1, max_rounds=1, out=out, report_path=rep)
            self.assertTrue(out.exists())
            self.assertEqual(out.read_text(encoding="utf-8"), res.text)
            data = json.loads(rep.read_text(encoding="utf-8"))
            self.assertEqual(len(data["rounds"]), len(res.rounds))
            self.assertTrue(0 <= res.chosen < len(res.rounds))
            self.assertTrue(res.stop_reason)
            self.assertIsNone(res.gate)

    def test_gate_failure_recorded(self):
        cfg = InkSoulConfig()
        cfg.model.api_key = "sk-t"
        res = WritingAgent(cfg, client=fake_client(), gate_cmd="bash g.sh {file}",
                           gate_timeout=1,
                           runner=lambda line, t: (1, "VERDICT: FAIL")).run(
            "雨夜重逢", candidates=1, max_rounds=0)
        self.assertEqual(res.gate.status, STATUS_FAIL)
        self.assertTrue(any("闸门" in n for n in res.notes))
        self.assertTrue(all(r.gate_status == STATUS_FAIL for r in res.rounds))

    def test_gate_pass_is_not_blocking(self):
        cfg = InkSoulConfig()
        cfg.model.api_key = "sk-t"
        res = WritingAgent(cfg, client=fake_client(), gate_cmd="bash g.sh {file}",
                           gate_timeout=1,
                           runner=lambda line, t: (0, "VERDICT: PASS\nRECEIPT: d.txt rc=0")).run(
            "雨夜重逢", candidates=1, max_rounds=1)
        self.assertEqual(res.gate.status, STATUS_PASS)
        self.assertFalse(any("未 PASS" in n for n in res.notes))
class TestGateFinalOnly(unittest.TestCase):
    """闸门是 40s 级外部进程：默认只在定稿后跑，不逐候选跑。"""

    def _cfg(self):
        cfg = InkSoulConfig()
        cfg.model.api_key = "sk-t"
        return cfg

    def test_pass_runs_once_for_many_candidates(self):
        calls = []

        def runner(line, timeout):
            calls.append(line)
            return 0, "VERDICT: PASS"

        res = WritingAgent(self._cfg(), client=fake_client(), gate_cmd="bash g.sh {file}",
                           gate_timeout=1, runner=runner).run(
            "雨夜重逢", candidates=3, max_rounds=0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(res.gate.status, STATUS_PASS)
        self.assertTrue(any("定稿后过闸门 1 次" in n for n in res.notes))

    def test_fail_then_restyle_then_pass(self):
        seq = []

        def runner(line, timeout):
            seq.append(line)
            if len(seq) == 1:
                return 1, "prose_dense FAIL 句末单字 0 处\nVERDICT: FAIL"
            return 0, "VERDICT: PASS"

        res = WritingAgent(self._cfg(), client=fake_client(), gate_cmd="bash g.sh {file}",
                           gate_timeout=1, runner=runner).run(
            "雨夜重逢", candidates=2, max_rounds=0)
        self.assertEqual(len(seq), 2)
        self.assertEqual(res.gate.status, STATUS_PASS)
        self.assertTrue(any("定稿后过闸门 2 次" in n for n in res.notes))

    def test_grade_flag_controls_gate_call(self):
        calls = []

        def runner(line, timeout):
            calls.append(line)
            return 0, "VERDICT: PASS"

        agent = WritingAgent(self._cfg(), client=fake_client(),
                             gate_cmd="bash g.sh {file}", gate_timeout=1,
                             runner=runner)
        _, _, g1 = agent._grade(DRAFT, label="候选#0", with_gate=False)
        self.assertEqual(g1.status, STATUS_SKIPPED)
        self.assertEqual(len(calls), 0)
        _, _, g2 = agent._grade(DRAFT, label="定稿")
        self.assertEqual(g2.status, STATUS_PASS)
        self.assertEqual(len(calls), 1)

