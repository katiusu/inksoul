#!/usr/bin/env python3
"""用真实人类语料标定 markers 的基线分位数。

用法：
    PYTHONPATH=python python3 scripts/calibrate_markers.py --genre 网文 \
        --chunk 3000 --step 1500 --out python/inksoul/data/marker_baseline_zh.json \
        人类语料.txt [更多文件...]

做的是「人类分布」而不是「AI 判定」：把长文切块，每块算每千字标记密度，
取 p50/p90/p99 作为后续比较的参照点。换语料就重跑，不要手改 JSON。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from inksoul.markers import analyze_markers, KINDS  # noqa: E402
from inksoul.text_processor import process  # noqa: E402


def pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--genre", default="网文")
    ap.add_argument("--chunk", type=int, default=3000)
    ap.add_argument("--step", type=int, default=1500)
    ap.add_argument("--min-narrative", type=int, default=800)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = {k: [] for k in KINDS}
    chunks = 0
    skipped = 0
    sources = []
    for path in args.files:
        text = open(path, encoding="utf-8").read()
        sources.append({"name": os.path.basename(path), "chars": len(text)})
        pos = 0
        while pos + args.chunk <= len(text):
            piece = text[pos:pos + args.chunk]
            pos += args.step
            try:
                doc = process(piece)
            except Exception:
                skipped += 1
                continue
            rep = analyze_markers(doc)
            if rep.narrative_chars < args.min_narrative:
                skipped += 1
                continue
            chunks += 1
            for k in KINDS:
                rows[k].append(rep.per_1000.get(k, 0.0))

    payload = {
        "version": 1,
        "generated": datetime.date.today().isoformat(),
        "genre": args.genre,
        "method": "长文按 %d 字窗口 / %d 字步长切块；每块只统计叙述句（去引号句），"
                  "算每千字密度；剔除叙述字数 < %d 的块；分位数线性插值。" % (args.chunk, args.step, args.min_narrative),
        "sources": sources,
        "genres": {args.genre: {"chunks": chunks, "skipped": skipped,
                                "per_1000": {k: {
                                    "mean": round(statistics.mean(rows[k]), 2) if rows[k] else 0.0,
                                    "p50": round(pct(sorted(rows[k]), 0.50), 2),
                                    "p90": round(pct(sorted(rows[k]), 0.90), 2),
                                    "p99": round(pct(sorted(rows[k]), 0.99), 2),
                                } for k in KINDS}}},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print("chunks=%d skipped=%d -> %s" % (chunks, skipped, args.out))
    for k in KINDS:
        s = payload["genres"][args.genre]["per_1000"][k]
        print("  %-10s p50=%5.2f p90=%5.2f p99=%5.2f" % (k, s["p50"], s["p90"], s["p99"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
