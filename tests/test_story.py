import json
import os
import tempfile
import unittest
from pathlib import Path

from inksoul.agent import WritingAgent, build_deliverable
from inksoul.config import InkSoulConfig, ModelConfig
from inksoul.errors import ConfigError
from inksoul.generation import CreationBrief
from inksoul.llm import LLMClient
from inksoul.story import EXCLUDED, StoryPack, discover, load_skill_block


def _write_skill(root: Path, name: str, version: str, body: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\nversion: %s\ndescription: d\n---\n%s" % (name, version, body),
        encoding="utf-8")
    return d


LONG_BODY = ("## 写前必读\n必须先生成章纲，再写正文。\n\n## 核心方法\n先定本章主导情绪，\n"
             "再排场景。\n\n## 结构\n黄金三章要给出主角处境。\n")
SHORT_BODY = ("## 写前必读\n开篇两百字内出冲突。\n\n## 核心方法\n按题材选写法。\n\n"
              "## 情绪\n情绪靠动作推。\n")
REVIEW_BODY = "## 审查维度\n- 因果\n- 节奏\n- 人物一致性\n"


class StoryDiscoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write_skill(self.root, "story-long-write", "1.2.3", LONG_BODY)
        _write_skill(self.root, "story-short-write", "0.9.0", SHORT_BODY)
        _write_skill(self.root, "story-review", "2.0.0", REVIEW_BODY)
        _write_skill(self.root, "story-cover", "1.0.0", "## 封面\n提示词。\n")
        _write_skill(self.root, "story-deslop", "1.0.0", "## 去味\n不该被接入。\n")
        (self.root / "not-a-skill").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_discover_parses_and_skips_deslop(self):
        skills = discover([str(self.root)])
        self.assertIn("story-long-write", skills)
        self.assertNotIn("story-deslop", skills)
        self.assertNotIn("not-a-skill", skills)
        self.assertEqual(skills["story-long-write"].version, "1.2.3")
        self.assertIn("必须先生成章纲", skills["story-long-write"].body)

    def test_missing_root_returns_empty(self):
        self.assertEqual(discover([str(self.root / "nope")]), {})

    def test_excluded_names_constant(self):
        self.assertIn("story-deslop", EXCLUDED)


class StoryPackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write_skill(self.root, "story-long-write", "1.2.3", LONG_BODY)
        _write_skill(self.root, "story-short-write", "0.9.0", SHORT_BODY)
        _write_skill(self.root, "story-review", "2.0.0", REVIEW_BODY)

    def tearDown(self):
        self.tmp.cleanup()

    def _pack(self, mode="auto", target_chars=0):
        return StoryPack(mode=mode, target_chars=target_chars, roots=[str(self.root)])

    def test_off_mode_does_not_require(self):
        pack = self._pack("off")
        self.assertEqual(pack.prompt_block(), "")
        self.assertIn("不要求载入", "".join(pack.notes))

    def test_long_mode_only_asks_to_load_skill(self):
        pack = self._pack("long")
        block = pack.prompt_block()
        self.assertIn("load_skill", block)
        self.assertIn("story-long-write", block)
        self.assertIn("只采纳关于写法", block)
        # 规范正文不再内联：整句要求不到 300 字，正文里的字一句都不该出现
        self.assertLess(len(block), 300)
        self.assertNotIn("黄金三章", block)
        self.assertNotIn("必须先生成章纲", block)
        self.assertIn("1.2.3", "".join(pack.notes))

    def test_auto_picks_short_for_small_target(self):
        self.assertEqual(self._pack("auto", target_chars=2000).write_skill, "story-short-write")
        self.assertEqual(self._pack("auto", target_chars=20000).write_skill, "story-long-write")

    def test_load_skill_block_lists_names(self):
        block = load_skill_block(["prose-deai", "story-review"])
        self.assertIn("prose-deai", block)
        self.assertIn("story-review", block)
        self.assertEqual(load_skill_block([]), "")
        self.assertEqual(load_skill_block([" ", ""]), "")

    def test_manifest_marks_selected(self):
        rows = {r["name"]: r for r in self._pack("short").manifest()}
        self.assertTrue(rows["story-short-write"]["selected"])
        self.assertFalse(rows["story-long-write"]["selected"])
        self.assertFalse(rows["story-cover"]["present"])
        self.assertIn("不载入", rows["story-setup"]["role"])

    def test_missing_skills_no_requirement(self):
        pack = StoryPack(mode="long", roots=[str(self.root / "nope")])
        self.assertEqual(pack.prompt_block(), "")
        self.assertIn("未找到", "".join(pack.notes))


class StoryInjectionTest(unittest.TestCase):
    def test_generate_puts_extra_system_into_system_message(self):
        from inksoul.generation import CreationBrief, StylePlan, generate

        class FakeClient:
            available = True

            def __init__(self):
                self.seen = []

            def chat(self, messages, **kw):
                self.seen.append(messages)

                class R:
                    text = "他推门进来，屋里没人。"
                    usage = {}
                    finish_reason = "stop"
                    latency_s = 0.1

                return R()

        client = FakeClient()
        plan = StylePlan(genre="小说", voice="第三人称", rhythm="短句", dialogue="少",
                        temperatures=[0.8])
        generate(CreationBrief(theme="重逢"), plan, client, extra_system="MARKER-规则")
        system = client.seen[0][0]["content"]
        self.assertIn("MARKER-规则", system)
        self.assertIn("不要用总结句收尾", system)


if __name__ == "__main__":
    unittest.main()
DRAFT = "他把门推开。" + "她把窗关上。" * 40
PLAN = json.dumps({"voice": "冷调第三人称", "rhythm": "长短交替", "dialogue": "少标签",
                   "sentence_policy": ["a"], "forbidden": ["c"]}, ensure_ascii=False)

class DeliverTest(unittest.TestCase):
    """--from / --ref / --deliver 的接线：走假模型，不联网。"""

    def _roots(self, td):
        root = Path(td)
        _write_skill(root, "story-publish", "9.9.9",
                     "## 书名" + chr(10) + "按题材起 3 个候选书名。")
        _write_skill(root, "story-cover", "1.2.0",
                     "## 提示词" + chr(10) + "输出三段封面提示词。")
        return [str(root)]

    def _client(self, seen, reply="《雨夜重逢》等三个书名"):
        def transport(method, url, headers, body, timeout):
            payload = json.loads(body.decode() if isinstance(body, bytes) else body)
            prompt = " ".join(m.get("content", "") for m in payload.get("messages", []))
            seen.append(prompt)
            if "文体策略" in prompt:
                content = PLAN
            elif "只改写" in prompt:
                content = DRAFT
            elif "候选书名" in prompt or "提示词" in prompt:
                content = reply
            else:
                content = DRAFT
            return 200, json.dumps({"choices": [{"message": {"content": content}}]},
                                   ensure_ascii=False)
        return LLMClient(ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m"),
                         transport=transport, sleep=lambda s: None)

    def test_build_deliverable_uses_skill_and_brief(self):
        with tempfile.TemporaryDirectory() as td:
            seen = []
            pack = StoryPack(roots=self._roots(td))
            text = build_deliverable("publish", pack, CreationBrief(theme="雨夜重逢"),
                                     self._client(seen))
            self.assertTrue(text)
            joined = " ".join(seen)
            self.assertIn("候选书名", joined)
            self.assertIn("雨夜重逢", joined)

    def test_build_deliverable_rejects_unknown_kind(self):
        pack = StoryPack(roots=[])
        with self.assertRaises(ConfigError):
            build_deliverable("nope", pack, CreationBrief(theme="t"), None)

    def test_run_injects_from_file_and_ref(self):
        with tempfile.TemporaryDirectory() as td:
            prev = Path(td) / "prev.txt"
            prev.write_text("上一章结尾：他关门走了。", encoding="utf-8")
            ref = Path(td) / "ref.txt"
            ref.write_text("拆解报告：开头先给冲突。", encoding="utf-8")
            seen = []
            cfg = InkSoulConfig()
            cfg.model.api_key = "sk-t"
            res = WritingAgent(cfg, client=self._client(seen), gate_cmd="", require_skills=False).run(
                "雨夜重逢", candidates=1, max_rounds=0,
                from_path=prev, refs=[str(ref)])
            joined = " ".join(seen)
            self.assertIn("他关门走了", joined)
            self.assertIn("开头先给冲突", joined)
            self.assertTrue(any("续写" in n for n in res.notes))

    def test_run_generates_deliverable(self):
        with tempfile.TemporaryDirectory() as td:
            old = os.environ.get("INKSOUL_STORY_SKILLS")
            os.environ["INKSOUL_STORY_SKILLS"] = td
            try:
                self._roots(td)
                seen = []
                cfg = InkSoulConfig()
                cfg.model.api_key = "sk-t"
                res = WritingAgent(cfg, client=self._client(seen), gate_cmd="", require_skills=False).run(
                    "雨夜重逢", candidates=1, max_rounds=0, deliver_kind="publish")
                self.assertIn("publish", res.deliverables)
                self.assertIn("publish", res.as_dict()["deliverables"])
            finally:
                if old is None:
                    os.environ.pop("INKSOUL_STORY_SKILLS", None)
                else:
                    os.environ["INKSOUL_STORY_SKILLS"] = old


class AgentLoadRequirementTest(unittest.TestCase):
    """预设不再内联规范：只要求载入，并自动开工具面让这句要求可执行。"""

    def test_agent_requires_load_skill_and_enables_tools(self):
        with tempfile.TemporaryDirectory() as td:
            _write_skill(Path(td), "story-long-write", "1.0.0", LONG_BODY)
            old = os.environ.get("INKSOUL_STORY_SKILLS")
            os.environ["INKSOUL_STORY_SKILLS"] = td
            seen = []

            def transport(method, url, headers, body, timeout):
                payload = json.loads(body.decode() if isinstance(body, bytes) else body)
                seen.append(" ".join(str(m.get("content", "")) for m in payload["messages"]))
                content = PLAN if "文体策略" in seen[-1] else DRAFT
                return 200, json.dumps({"choices": [{"message": {"content": content}}]},
                                       ensure_ascii=False)

            try:
                cfg = InkSoulConfig()
                cfg.model.api_key = "sk-t"
                client = LLMClient(ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m"),
                                   transport=transport, sleep=lambda s: None)
                agent = WritingAgent(cfg, client=client, gate_cmd="", story="long", require_skills=False)
                res = agent.run("雨夜重逢", candidates=1, max_rounds=0)
            finally:
                if old is None:
                    os.environ.pop("INKSOUL_STORY_SKILLS", None)
                else:
                    os.environ["INKSOUL_STORY_SKILLS"] = old

        joined = "\n".join(seen)
        self.assertIn("load_skill 依次读", joined)
        self.assertIn("story-long-write", joined)
        self.assertNotIn("黄金三章要给出主角处境", joined)   # 规范正文不再内联
        self.assertIsNotNone(agent.toolbox)
        self.assertTrue(any("load_skill" in n for n in res.notes))