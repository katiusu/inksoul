"""InkSoul 命令行入口。

子命令：
  inksoul analyze  <文件|目录|->         结构与文体分析（默认文本报告）
  inksoul generate <创作要求>            调用模型生成并自检修订（需配置 API Key）
  inksoul plan     <创作要求>            只输出文体规划（不调模型）
  inksoul baseline build <目录> --genre  构建体裁基线
  inksoul doctor                         环境自检
  inksoul --version                      版本

退出码：0 成功；1 输入/配置/分析错误（InkSoulError）；2 未预期错误；3 模型接口失败。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import AGENT_PRESETS, InkSoulConfig, load_config
from .errors import InkSoulError, ModelAPIError
from .logging_setup import setup_logging


def _read_text(path: Path) -> str:
    """读 UTF-8 文本；编码不对时给可执行提示，而不是抛 UnicodeDecodeError。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InkSoulError(
            f"文件不是 UTF-8 编码：{path}",
            hint="先转码：iconv -f GB18030 -t UTF-8 原文件 > 新文件",
        ) from exc


def _read_inputs(target: str) -> list[tuple[str, str]]:
    """返回 [(名字, 文本)]。目录会递归收集 .txt/.md。"""
    if target == "-":
        return [("<stdin>", sys.stdin.read())]
    p = Path(target).expanduser()
    if p.is_file():
        return [(str(p), _read_text(p))]
    if p.is_dir():
        out = []
        for f in sorted(list(p.rglob("*.txt")) + list(p.rglob("*.md"))):
            try:
                out.append((str(f), _read_text(f)))
            except OSError:
                continue
        if not out:
            raise InkSoulError(f"目录里没有 .txt/.md 文件：{p}", hint="把待分析的中文文本放进该目录")
        return out
    raise InkSoulError(f"路径不存在：{p}", hint="检查文件路径，或用 - 从标准输入读取")


def _fmt_report(rep) -> str:
    d = rep.as_dict()
    f = d["fingerprint"]
    lines = [
        "== 概览 ==",
        f"后端 {d['meta']['backend']}（依存句法：{'有' if d['meta']['has_dependency'] else '无'}）"
        f"｜段落 {d['meta']['paragraphs']}｜句 {d['meta']['sentences']}｜小句 {d['meta']['clauses']}｜字数 {d['meta']['chars']}",
        "",
        "== 句法指纹 ==",
        f"不同骨架 {f['distinct_patterns']} 种，模式熵 {f['pattern_entropy']}，复用率 {f['reuse_rate']:.0%}",
    ]
    for p in f["top_patterns"][:5]:
        lines.append(f"  {p['share']:.0%}  {p['signature']}  ×{p['count']}")
    if f["suspects"]:
        lines.append("")
        lines.append("== 机械复用嫌疑 ==")
        for s in f["suspects"][:5]:
            lines.append(f"  ×{s['freq']} 跨段{s['para_spread']} 间距变异{s['gap_cv']}  {s['signature']}")
            for ev in s["evidence"][:2]:
                lines.append(f"      · {ev}")
    div = d.get("diversity") or {}
    if not div.get("unavailable"):
        lines.append("")
        lines.append("== 句法多样性 ==")
        for key in ("adjacent_similarity_mean", "paragraph_internal_repeat_rate", "cross_paragraph_reuse_rate"):
            if key in div:
                lines.append(f"  {key} = {div[key]}")
    sty = d.get("style") or {}
    if not sty.get("unavailable"):
        lines.append("")
        lines.append("== 文体 ==")
        for key in ("ttr", "dialogue_ratio", "sentence_length_stats"):
            if key in sty:
                lines.append(f"  {key} = {sty[key]}")
    rev = d.get("review") or {}
    if rev and not rev.get("unavailable"):
        lines.append("")
        lines.append("== 审阅意见 ==")
        counts = rev.get("counts") or rev.get("severity_counts") or {}
        lines.append(f"  问题 {len(rev.get('issues', []))} 条｜严重度 {counts}")
        for it in rev.get("issues", [])[:8]:
            lines.append(f"  [{it.get('severity')}] {it.get('kind')}：{it.get('text', '')[:30]}")
            if it.get("suggestion"):
                lines.append(f"      → {it['suggestion']}")
    for note in (div.get("notes") or [])[:3] + (sty.get("notes") or [])[:2]:
        lines.append(f"注：{note}")
    return "\n".join(lines)


def cmd_analyze(args) -> int:
    cfg = load_config(args.config)
    setup_logging(cfg)
    from .analyzer import Analyzer, AnalysisReport

    analyzer = Analyzer(cfg)
    baseline = None
    if args.baseline:
        from . import fingerprint as fp

        try:
            baseline = fp.Baseline.from_dict(
                json.loads(Path(args.baseline).read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            print(f"基线读取失败：{exc}", file=sys.stderr)
            return 2
    inputs = _read_inputs(args.target)
    reports = []
    for name, text in inputs:
        try:
            rep = analyzer.analyze(text, with_review=not args.no_review, baseline=baseline)
        except InkSoulError as exc:
            print(f"[{name}] 分析失败：{exc}", file=sys.stderr)
            continue
        reports.append((name, rep))
    if not reports:
        return 2
    if args.json:
        payload = {name: rep.as_dict() for name, rep in reports}
        print(json.dumps(payload if len(payload) > 1 else next(iter(payload.values())),
                         ensure_ascii=False, indent=2))
    else:
        for name, rep in reports:
            if len(reports) > 1:
                print(f"\n######## {name} ########")
            print(_fmt_report(rep))
    return 0


def cmd_corpus(args) -> int:
    """跨作品同质度（Doshi 式集体多样性代理）。"""
    from .corpus import analyze_corpus

    inputs = _read_inputs(args.target)
    if len(inputs) < 2:
        print("至少需要 2 个文件（或目录里 2 个 .txt）才能比较", file=sys.stderr)
        return 2
    try:
        rep = analyze_corpus(dict(inputs))
    except InkSoulError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        if exc.hint:
            print(f"提示：{exc.hint}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"比较 {rep.n_compared}/{rep.n_works} 篇｜两两平均相似度 {rep.mean_pairwise_similarity:.3f}")
        if rep.max_pair:
            print(f"最像：{rep.max_pair['a']} ↔ {rep.max_pair['b']} = {rep.max_pair['similarity']:.3f}"
                  f"{'（几乎同构）' if rep.max_pair.get('near_identical') else ''}")
        if rep.min_pair:
            print(f"最不像：{rep.min_pair['a']} ↔ {rep.min_pair['b']} = {rep.min_pair['similarity']:.3f}")
        print("每篇与同侪的平均相似度：")
        for w in rep.works[:10]:
            print(f"  {w['name']}：{w['mean_similarity_to_others']:.3f}（{w['clauses']} 小句）")
        for note in rep.notes[:3]:
            print(f"注：{note}")
        # Burrows' Delta（字频风格距离）：O'Sullivan 2025 的方法
        from .stylometry import burrows_delta
        try:
            rep_d = burrows_delta(dict(inputs))
        except ValueError as exc:
            print(f"注：Delta 未计算（{exc}）")
        else:
            print(f"Burrows' Delta（字频风格距离，{rep_d.n_features} 个高频字作特征；"
                  f"请求 100 个、数字字符已剔除）："
                  f"两两平均 {rep_d.mean_pairwise_delta:.3f}｜"
                  f"最大 {rep_d.max_pair['delta']:.3f}（{rep_d.max_pair['a']} ↔ {rep_d.max_pair['b']}）｜"
                  f"最小 {rep_d.min_pair['delta']:.3f}")
    return 0


def cmd_plan(args) -> int:
    cfg = load_config(args.config)
    setup_logging(cfg)
    from .generation import GenerationController

    if getattr(args, "target_chars", 0):
        cfg.generation.target_chars = int(args.target_chars)
    plan = GenerationController(cfg).plan(args.brief, genre=args.genre, perspective=args.perspective)
    print(json.dumps(plan.as_dict() if hasattr(plan, "as_dict") else plan, ensure_ascii=False, indent=2))
    return 0


def cmd_generate(args) -> int:
    cfg = load_config(args.config)
    setup_logging(cfg)
    from .generation import GenerationController

    if getattr(args, "target_chars", 0):
        cfg.generation.target_chars = int(args.target_chars)
    ctrl = GenerationController(cfg)
    try:
        result = ctrl.generate(args.brief, genre=args.genre, perspective=args.perspective,
                               max_rounds=args.rounds, offline=args.offline)
    except ModelAPIError as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        if exc.hint:
            print(f"提示：{exc.hint}", file=sys.stderr)
        return 3
    out = Path(args.out).expanduser() if args.out else None
    if out:
        out.write_text(result.text, encoding="utf-8")
        print(f"已写入 {out}")
    else:
        print(result.text)
    if args.report:
        print("\n== 生成后自检 ==")
        for item in result.analysis:
            print(json.dumps(item, ensure_ascii=False)[:800])
    return 0


def cmd_agent(args) -> int:
    from .config import merge_preset, resolve_gate, resolve_preset

    if getattr(args, "list_presets", False):
        print("%-8s %-6s %-6s %-6s %-10s %-8s %s" % ("预设", "story", "候选", "轮次", "目标字数", "闸门", "说明"))
        for p in AGENT_PRESETS.values():
            print("%-8s %-6s %-6d %-6d %-10s %-8s %s" % (p.name, p.story, p.candidates, p.max_rounds,
                                                    p.target_chars or "-", p.gate or "-", p.desc))
        return 0
    if not args.brief:
        print("缺少题材：inksoul agent \"题材…\"；或用 --list-presets 看预设", file=sys.stderr)
        return 2
    preset = resolve_preset(args.preset)
    if preset and preset.require_from and not args.from_path:
        print("预设 %s 需要 --from <前文路径>" % preset.name, file=sys.stderr)
        return 2
    picked = merge_preset(preset, story=args.story, candidates=args.candidates,
                          rounds=args.rounds, target_chars=args.target_chars,
                          deliver=args.deliver, gate=args.gate)
    story, candidates = picked["story"], picked["candidates"]
    rounds, target_chars, deliver = picked["max_rounds"], picked["target_chars"], picked["deliver"]
    if preset:
        print("预设：%s（%s）" % (preset.name, preset.desc))
    cfg = load_config(args.config)
    setup_logging(cfg)
    from .agent import WritingAgent

    gate_cmd = resolve_gate(picked["gate"])
    agent = WritingAgent(cfg, gate_cmd=gate_cmd, story=story,
                         tool_mode=args.tool_mode or ("ptc" if args.tools else ""),
                         tool_steps=args.tool_steps)
    try:
        result = agent.run(args.brief, genre=args.genre, perspective=args.perspective,
                           target_chars=target_chars, candidates=candidates,
                           max_rounds=rounds, out=args.out,
                           report_path=args.report, offline=args.offline,
                           from_path=args.from_path, refs=args.ref,
                           deliver_kind=deliver)
    except ModelAPIError as exc:
        print("生成失败：%s" % exc, file=sys.stderr)
        if exc.hint:
            print("提示：%s" % exc.hint, file=sys.stderr)
        return 3
    for note in result.notes:
        print(note)
    print()
    print("%-10s %6s %5s %5s %8s %8s %s" % ("阶段", "字数", "阻断", "问题", "MTLD", "MATTR", "闸门"))
    for rec in result.rounds:
        mtld = "%.1f" % rec.mtld if rec.mtld else "-"
        mattr = "%.3f" % rec.mattr if rec.mattr else "-"
        print("%-10s %6d %5d %5d %8s %8s %s" % (rec.label, rec.chars, rec.blocking,
                                                rec.issues, mtld, mattr, rec.gate_status))
    print()
    print("停止原因：%s" % result.stop_reason)
    print("定稿取自：%s" % result.rounds[result.chosen].label)
    if result.gate and result.gate.receipt:
        print(result.gate.receipt)
    if not args.out:
        print()
        print(result.text)
    return 0


def cmd_skills(args) -> int:
    from .story import EXCLUDED, StoryPack, discover

    if args.show:
        skill = discover().get(args.show)
        if not skill:
            print("未找到 skill：%s（已排除：%s）" % (args.show, "、".join(EXCLUDED)),
                  file=sys.stderr)
            return 2
        print("# %s %s" % (skill.name, skill.version or "(无版本)"))
        if skill.description:
            print(skill.description)
        print()
        print(skill.excerpt(args.chars) if args.chars else skill.body)
        return 0
    pack = StoryPack(mode=args.mode or "auto", target_chars=args.target_chars)
    for note in pack.notes:
        print(note)
    print()
    print("%-22s %-8s %-6s %s" % ("skill", "版本", "状态", "角色"))
    for row in pack.manifest():
        status = "选中" if row["selected"] else ("有" if row["present"] else "缺")
        print("%-22s %-8s %-6s %s" % (row["name"], row["version"] or "-", status, row["role"]))
    return 0


def cmd_baseline(args) -> int:
    from . import fingerprint as fp

    inputs = _read_inputs(args.target)
    baseline = fp.build_baseline([t for _, t in inputs], args.genre, source=args.target)
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(baseline.as_dict())
    payload["patterns"] = [{"signature": " ".join(p), "count": n} for p, n in baseline.patterns.most_common()]
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"基线已写入 {out}：{baseline.n_clauses} 小句 / {len(baseline.patterns)} 种骨架 / tau={baseline.tau:.2f}")
    return 0


def cmd_doctor(args) -> int:
    import platform
    import shutil

    print(f"InkSoul {__version__}｜Python {platform.python_version()}｜{platform.machine()}")
    cfg = load_config(args.config)
    print(f"配置目录：{cfg.home}")
    ok = True
    for mod in ("jieba",):
        print(f"  {mod}: {'✔' if shutil.which('python3') and _has(mod) else '✘ 缺失'}")
        ok = ok and _has(mod)
    try:
        from .nlp.backend import build_backend

        be = build_backend(cfg.analysis.backend)
        print(f"  NLP 后端：{be.name} {be.version}（依存：{be.has_dependency}）")
    except InkSoulError as exc:
        ok = False
        print(f"  NLP 后端：不可用（{exc}）")
    print(f"  模型：{cfg.model.model} @ {cfg.model.base_url}｜Key：{'已配置' if cfg.model.api_key else '未配置'}")
    print("结论：" + ("核心功能可用" if ok else "缺少核心依赖，见上面 ✘"))
    return 0 if ok else 2


def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="inksoul", description="InkSoul · 面向 AI Agent 的中文文学创作增强工具")
    p.add_argument("--version", action="version", version=f"inksoul {__version__}")
    p.add_argument("--config", help="配置文件路径（默认 ~/.inksoul/config.json）")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="分析文本的句法/文体特征")
    a.add_argument("target", help="文件、目录或 - （标准输入）")
    a.add_argument("--json", action="store_true", help="输出 JSON")
    a.add_argument("--no-review", action="store_true", help="跳过审阅意见")
    a.add_argument("--baseline", help="体裁基线 JSON 路径")
    a.set_defaults(func=cmd_analyze)

    g = sub.add_parser("generate", help="按创作要求生成并自检修订")
    g.add_argument("brief", help="创作要求")
    g.add_argument("--genre", default=None)
    g.add_argument("--perspective", default=None)
    g.add_argument("--rounds", type=int, default=2)
    g.add_argument("--out", default=None)
    g.add_argument("--target-chars", type=int, default=0, help="目标篇幅（字）")
    g.add_argument("--offline", action="store_true", help="不调模型，只校验配置")
    g.add_argument("--report", action="store_true", help="打印生成后自检")
    g.set_defaults(func=cmd_generate)

    ag = sub.add_parser("agent", help="Agent 闭环：生成→复核→改进→回滚（一键）")
    ag.add_argument("brief", nargs="?", default=None, help="题材/一句话要求；配合 --list-presets 可省略")
    ag.add_argument("--preset", default="", choices=[""] + list(AGENT_PRESETS),
                    help="预设档：draft/long/short/rewrite/publish/cover；显式参数优先")
    ag.add_argument("--list-presets", action="store_true", help="列出预设档后退出")
    ag.add_argument("--genre", default=None)
    ag.add_argument("--perspective", default=None)
    ag.add_argument("--rounds", type=int, default=None, help="改进轮数上限（默认取配置，缺省 3）")
    ag.add_argument("--candidates", type=int, default=None, help="候选稿数（默认取配置）")
    ag.add_argument("--target-chars", type=int, default=0)
    ag.add_argument("--out", default=None)
    ag.add_argument("--report", default=None, help="把每轮轨迹写成 JSON 报告")
    ag.add_argument("--gate", default="",
                    help="文风闸门：deslop/full/essay/zhuque/off，或直接写命令（{file} 换成正文路径）")
    ag.add_argument("--tools", action="store_true",
                    help="开启工具面（等同 --tool-mode ptc）")
    ag.add_argument("--tool-mode", default="", choices=["", "standard", "ptc"],
                    help="工具模式：ptc=程序化工具调用（默认，模型写程序一次查完）；standard=逐个 function calling")
    ag.add_argument("--tool-steps", type=int, default=0,
                    help="工具轮数上限（ptc 默认 2 段程序，standard 默认 3 轮）")
    ag.add_argument("--story", default="", choices=["", "auto", "long", "short", "off"],
                    help="注入本地 story 写作规范：auto/long/short/off（默认取配置）")
    ag.add_argument("--from", dest="from_path", default=None,
                    help="续写：已有前文路径（story-import 口径，取尾部 3000 字进提示）")
    ag.add_argument("--ref", action="append", default=[],
                    help="参考资料（拆解报告等），可重复；每个文件取前 3000 字")
    ag.add_argument("--deliver", default="", choices=["", "publish", "cover"],
                    help="额外产出：publish 发布资料 / cover 封面提示词")
    ag.add_argument("--offline", action="store_true", help="不调模型，只校验配置")
    ag.set_defaults(func=cmd_agent)

    pl = sub.add_parser("plan", help="只输出文体规划")
    pl.add_argument("brief")
    pl.add_argument("--genre", default=None)
    pl.add_argument("--perspective", default=None)
    pl.add_argument("--target-chars", type=int, default=0)
    pl.set_defaults(func=cmd_plan)

    sk = sub.add_parser("skills", help="本地 story 写作 skill：清点与摘录")
    sk.add_argument("--show", default=None, help="查看某个 skill 的摘录")
    sk.add_argument("--chars", type=int, default=2000, help="摘录上限（配合 --show）")
    sk.add_argument("--mode", default="auto", choices=["auto", "long", "short", "off"])
    sk.add_argument("--target-chars", type=int, default=0)
    sk.set_defaults(func=cmd_skills)

    b = sub.add_parser("baseline", help="体裁基线")
    bsub = b.add_subparsers(dest="bcmd", required=True)
    bb = bsub.add_parser("build", help="从语料构建基线")
    bb.add_argument("target")
    bb.add_argument("--genre", required=True)
    bb.add_argument("--out", default=str(Path.home() / ".inksoul" / "baseline.json"))
    bb.set_defaults(func=cmd_baseline)

    c = sub.add_parser("corpus", help="跨作品同质度（两两骨架相似度）")
    c.add_argument("target", help="目录（比较其中所有 .txt）或多个文件")
    c.add_argument("--json", action="store_true", help="输出 JSON")
    c.set_defaults(func=cmd_corpus)

    d = sub.add_parser("doctor", help="环境自检")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except InkSoulError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        if exc.hint:
            print(f"提示：{exc.hint}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"未预期错误：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())