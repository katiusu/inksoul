"""style guard：修订/整篇重写都要接受「离人类池不更远」这个条件（v0.5.1）。"""
import json
import unittest
from unittest import mock

from inksoul.config import InkSoulConfig, ModelConfig
from inksoul.generation import (CreationBrief, StylePlan, build_plan, restyle,
                                revise, _human_target_lines)
from inksoul.llm import LLMClient


def fake_client(text):
    def transport(method, url, headers, body, timeout):
        return 200, json.dumps({"choices": [{"message": {"content": text}}],
                                "usage": {"total_tokens": 10}}, ensure_ascii=False)
    return LLMClient(ModelConfig(base_url="http://x/v1", api_key="sk-t", model="m"),
                     transport=transport, sleep=lambda s: None)


def review_one(text, severity=0.8):
    from inksoul.reviewer import LiteraryIssue, ReviewReport
    return ReviewReport(issues=[LiteraryIssue(kind="机械复用", clause_id="c1",
                                              text=text, severity=severity,
                                              suggestion="换个结构")],
                        verdict="建议修订")


class TestReviseStyleGuard(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(CreationBrief(theme="雨夜", genre="小说"), InkSoulConfig())

    def test_rejects_when_distance_rises(self):
        with mock.patch("inksoul.generation._style_distance", side_effect=[1.0, 1.6, 1.6]):
            res = revise("他推开门。", review_one("他推开门。"),
                         fake_client("风把门吹开了。"), self.plan)
        self.assertEqual(res.applied, 0)
        self.assertIn("他推开门。", res.text)

    def test_accepts_when_distance_stable(self):
        with mock.patch("inksoul.generation._style_distance", side_effect=[1.0, 1.02]):
            res = revise("他推开门。", review_one("他推开门。"),
                         fake_client("风把门吹开了。"), self.plan)
        self.assertEqual(res.applied, 1)
        self.assertIn("风把门吹开了。", res.text)

    def test_guard_off_ignores_distance(self):
        with mock.patch("inksoul.generation._style_distance", side_effect=[1.0, 9.0, 1.0, 9.0]):
            res = revise("他推开门。", review_one("他推开门。"),
                         fake_client("风把门吹开了。"), self.plan, style_guard=False)
        self.assertEqual(res.applied, 1)


class TestRestyleStyleGuard(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(CreationBrief(theme="雨夜", genre="小说"), InkSoulConfig())
        self.text = "他推开门，风灌进来。她把外套挂好。" * 20

    def test_keeps_original_when_farther(self):
        with mock.patch("inksoul.generation._style_distance", side_effect=[1.0, 1.9]):
            res = restyle(self.text, ["连接词过密"], fake_client(self.text), self.plan)
        self.assertEqual(res.text, self.text)
        self.assertIn("人类池", res.notes[0])


class TestHumanTargetsInPrompt(unittest.TestCase):
    def test_targets_present(self):
        lines = _human_target_lines()
        self.assertTrue(lines)
        prompt = StylePlan(genre="网文", voice="贴身第三人称", rhythm="中等",
                           dialogue="口语").as_prompt()
        self.assertIn("人类写法目标", prompt)
        self.assertIn("长句占比", prompt)


if __name__ == "__main__":
    unittest.main()