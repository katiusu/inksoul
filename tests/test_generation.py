"""生成控制测试：离线路径 + 假模型（不联网）。"""
import json
import unittest

from inksoul.config import InkSoulConfig
from inksoul.errors import ConfigError
from inksoul.generation import (CreationBrief, build_plan, generate, revise,
                                revision_prompt, _clean_output)
from inksoul.llm import LLMClient
from inksoul.reviewer import LiteraryIssue, ReviewReport


def fake_client(text, status=200):
    def transport(method, url, headers, body, timeout):
        if status != 200:
            return status, "err"
        return 200, json.dumps({"choices": [{"message": {"content": text}}],
                                "usage": {"total_tokens": 10}}, ensure_ascii=False)
    from inksoul.config import ModelConfig
    return LLMClient(ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m"),
                     transport=transport, sleep=lambda s: None)


class TestPlan(unittest.TestCase):
    def test_offline_plan_has_presets(self):
        cfg = InkSoulConfig()
        plan = build_plan(CreationBrief(theme="雨夜重逢", genre="小说"), cfg)
        self.assertTrue(plan.voice)
        self.assertTrue(plan.sentence_policy)
        self.assertTrue(any("未配置模型" in n for n in plan.notes))
        self.assertIn("【文体规划】", plan.as_prompt())

    def test_genre_differs(self):
        cfg = InkSoulConfig()
        a = build_plan(CreationBrief(theme="x", genre="小说"), cfg)
        b = build_plan(CreationBrief(theme="x", genre="散文"), cfg)
        self.assertNotEqual(a.rhythm, b.rhythm)

    def test_llm_refines_plan(self):
        plan_json = json.dumps({"voice": "冷调第一人称", "rhythm": "短句为主",
                                "dialogue": "几乎无对话", "sentence_policy": ["a", "b"],
                                "forbidden": ["c"]}, ensure_ascii=False)
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig(),
                          client=fake_client(plan_json), use_llm=True)
        self.assertEqual(plan.voice, "冷调第一人称")
        self.assertEqual(plan.sentence_policy, ["a", "b"])

    def test_llm_failure_falls_back(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig(),
                          client=fake_client("", status=401), use_llm=True)
        self.assertTrue(plan.voice)  # 退回先验
        self.assertTrue(any("沿用先验" in n for n in plan.notes))


class TestGenerate(unittest.TestCase):
    def test_requires_api(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig())
        with self.assertRaises(ConfigError):
            generate(CreationBrief(theme="x"), plan, None, offline=False)

    def test_offline_flag(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig())
        with self.assertRaises(ConfigError):
            generate(CreationBrief(theme="x"), plan, fake_client("正文"), offline=True)

    def test_fenced_output_cleaned(self):
        plan = build_plan(CreationBrief(theme="x", target_chars=50), InkSoulConfig())
        draft = generate(CreationBrief(theme="x"), plan, fake_client("```\n他推开门。\n```"))
        self.assertEqual(draft.text, "他推开门。")
        self.assertGreater(draft.temperature, 0)


class TestRevise(unittest.TestCase):
    def review(self, text):
        issue = LiteraryIssue(kind="机械复用", clause_id="c1", text=text,
                              severity=0.8, suggestion="换个结构")
        return ReviewReport(issues=[issue], verdict="建议修订")

    def test_offline_revise_skips(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig())
        res = revise("他推开门。她关窗户。", self.review("他推开门。"), None, plan, offline=True)
        self.assertEqual(res.applied, 0)
        self.assertEqual(res.text, "他推开门。她关窗户。")
        self.assertTrue(res.notes)

    def test_revise_replaces_sentence(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig())
        text = "他推开门。她关上窗户。"
        res = revise(text, self.review("他推开门。"), fake_client("门被他推开了。"), plan)
        self.assertEqual(res.applied, 1)
        self.assertIn("门被他推开了。", res.text)

    def test_revise_skip_when_text_missing(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig())
        res = revise("完全不同的句子。", self.review("他推开门。"), fake_client("x"), plan)
        self.assertEqual(res.applied, 0)

    def test_revision_prompt_has_window(self):
        plan = build_plan(CreationBrief(theme="x"), InkSoulConfig())
        p = revision_prompt(["机械复用：换结构"], {"prev": "上句", "cur": "问题句", "next": "下句"}, plan)
        self.assertIn("问题句", p)
        self.assertIn("只输出改写后的那一句", p)

    def test_clean_output(self):
        self.assertEqual(_clean_output("```text\n正文\n```"), "正文")


if __name__ == "__main__":
    unittest.main()
