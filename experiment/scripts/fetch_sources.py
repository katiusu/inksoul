#!/usr/bin/env python3
"""抓取公有领域中文样本原文（中文维基文库），落在 experiment/data/raw_sources/。

为什么要抓而不凭记忆写：
  实验的度量依赖"分词/归一"对字面文本的稳定性；凭记忆转录会引入与记忆相关的
  字面偏差（错字、漏句），且无法审计。这里保留抓取快照 + 版本号（revid）+ sha256，
  使 experiment/sources.md 里每一条都能被第三人复核。

用法（需要联网）：
  python3 experiment/scripts/fetch_sources.py [--out experiment/data/raw_sources]

注意：
  - 只用 variant=zh-hans（简体），避免"人类样本繁体、AI 样本简体"造成分词偏差——
    这是本项目已知的混淆源，必须在报告里写明。
  - 不抓取任何仍可能在保护期内的作品（本脚本的 PAGES 列表全部是 2026-10-31 前的
    公有领域作品，见 sources.md 的作者卒年与依据）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests

API = "https://zh.wikisource.org/w/api.php"
UA = "InkSoul-experiment/0.1 (research; local corpus build)"

# key -> (页面名, 作者, 篇名, 年份, 体裁)
PAGES = {
    "h_novel_01": ("孔乙己", "鲁迅", "孔乙己", "1919", "小说"),
    "h_novel_02": ("藥", "鲁迅", "药", "1919", "小说"),
    "h_novel_03": ("祝福", "鲁迅", "祝福", "1924", "小说"),
    "h_prose_01": ("背影", "朱自清", "背影", "1925", "散文"),
    "h_prose_02": ("荷塘月色", "朱自清", "荷塘月色", "1927", "散文"),
    "h_prose_03": ("匆匆", "朱自清", "匆匆", "1922", "散文"),
    "h_dialogue_01": ("過客", "鲁迅", "过客", "1925", "对话"),
    "h_dialogue_02": ("起死", "鲁迅", "起死", "1936", "对话"),
}

BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "dd", "dt", "blockquote", "tr"}


class _TextExtractor(HTMLParser):
    """把 MediaWiki parse HTML 的正文抽成纯文本（跳过表格/导航/脚注）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._skip_tags = {"table", "style", "script", "sup", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = []
        for line in raw.splitlines():
            line = re.sub(r"[ \t\u00a0\u200b]+", "", line).strip()
            if line:
                lines.append(line)
        return "\n".join(lines)


#: 维基文库页脚许可声明、章节编辑链接、章节序号——不属于正文，必须剔除
LICENSE_MARKERS = (
    "1996年1月1日，这部作品在原著作国家",
    "这部作品在1931年1月1日以前出版",
    "本作品现时在两岸因著作权保护期届满",
    "PublicdomainPublicdomainfalsefalse",
    "这部作品也可能在本国本地版权期限更长",
)
_EDIT_LINE = re.compile(r"^\[编辑\]$")
_CN_NUM = re.compile(r"^[一二三四五六七八九十]{1,2}$")


def clean_text(text: str) -> str:
    """去掉页脚许可声明/编辑链接/章节序号，保留正文（含剧本的角色名与舞台提示）。"""
    lines = []
    for line in text.splitlines():
        if any(m in line for m in LICENSE_MARKERS):
            break
        if _EDIT_LINE.match(line) or _CN_NUM.match(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def fetch(page: str, timeout: float = 60.0) -> dict:
    params = {
        "action": "parse",
        "page": page,
        "prop": "text|revid|displaytitle",
        "format": "json",
        "formatversion": "2",
        "variant": "zh-hans",
        "redirects": "1",
    }
    resp = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"API 错误：{data['error']}")
    node = data["parse"]
    return {"html": node["text"], "revid": node.get("revid"), "title": node.get("title", page)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiment/data/raw_sources")
    ap.add_argument("--only", nargs="*", help="只抓这些 key")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest = []
    failures = []
    for key, (page, author, title, year, genre) in PAGES.items():
        if args.only and key not in args.only:
            continue
        try:
            got = fetch(page)
            parser = _TextExtractor()
            parser.feed(got["html"])
            text = parser.text()
            if len(text) < 500:
                raise RuntimeError(f"正文过短（{len(text)} 字），可能页面结构不同")
            (out / f"{key}.raw.txt").write_text(text + "\n", encoding="utf-8")
            clean = clean_text(text)
            if len(clean) < 500:
                raise RuntimeError(f"清洗后正文过短（{len(clean)} 字）")
            path = out / f"{key}.txt"
            path.write_text(clean, encoding="utf-8")
            digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            url = f"https://zh.wikisource.org/wiki/{requests.utils.quote(page)}?oldid={got['revid']}"
            manifest.append({
                "key": key, "page": page, "title": title, "author": author, "year": year,
                "genre": genre, "revid": got["revid"], "url": url, "chars": len(clean),
                "sha256": digest, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "variant": "zh-hans",
            })
            print(f"OK   {key:14s} {len(clean):6d} 字（clean）  {page}", flush=True)
        except Exception as exc:  # noqa: BLE001
            failures.append({"key": key, "page": page, "error": str(exc)})
            print(f"FAIL {key:14s} {page}: {exc}", file=sys.stderr, flush=True)
        time.sleep(0.6)

    if manifest:
        mpath = out / "manifest.json"
        old = []
        if mpath.exists():
            try:
                old = json.loads(mpath.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                old = []
        by_key = {m["key"]: m for m in old + manifest}
        mpath.write_text(json.dumps(list(by_key.values()), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nmanifest: {mpath}（{len(by_key)} 条）")
    if failures:
        print(f"\n{len(failures)} 条失败：{failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
