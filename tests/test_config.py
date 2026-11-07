"""配置测试：脱敏、保存/加载、非法值提示。"""
import json
import tempfile
import unittest
from pathlib import Path

from inksoul.config import InkSoulConfig, load_config, save_config
from inksoul.errors import ConfigError


class TestConfig(unittest.TestCase):
    def test_default_redacts_key(self):
        cfg = InkSoulConfig()
        cfg.model.api_key = "sk-abcdef123456"
        blob = json.dumps(cfg.to_dict(redact=True), ensure_ascii=False)
        self.assertNotIn("sk-abcdef123456", blob)

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            cfg = InkSoulConfig()
            cfg.model.model = "deepseek-chat"
            cfg.model.temperature = 0.7
            save_config(cfg, p)
            back = load_config(p)
            self.assertEqual(back.model.model, "deepseek-chat")
            self.assertAlmostEqual(back.model.temperature, 0.7)

    def test_missing_config_raises(self):
        with self.assertRaises(ConfigError):
            load_config("/nope/none.json")

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(p)

    def test_unknown_key_is_rejected_loudly(self):
        # 拼错的配置项必须报错，而不是静默忽略（否则用户会以为设置生效了）
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"model": {"model": "m", "unknown": 1}}), encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load_config(p)
            self.assertIn("unknown", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
