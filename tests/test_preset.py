"""agent 预设档测试：取值、优先级、CLI 入口。"""
import contextlib
import io
import unittest

from inksoul.cli import main
from inksoul.config import (AGENT_PRESETS, ConfigError, GATE_COMMANDS, merge_preset,
                            resolve_gate, resolve_preset)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestPresetRegistry(unittest.TestCase):
    def test_known_presets(self):
        for name in ("draft", "long", "short", "rewrite", "publish", "cover"):
            self.assertIn(name, AGENT_PRESETS)
        self.assertEqual(resolve_preset("long").story, "long")
        self.assertEqual(resolve_preset("draft").max_rounds, 0)
        self.assertTrue(resolve_preset("rewrite").require_from)
        self.assertEqual(resolve_preset("publish").deliver, "publish")

    def test_empty_is_none(self):
        self.assertIsNone(resolve_preset(""))

    def test_unknown_raises(self):
        with self.assertRaises(ConfigError):
            resolve_preset("nope")


class TestMerge(unittest.TestCase):
    def test_preset_fills_gaps(self):
        got = merge_preset(resolve_preset("long"))
        self.assertEqual(got["story"], "long")
        self.assertEqual(got["candidates"], 3)
        self.assertEqual(got["max_rounds"], 3)
        self.assertEqual(got["target_chars"], 3000)

    def test_explicit_wins(self):
        got = merge_preset(resolve_preset("long"), story="off", candidates=1, rounds=0)
        self.assertEqual(got["story"], "off")
        self.assertEqual(got["candidates"], 1)
        self.assertEqual(got["max_rounds"], 0)

    def test_no_preset_keeps_defaults(self):
        got = merge_preset(None)
        self.assertEqual(got["story"], "")
        self.assertIsNone(got["candidates"])
        self.assertIsNone(got["max_rounds"])


class TestPresetCLI(unittest.TestCase):
    def test_list_presets(self):
        code, out, _ = run(["agent", "--list-presets"])
        self.assertEqual(code, 0)
        for name in ("draft", "long", "short", "rewrite", "publish", "cover"):
            self.assertIn(name, out)

    def test_rewrite_requires_from(self):
        code, _, err = run(["agent", "一个题材", "--preset", "rewrite", "--offline"])
        self.assertEqual(code, 2)
        self.assertIn("--from", err)

    def test_missing_brief(self):
        code, _, err = run(["agent"])
        self.assertEqual(code, 2)
        self.assertIn("缺少题材", err)

    def test_unknown_preset_rejected_by_argparse(self):
        with self.assertRaises(SystemExit):
            run(["agent", "x", "--preset", "nope"])


class TestGateAliases(unittest.TestCase):
    def test_deslop_alias(self):
        self.assertEqual(resolve_gate("deslop"), GATE_COMMANDS["deslop"])
        self.assertIn("{file}", resolve_gate("deslop"))

    def test_off_and_empty(self):
        self.assertEqual(resolve_gate(""), "")
        self.assertEqual(resolve_gate("off"), "")

    def test_raw_command_passthrough(self):
        cmd = "python3 /root/deslop/run_gates.sh {file}"
        self.assertEqual(resolve_gate(cmd), cmd)

    def test_unknown_alias_rejected(self):
        with self.assertRaises(ConfigError):
            resolve_gate("magic")

    def test_deai_preset_carries_gate(self):
        self.assertEqual(AGENT_PRESETS["deai"].gate, "deslop")

    def test_long_short_publish_carry_gate(self):
        for name in ("long", "short", "publish"):
            self.assertEqual(AGENT_PRESETS[name].gate, "deslop", name)

    def test_draft_cover_rewrite_no_gate(self):
        for name in ("draft", "cover", "rewrite"):
            self.assertEqual(AGENT_PRESETS[name].gate, "", name)

    def test_merge_gate_precedence(self):
        self.assertEqual(merge_preset(AGENT_PRESETS["deai"])["gate"], "deslop")
        self.assertEqual(merge_preset(AGENT_PRESETS["deai"], gate="off")["gate"], "off")
        self.assertEqual(merge_preset(None)["gate"], "")


if __name__ == "__main__":
    unittest.main()