"""模型接口测试：全部走假 transport，不联网、不需要 Key。"""
import json
import unittest

from inksoul.config import ModelConfig
from inksoul.errors import ConfigError, ModelAPIError
from inksoul.llm import LLMClient


def ok_body(text="正文"):
    return json.dumps({"model": "m", "choices": [{"message": {"content": text},
                                                  "finish_reason": "stop"}],
                       "usage": {"total_tokens": 42}}, ensure_ascii=False)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        status, text = self.responses.pop(0) if self.responses else (200, ok_body())
        return status, text


class TestLLMClient(unittest.TestCase):
    def cfg(self, **kw):
        base = dict(base_url="http://x/v1", api_key="sk-test", model="m", max_retries=1)
        base.update(kw)
        return ModelConfig(**base)

    def test_missing_key_raises_config_error(self):
        client = LLMClient(self.cfg(api_key=""))
        with self.assertRaises(ConfigError) as ctx:
            client.chat([{"role": "user", "content": "hi"}])
        self.assertIn("api_key", str(ctx.exception))

    def test_success(self):
        t = FakeTransport([(200, ok_body("他推开门。"))])
        client = LLMClient(self.cfg(), transport=t, sleep=lambda s: None)
        resp = client.chat([{"role": "user", "content": "写一句"}])
        self.assertEqual(resp.text, "他推开门。")
        self.assertEqual(resp.usage["total_tokens"], 42)
        self.assertIn("Bearer sk-test", t.calls[0]["headers"]["Authorization"])

    def test_endpoint_join(self):
        c = LLMClient(self.cfg(base_url="http://x/v1/"))
        self.assertEqual(c.endpoint, "http://x/v1/chat/completions")
        c2 = LLMClient(self.cfg(base_url="http://x/v1/chat/completions"))
        self.assertEqual(c2.endpoint, "http://x/v1/chat/completions")

    def test_retry_on_500_then_success(self):
        t = FakeTransport([(500, "boom"), (200, ok_body("ok"))])
        client = LLMClient(self.cfg(), transport=t, sleep=lambda s: None)
        resp = client.chat([{"role": "user", "content": "x"}])
        self.assertEqual(resp.text, "ok")
        self.assertEqual(resp.attempts, 2)

    def test_retry_exhausted(self):
        t = FakeTransport([(503, "busy"), (503, "busy")])
        client = LLMClient(self.cfg(), transport=t, sleep=lambda s: None)
        with self.assertRaises(ModelAPIError) as ctx:
            client.chat([{"role": "user", "content": "x"}])
        self.assertIn("已重试", str(ctx.exception))

    def test_401_no_retry(self):
        t = FakeTransport([(401, "bad key")])
        client = LLMClient(self.cfg(), transport=t, sleep=lambda s: None)
        with self.assertRaises(ModelAPIError):
            client.chat([{"role": "user", "content": "x"}])
        self.assertEqual(len(t.calls), 1)

    def test_error_never_leaks_key(self):
        t = FakeTransport([(401, "invalid sk-test")])
        client = LLMClient(self.cfg(api_key="sk-secret"), transport=t, sleep=lambda s: None)
        with self.assertRaises(ModelAPIError) as ctx:
            client.chat([{"role": "user", "content": "x"}])
        self.assertNotIn("sk-secret", str(ctx.exception))
        self.assertNotIn("sk-secret", json.dumps(ctx.exception.detail, ensure_ascii=False))

    def test_non_json_response(self):
        t = FakeTransport([(200, "<html>首页</html>")])
        client = LLMClient(self.cfg(), transport=t, sleep=lambda s: None)
        with self.assertRaises(ModelAPIError) as ctx:
            client.chat([{"role": "user", "content": "x"}])
        self.assertIn("不是合法 JSON", str(ctx.exception))

    def test_empty_choices(self):
        t = FakeTransport([(200, json.dumps({"choices": []}))])
        client = LLMClient(self.cfg(), transport=t, sleep=lambda s: None)
        with self.assertRaises(ModelAPIError):
            client.chat([{"role": "user", "content": "x"}])

    def test_empty_messages(self):
        client = LLMClient(self.cfg(), transport=FakeTransport([]))
        with self.assertRaises(ConfigError):
            client.chat([])

    def test_oversize_messages(self):
        client = LLMClient(self.cfg(), transport=FakeTransport([]))
        with self.assertRaises(ConfigError) as ctx:
            client.chat([{"role": "user", "content": "字" * 200_001}])
        self.assertIn("上限", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
