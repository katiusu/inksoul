"""PTC 工具基座测试：AST 校验、子进程执行、代码提取、循环与 Agent 接线。"""
import json
import tempfile
import unittest
from pathlib import Path

from inksoul.config import InkSoulConfig, ModelConfig
from inksoul.ptc import (PtcError, extract_code, run_program, run_ptc_loop,
                         validate_code)
from inksoul.toolbox import ToolBox


def make_cfg():
    return InkSoulConfig(model=ModelConfig(api_key="k"))


class FakeClient:
    """按脚本返回文本；记录每次请求的 messages。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": [dict(m) for m in messages], **kwargs})
        text = self.script.pop(0) if self.script else "（结束）"
        return type("R", (), {"text": text, "tool_calls": []})()


class TestValidate(unittest.TestCase):
    def test_import_rejected(self):
        with self.assertRaises(PtcError):
            validate_code("import os")

    def test_open_rejected(self):
        with self.assertRaises(PtcError):
            validate_code("open('/etc/passwd')")

    def test_dunder_rejected(self):
        with self.assertRaises(PtcError):
            validate_code("x = (1).__class__")

    def test_normal_program_accepted(self):
        validate_code("rows = []" + chr(10) + "for i in range(3):" + chr(10)
                      + "    rows.append(measure(str(i)))" + chr(10) + "print(rows)")


class TestExtract(unittest.TestCase):
    def test_python_fence(self):
        text = "先看前文" + chr(10) + "```python" + chr(10) + "print(1)" + chr(10) + "```"
        self.assertEqual(extract_code(text), "print(1)")

    def test_bare_fence(self):
        text = "```" + chr(10) + "print(2)" + chr(10) + "```"
        self.assertEqual(extract_code(text), "print(2)")

    def test_no_fence(self):
        self.assertEqual(extract_code("结论：主角叫阿七。"), "")


class TestRunProgram(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "prev.txt").write_text("前情：阿七在渡口等船。", encoding="utf-8")
        self.box = ToolBox(make_cfg(), roots=[self.root])

    def test_tools_available(self):
        code = ("d = read_prev(%r)" % str(self.root / "prev.txt") + chr(10)
                + "print(d['chars'])" + chr(10)
                + "print(measure('你好。世界。')['sentences'])")
        res = run_program(code, self.box, timeout=30)
        self.assertEqual(res.error, "")
        self.assertEqual(res.stdout.splitlines(), ["11", "2"])

    def test_loop_inside_program(self):
        code = "n = 0" + chr(10) + "for i in range(5):" + chr(10) + "    n += i" + chr(10) + "print(n)"
        res = run_program(code, self.box, timeout=30)
        self.assertEqual(res.stdout.strip(), "10")

    def test_runtime_error_captured(self):
        res = run_program("raise ValueError('boom')", self.box, timeout=30)
        self.assertIn("ValueError", res.error)
        self.assertIn("boom", res.error)

    def test_forbidden_call_blocked_before_spawn(self):
        res = run_program("open(%r)" % str(self.root / "prev.txt"), self.box)
        self.assertIn("open", res.error)
        self.assertEqual(res.elapsed, 0.0)

    def test_timeout(self):
        res = run_program("while True:" + chr(10) + "    pass", self.box, timeout=1.0)
        self.assertIn("超时", res.error)


class TestPtcLoop(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "prev.txt").write_text("阿七在渡口。", encoding="utf-8")
        self.box = ToolBox(make_cfg(), roots=[self.root])

    def test_code_then_conclusion(self):
        code = "```python" + chr(10) + "print(read_prev(%r)['chars'])" % str(self.root / "prev.txt") + chr(10) + "```"
        client = FakeClient([code, "侦察完毕：主角叫阿七。"])
        res = run_ptc_loop(client, [{"role": "user", "content": "查前文"}], self.box, max_rounds=3)
        self.assertEqual(res.text, "侦察完毕：主角叫阿七。")
        self.assertEqual(len(res.programs), 1)
        self.assertIn("6", res.programs[0]["stdout"])
        feedback = client.calls[1]["messages"][-1]["content"]
        self.assertIn("程序执行结果", feedback)

    def test_max_rounds(self):
        code = "```python" + chr(10) + "print(1)" + chr(10) + "```"
        client = FakeClient([code, code, code])
        res = run_ptc_loop(client, [{"role": "user", "content": "查"}], self.box, max_rounds=2)
        self.assertEqual(len(res.programs), 2)
        self.assertEqual(res.stopped, "max-rounds")

    def test_ptc_agent_recon(self):
        from inksoul.agent import WritingAgent
        from inksoul.llm import LLMClient

        bodies = []
        code = "```python" + chr(10) + "print(read_prev(%r)['text'])" % str(self.root / "prev.txt") + chr(10) + "```"

        def transport(method, url, headers, body, timeout):
            payload = json.loads(body)
            bodies.append(payload)
            prompt = " ".join(str(m.get("content", "")) for m in payload["messages"])
            if "程序化工具调用" in prompt:
                if "程序执行结果" in prompt:
                    msg = {"content": "侦察：主角阿七在渡口。"}
                else:
                    msg = {"content": code}
            elif "文体策略" in prompt:
                msg = {"content": "{}"}
            else:
                msg = {"content": "正文：" + "阿七在渡口等船。" * 20}
            return 200, json.dumps({"choices": [{"message": msg}]}, ensure_ascii=False)

        cfg = make_cfg()
        client = LLMClient(cfg.model, transport=transport, sleep=lambda s: None)
        agent = WritingAgent(cfg, client=client, story="off", tool_mode="ptc", tool_steps=2)
        agent.toolbox.roots = [self.root.resolve()]
        result = agent.run("渡口夜话", candidates=1, max_rounds=1)
        self.assertEqual(len(result.tool_steps), 1)
        self.assertIn("code", result.tool_steps[0])
        self.assertTrue(any("PTC" in n for n in result.notes))
        self.assertTrue(any("阿七在渡口" in p for p in
                            [" ".join(str(m.get("content", "")) for m in b["messages"])
                             for b in bodies]))


if __name__ == "__main__":
    unittest.main()
