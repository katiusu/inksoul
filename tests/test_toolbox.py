"""标准模式工具面测试：四个工具 + function-calling 循环 + Agent 侦察接线。"""
import json
import tempfile
import unittest
from pathlib import Path

from inksoul.config import InkSoulConfig, ModelConfig
from inksoul.llm import LLMClient
from inksoul.toolbox import ToolBox, run_tool_loop

PLAN = json.dumps({"voice": "冷调", "rhythm": "长短交替", "dialogue": "少标签",
                   "sentence_policy": ["a"], "forbidden": ["b"]}, ensure_ascii=False)
DRAFT = "他把门推开。他把门推开。他把门推开。雨敲着铁皮棚子，一阵紧一阵松，像有人在上面来回走。"


def make_cfg() -> InkSoulConfig:
    cfg = InkSoulConfig()
    cfg.model = ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m")
    return cfg


class FakeClient:
    """按脚本返回：先给一次 tool_calls，再给最终文本。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": list(messages), **kwargs})
        item = self.script.pop(0) if self.script else {"text": ""}
        return type("R", (), {"text": item.get("text", ""),
                              "tool_calls": item.get("tool_calls", [])})()


class TestSchema(unittest.TestCase):
    def test_four_tools(self):
        box = ToolBox(make_cfg())
        self.assertEqual(box.names, ["read_prev", "lookup_bible", "measure", "run_gate"])
        schema = box.schema()
        self.assertTrue(all(s["type"] == "function" for s in schema))
        self.assertEqual(schema[0]["function"]["name"], "read_prev")


class TestTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = make_cfg()
        self.cfg.home = self.root
        self.box = ToolBox(self.cfg, roots=[self.root])

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_prev_ok(self):
        f = self.root / "prev.txt"
        f.write_text("开头。" + "中间。" * 100 + "结尾一句。", encoding="utf-8")
        out = json.loads(self.box.dispatch("read_prev", {"path": str(f), "limit": 20}))
        self.assertEqual(out["chars"] > 20, True)
        self.assertTrue(out["text"].endswith("结尾一句。"))

    def test_read_prev_outside_root_denied(self):
        out = json.loads(self.box.dispatch("read_prev", {"path": "/etc/hostname"}))
        self.assertIn("error", out)

    def test_read_prev_missing(self):
        out = json.loads(self.box.dispatch("read_prev", {"path": str(self.root / "nope.txt")}))
        self.assertIn("error", out)

    def test_lookup_bible(self):
        d = self.root / "bible"
        d.mkdir()
        (d / "char.md").write_text("# 人物\n阿七：码头守夜人，左手有疤。\n\n无关行。", encoding="utf-8")
        out = json.loads(self.box.dispatch("lookup_bible", {"query": "阿七", "top": 2}))
        self.assertEqual(len(out["hits"]), 1)
        self.assertIn("码头守夜人", out["hits"][0]["text"])

    def test_measure(self):
        out = json.loads(self.box.dispatch("measure", {"text": "短句。这是一个稍微长一点的句子，有逗号。"}))
        self.assertEqual(out["sentences"], 2)
        self.assertGreater(out["avg_sentence"], 0)
        self.assertGreater(out["cv"], 0)

    def test_measure_empty(self):
        out = json.loads(self.box.dispatch("measure", {"text": "  "}))
        self.assertIn("error", out)

    def test_run_gate_with_runner(self):
        def runner(line, timeout):
            return 1, "prose_dense        FAIL   句末单字 0 处\nVERDICT: FAIL\nRECEIPT: x rc=1"
        box = ToolBox(self.cfg, roots=[self.root], runner=runner)
        out = json.loads(box.dispatch("run_gate", {"text": "他把门推开。", "gate": "deslop"}))
        self.assertEqual(out["status"], "fail")
        self.assertEqual(len(out["findings"]), 1)

    def test_unknown_tool(self):
        out = json.loads(self.box.dispatch("nope", {}))
        self.assertIn("error", out)

    def test_bad_args(self):
        out = json.loads(self.box.dispatch("measure", {"wrong": 1}))
        self.assertIn("error", out)


class TestGateFd(unittest.TestCase):
    def test_run_gate_does_not_leak_fds(self):
        import os
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("没有 /proc/self/fd")
        box = ToolBox(make_cfg(), gate_cmd="true {file}", gate_timeout=5,
                      runner=lambda line, t: (0, "VERDICT: PASS"))
        before = len(os.listdir("/proc/self/fd"))
        for _ in range(30):
            box._run_gate("正文文本", "deslop")
        self.assertLessEqual(len(os.listdir("/proc/self/fd")) - before, 2)


class TestLoop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "prev.txt").write_text("前情提要：阿七在渡口等船。", encoding="utf-8")
        self.cfg = make_cfg()
        self.cfg.home = self.root
        self.box = ToolBox(self.cfg, roots=[self.root])

    def tearDown(self):
        self.tmp.cleanup()

    def test_tool_then_answer(self):
        client = FakeClient([
            {"tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "read_prev",
                                          "arguments": json.dumps({"path": str(self.root / "prev.txt")})}}]},
            {"text": "侦察完毕：主角是阿七。"},
        ])
        res = run_tool_loop(client, [{"role": "user", "content": "查前文"}], self.box, max_steps=3)
        self.assertEqual(res.text, "侦察完毕：主角是阿七。")
        self.assertEqual(len(res.steps), 1)
        self.assertEqual(res.steps[0].tool, "read_prev")
        # 第二次请求里应带上 tool 结果
        tool_msgs = [m for m in client.calls[1]["messages"] if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertIn("阿七", tool_msgs[0]["content"])
        self.assertTrue(client.calls[0]["tools"])

    def test_max_steps(self):
        call = {"tool_calls": [{"id": "c", "type": "function",
                                "function": {"name": "measure", "arguments": "{\"text\": \"句子。\"}"}}]}
        client = FakeClient([call, call, call])
        res = run_tool_loop(client, [{"role": "user", "content": "x"}], self.box, max_steps=2)
        self.assertEqual(res.stopped, "max-steps")
        self.assertEqual(len(res.steps), 2)
        self.assertEqual(res.text, "")

    def test_bad_json_arguments(self):
        client = FakeClient([
            {"tool_calls": [{"id": "c", "type": "function",
                             "function": {"name": "measure", "arguments": "{not json"}}]},
            {"text": "ok"},
        ])
        res = run_tool_loop(client, [{"role": "user", "content": "x"}], self.box, max_steps=2)
        self.assertEqual(res.steps[0].args, {})
        self.assertIn("error", res.steps[0].result)
        self.assertEqual(res.text, "ok")


class TestLLMTools(unittest.TestCase):
    def test_payload_and_parse(self):
        seen = {}

        def transport(method, url, headers, body, timeout):
            seen.update(json.loads(body))
            msg = {"content": "", "tool_calls": [{"id": "c1", "type": "function",
                                                  "function": {"name": "measure", "arguments": "{}"}}]}
            return 200, json.dumps({"choices": [{"message": msg}]})

        client = LLMClient(make_cfg().model, transport=transport, sleep=lambda s: None)
        resp = client.chat([{"role": "user", "content": "hi"}],
                           tools=[{"type": "function", "function": {"name": "measure"}}],
                           tool_choice="auto")
        self.assertIn("tools", seen)
        self.assertEqual(seen["tool_choice"], "auto")
        self.assertEqual(len(resp.tool_calls), 1)
        self.assertEqual(resp.as_dict()["tool_calls"], 1)


class TestAgentRecon(unittest.TestCase):
    def test_recon_notes_enter_generation(self):
        from inksoul.agent import WritingAgent

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "prev.txt").write_text("前情：阿七在渡口等船。", encoding="utf-8")
        cfg = make_cfg()
        cfg.home = root
        bodies = []

        def transport(method, url, headers, body, timeout):
            payload = json.loads(body)
            bodies.append(payload)
            prompt = " ".join(str(m.get("content", "")) for m in payload.get("messages", []))
            if "资料侦察员" in prompt:
                if any(m.get("role") == "tool" for m in payload["messages"]):
                    msg = {"content": "侦察：主角叫阿七，在渡口。"}
                else:
                    msg = {"content": "", "tool_calls": [{
                        "id": "c1", "type": "function",
                        "function": {"name": "read_prev",
                                     "arguments": json.dumps({"path": str(root / "prev.txt")})}}]}
            elif "文体策略" in prompt:
                msg = {"content": PLAN}
            else:
                msg = {"content": DRAFT}
            return 200, json.dumps({"choices": [{"message": msg}]}, ensure_ascii=False)

        client = LLMClient(cfg.model, transport=transport, sleep=lambda s: None)
        agent = WritingAgent(cfg, client=client, story="off",
                             tool_mode="standard", tool_steps=2)
        agent.toolbox.roots = [root.resolve()]
        result = agent.run("渡口夜话", candidates=1, max_rounds=1)
        self.assertEqual(len(result.tool_steps), 1)
        self.assertEqual(result.tool_steps[0]["tool"], "read_prev")
        self.assertTrue(any("侦察阶段调用工具" in n for n in result.notes))
        gen_prompts = [" ".join(str(m.get("content", "")) for m in b["messages"])
                       for b in bodies
                       if any("资料侦察员" not in str(m.get("content", "")) for m in b["messages"])]
        self.assertTrue(any("侦察：主角叫阿七" in p for p in gen_prompts))


if __name__ == "__main__":
    unittest.main()
