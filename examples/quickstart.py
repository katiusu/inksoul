#!/usr/bin/env python3
"""InkSoul 最小可运行示例：输入一段创作要求，输出文体规划 + 自检报告。

用法：
    python3 examples/quickstart.py                    # 用内置示例需求（离线）
    python3 examples/quickstart.py "雨夜，旧友重逢"     # 自定义需求
    INKSOUL_API_KEY=sk-… python3 examples/quickstart.py "…"   # 有 Key 时额外生成正文

没有 API Key 时**不会**伪造正文：只给规划 + 对示例草稿的诊断，并说明如何开启生成。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from inksoul import Analyzer, load_config          # noqa: E402
from inksoul.generation import GenerationController  # noqa: E402

DEMO_BRIEF = "雨夜，旧书店，两个十年未见的老同学重逢，气氛克制，结尾留一个未说出口的问题。"

#: 离线演示用的「初稿」：故意写得机械，用来看诊断能抓到什么
DEMO_DRAFT = """他慢慢地推开了旧书店的门，走进了屋里。她慢慢地推开了旧书店的门，走进了屋里。
他轻轻地关上了伞，走进了屋里。她轻轻地关上了伞，走进了屋里。
他看着书架，没有说话。她看着书架，没有说话。
屋里很安静，什么也没有。雨声很安静，什么也没有。
"""


def main(argv: list[str]) -> int:
    brief = argv[1] if len(argv) > 1 else DEMO_BRIEF
    cfg = load_config()
    print(f"创作要求：{brief}\n")

    ctrl = GenerationController(cfg)
    plan = ctrl.plan(brief, genre="小说", perspective="第三人称限制")
    print("== 文体规划 ==")
    for k, v in plan.as_dict().items():
        if isinstance(v, list):
            v = "；".join(str(x) for x in v)
        print(f"  {k}: {v}")

    if ctrl.client is not None and ctrl.client.available:
        print("\n== 生成正文（调用模型）==")
        res = ctrl.generate(brief, genre="小说")
        print(res.text)
        print(f"\n候选 {res.candidates} 份｜修订 {res.revisions} 处")
        for note in res.notes:
            print(f"  - {note}")
        return 0

    print("\n（未配置 API Key：跳过生成。设置 INKSOUL_API_KEY 后重跑即可生成正文。）")
    print("\n== 对示例初稿的诊断 ==")
    rep = Analyzer(cfg).analyze(DEMO_DRAFT)
    data = rep.as_dict()
    fp = data["fingerprint"]
    print(f"  小句 {data['meta']['clauses']}｜不同骨架 {fp['distinct_patterns']} 种｜复用率 {fp['reuse_rate']:.0%}")
    for p in fp["top_patterns"][:3]:
        print(f"  {p['share']:.0%}  {p['signature']}  ×{p['count']}")
    print(f"  审阅结论：{data['review']['verdict']}")
    for issue in data["review"]["issues"][:3]:
        print(f"   - {issue['kind']}：{issue['text']}（{issue['suggestion'][:40]}…）")
    print("\n完整 JSON：inksoul analyze 稿子.txt --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
