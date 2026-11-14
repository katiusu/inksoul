# -*- coding: utf-8 -*-
"""重建 molds 基线：从 experiment/corpus/human/*.txt 算 mean/p10/p90，写回 molds.py 与 JSON。

用法：python3 scripts/build_molds_baseline.py [--corpus DIR]
只认 ≥20000 汉字的样本；逐本算密度再取分位（不用全书合并值，避免长书 dominate）。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import statistics as st
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from inksoul.molds import MOLDS, han_count  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "experiment" / "corpus" / "human"))
    ap.add_argument("--min-chars", type=int, default=20000)
    args = ap.parse_args()

    files = sorted(glob.glob(str(Path(args.corpus) / "*.txt")))
    texts = []
    for f in files:
        t = Path(f).read_text(encoding="utf-8", errors="ignore")
        if han_count(t) >= args.min_chars:
            texts.append(t)
    if not texts:
        print("没有可用样本：%s" % args.corpus, file=sys.stderr)
        return 2

    out: dict[str, dict] = {}
    for m in MOLDS:
        pat = re.compile(m.pattern, re.M)
        vals = sorted(len(pat.findall(t)) / han_count(t) * 1000 for t in texts)
        n = len(vals)
        out[m.key] = {
            "mean": round(st.mean(vals), 4),
            "p10": round(vals[int(n * 0.1)], 4),
            "p90": round(vals[int(n * 0.9) - 1], 4),
            "books": n,
        }

    payload = {
        "basis": {"books": len(texts), "chars": sum(han_count(t) for t in texts), "unit": "次/千汉字",
                  "corpus": str(Path(args.corpus).name)},
        "molds": out,
    }
    dst = ROOT / "src" / "inksoul" / "data" / "molds_baseline.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    src_path = ROOT / "src" / "inksoul" / "molds.py"
    src = src_path.read_text(encoding="utf-8")
    for key, b in out.items():
        pat = re.compile(r'(Mold\("%s",.*?)([\d.]+, )([\d.]+, )([\d.]+)(, "(?:over|under|neutral)")' % key, re.S)
        m = pat.search(src)
        if not m:
            print("警告：molds.py 里找不到 %s 的常量" % key, file=sys.stderr)
            continue
        repl = m.group(1) + ("%g, %g, %g" % (b["mean"], b["p10"], b["p90"])) + m.group(5)
        src = src[:m.start()] + repl + src[m.end():]
    src_path.write_text(src, encoding="utf-8")

    print("样本 %d 本 / %d 汉字 → %s" % (len(texts), payload["basis"]["chars"], dst))
    for k, b in out.items():
        print("  %-6s mean %7.3f  p10 %6.3f  p90 %6.3f" % (k, b["mean"], b["p10"], b["p90"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

