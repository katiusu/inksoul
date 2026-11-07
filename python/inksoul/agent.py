"""Agent 模式：生成 → 复核 → 改进 的闭环编排。

设计约束（docs/agent_mode.md）
------------------------------
- 不做综合打分：每轮只记「阻断级问题数 / 问题总数」，取舍靠逐项比较，
  否则整条流水线会退化成指标优化游戏。
- 必带回滚：每轮存档，最终取阻断数最少的版本，不取最后一版——改坏要能退回去。
- 外部门禁是硬条件：配置了 gate_cmd 时，闸门不过就不算定稿，回执原样写进报告。
- 改进分两条路：内部复核问题走 generation.revise 的窗口式替换；
  外部门禁未过时走 generation.restyle 整篇重写（只改文风，情节不变）。
"""
from __future__ import annotations

import json
import time
import re
import shlex
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .story import StoryPack
from .config import InkSoulConfig
from .errors import ConfigError, InkSoulError
from .generation import (CreationBrief, Draft, StylePlan, build_plan, generate, restyle,
                         revise)
from .llm import LLMClient
from .toolbox import ToolBox, run_tool_loop
from .ptc import PTC_SYSTEM, run_ptc_loop

#: 闸门命令里代表正文路径的占位符
GATE_PLACEHOLDER = "{file}"
#: 闸门默认超时（秒）：朱雀那类检测要几十秒
GATE_TIMEOUT = 300.0
#: 默认改进轮数（超过 3 轮基本是在拧指标而不是在改文）
DEFAULT_ROUNDS = 3
#: 修订阶段的总时间预算（秒）：多轮收敛不能无限烧模型
REVISION_BUDGET_SEC = 240.0
STATUS_SKIPPED = "skipped"
STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"

#: 侦察阶段的系统提示：只做资料准备，不写正文
RECON_SYSTEM = (
    "你是写作前的资料侦察员。用工具核实需要的事实与设定，然后给出一段不超过 400 字的侦察笔记："
    "人物/地点/前情要点、值得延续的细节、需要避开的重复。不要写正文，不要编造工具没返回的内容。")


@dataclass
class GateResult:
    """外部闸门（如 /root/deslop/postwrite.sh）的执行结果。"""

    status: str = STATUS_SKIPPED
    rc: int = 0
    verdict: str = ""
    receipt: str = ""
    output: str = ""
    findings: list[str] = field(default_factory=list)  # 闸门表里 FAIL 的命中行

    @property
    def blocked(self) -> bool:
        """闸门是否构成阻断：FAIL 与执行错误都算。"""
        return self.status in (STATUS_FAIL, STATUS_ERROR)

    def as_dict(self) -> dict:
        return asdict(self)


def _run_builtin_gate(name: str, path: Path) -> GateResult:
    """跑插件自带闸门（markers）：纯 Python，不调外部脚本。"""
    if name != "markers":
        return GateResult(status=STATUS_ERROR, rc=-2, output="未知的内置闸门：" + name)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return GateResult(status=STATUS_ERROR, rc=-1, output="读不到文件：" + str(exc))
    try:
        from .markers import gate_text

        passed, lines = gate_text(text, filename=path.name)
    except Exception as exc:  # noqa: BLE001 - 闸门内部错误按失败报
        return GateResult(status=STATUS_ERROR, rc=-1,
                          output="内置闸门出错：%s: %s" % (type(exc).__name__, exc))
    body = chr(10).join(lines)
    verdict = next((ln.split("（", 1)[0].strip() for ln in lines
                    if ln.startswith("VERDICT:")),
                   "VERDICT: " + ("PASS" if passed else "FAIL"))
    told_fail = verdict.endswith("FAIL")
    receipt = next((ln for ln in lines if ln.startswith("RECEIPT")), "")
    findings = [ln.strip() for ln in lines if "VHIGH" in ln or "HIGH" in ln]
    return GateResult(status=STATUS_FAIL if told_fail else STATUS_PASS,
                      rc=1 if told_fail else 0, verdict=verdict, receipt=receipt,
                      output=body[-4000:], findings=findings[:20])


def run_gate(cmd: str, path: Path, *, timeout: float = GATE_TIMEOUT,
             runner=None) -> GateResult:
    """执行外部门禁命令，解析 VERDICT 与 RECEIPT 行。

    runner 仅用于测试：runner(line, timeout) -> (rc, output)。
    """
    if not cmd:
        return GateResult()
    if cmd.strip().startswith("__inksoul__:"):
        return _run_builtin_gate(cmd.strip().split(":", 1)[1], path)
    if GATE_PLACEHOLDER in cmd:
        line = cmd.replace(GATE_PLACEHOLDER, shlex.quote(str(path)))
    else:
        line = cmd + " " + shlex.quote(str(path))
    try:
        if runner is not None:
            rc, output = runner(line, timeout)
        else:
            proc = subprocess.run(line, shell=True, capture_output=True,
                                  text=True, timeout=timeout)
            rc, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return GateResult(status=STATUS_ERROR, rc=-1, output="闸门超时（>{0:.0f}s）".format(timeout))
    except OSError as exc:
        return GateResult(status=STATUS_ERROR, rc=-1, output="闸门无法执行：" + str(exc))

    text = output or ""
    verdict = ""
    receipt = ""
    findings: list[str] = []
    for raw in text.splitlines():
        clean = re.sub(r"\x1b\[[0-9;]*m", "", raw).strip()
        if not verdict and "VERDICT" in clean:
            verdict = clean
        if not receipt and clean.startswith("RECEIPT"):
            receipt = clean
        if clean and not re.match(r"[-=]{3,}$", clean) \
                and not clean.startswith(("VERDICT", "RECEIPT")) \
                and re.search(r"\bFAIL\b", clean):
            findings.append(clean)
    m = re.search(r"VERDICT:\s*([A-Za-z]+)", text)
    word = m.group(1).upper() if m else ""
    if word == "FAIL":
        status = STATUS_FAIL
    elif word == "PASS":
        status = STATUS_PASS
    elif rc == 0:
        status = STATUS_PASS
    else:
        status = STATUS_FAIL
    return GateResult(status=status, rc=rc, verdict=verdict or word,
                      receipt=receipt, output=text[-4000:], findings=findings[:20])


@dataclass
class RoundRecord:
    """一轮的观测值；顺序即时间顺序，便于人工看轨迹。"""

    label: str
    round: int
    chars: int
    blocking: int
    issues: int
    mtld: float | None = None
    mattr: float | None = None
    gate_status: str = STATUS_SKIPPED
    applied: int = 0
    note: str = ""
    style_distance: float | None = None

    @property
    def blocked(self) -> bool:
        return self.gate_status in (STATUS_FAIL, STATUS_ERROR)

    def rank(self) -> tuple:
        """越小越好：闸门 → 阻断级问题 → 问题总数 → 到人类池的距离。"""
        dist = round(self.style_distance, 1) if self.style_distance is not None else 9.9
        return (1 if self.blocked else 0, self.blocking, self.issues, dist)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentResult:
    """闭环跑完的结果：定稿 + 每轮轨迹 + 定稿那份的分析。"""

    text: str
    plan: StylePlan
    rounds: list[RoundRecord] = field(default_factory=list)
    chosen: int = 0
    stop_reason: str = ""
    candidates: int = 0
    gate: GateResult | None = None
    analysis: dict | None = None
    skills: list[dict] = field(default_factory=list)
    deliverables: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    tool_steps: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "chosen_round": self.chosen,
            "stop_reason": self.stop_reason,
            "candidates": self.candidates,
            "plan": self.plan.as_dict() if hasattr(self.plan, "as_dict") else self.plan,
            "rounds": [r.as_dict() for r in self.rounds],
            "gate": self.gate.as_dict() if self.gate else None,
            "analysis": self.analysis,
            "skills": list(self.skills),
            "deliverables": dict(self.deliverables),
            "notes": list(self.notes),
            "tool_steps": list(self.tool_steps),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=indent)


DELIVER_SKILLS = {"publish": "story-publish", "cover": "story-cover"}


def build_deliverable(kind: str, pack: StoryPack, brief: CreationBrief, client,
                      *, max_chars: int = 1800) -> str:
    """按 story-publish / story-cover 的口径，额外生成发布资料或封面提示词。"""
    name = DELIVER_SKILLS.get(kind)
    if not name:
        raise ConfigError("未知的交付物类型：%s" % kind, hint="只支持 publish / cover")
    skill = pack.skills.get(name)
    if not skill:
        raise ConfigError("本地缺少 %s skill" % name, hint="跑 inksoul skills 确认安装")
    prompt = "%s\n\n【题材与要求】\n%s" % (skill.excerpt(max_chars), brief.prompt_block())
    resp = client.chat(
        [{"role": "system", "content": "你按给定的写作说明产出可直接使用的交付物，只输出正文。"},
         {"role": "user", "content": prompt}], temperature=0.4, max_tokens=800)
    return resp.text.strip()


class WritingAgent:
    """一条命令跑完：多候选择优 → 复核 → 局部修订 → 回滚 → 闸门。"""

    def __init__(self, config: InkSoulConfig, *, client: LLMClient | None = None,
                 gate_cmd: str = "", gate_timeout: float | None = None, runner=None,
                 story: str = "", tools: bool = False, tool_steps: int = 0,
                 tool_mode: str = "", gate_final_only: bool = True):
        self.config = config
        if client is None and config.model.api_key:
            client = LLMClient(config.model)
        self.client = client
        agent_cfg = getattr(config, "agent", None)
        self.gate_cmd = gate_cmd or (agent_cfg.gate_cmd if agent_cfg else "")
        default_timeout = agent_cfg.gate_timeout if agent_cfg else GATE_TIMEOUT
        self.gate_timeout = float(gate_timeout or default_timeout or GATE_TIMEOUT)
        self.runner = runner
        # 闸门是 40s 级外部进程：默认只在定稿后跑，不逐候选、不逐轮跑
        self.gate_final_only = bool(gate_final_only)
        self.story_mode = story or getattr(agent_cfg, "story", "auto")
        # 工具面：默认关闭（零额外请求）；standard=function calling，ptc=程序化工具调用
        mode = str(tool_mode or "").strip().lower()
        if mode not in ("", "standard", "ptc"):
            raise ConfigError("未知的工具模式：%s" % tool_mode, hint="可选 standard / ptc")
        if not mode and tools:
            mode = "ptc"
        self.tool_mode = mode
        self.toolbox = None
        self.tool_steps = max(0, int(tool_steps or (3 if mode == "standard" else 2 if mode else 0)))
        if self.tool_steps:
            self.toolbox = ToolBox(config, gate_cmd=self.gate_cmd,
                                   gate_timeout=self.gate_timeout, runner=self.runner)
        from .analyzer import Analyzer

        self.analyzer = Analyzer(config)

    # ---------------------------------------------------------------- 观测
    def _grade(self, text: str, *, label: str, rnd: int = 0, applied: int = 0,
               note: str = "", with_gate: bool = True) -> tuple[RoundRecord, object, GateResult]:
        report = self.analyzer.analyze(text, with_review=True)
        review = report.review
        blocking = len(review.blocking) if hasattr(review, "blocking") else 0
        issues = len(getattr(review, "issues", []) or [])
        lex = getattr(report.diversity, "lexical", None) or {}
        style_dist = None
        try:
            from . import style_pool as _sp
            _pool = _sp.load_pool()
            if _pool:
                style_dist = _sp.distance(_sp.metrics_from_dict(report.as_dict()), _pool)
        except Exception:
            style_dist = None
        gate = GateResult()
        if self.gate_cmd and with_gate:
            gate = self._gate_text(text)
        if gate.status == STATUS_PASS and blocking:
            note = (note + "；" if note else "") + "闸门 PASS 仅覆盖标记族，另有 %d 条阻断" % blocking
        rec = RoundRecord(label=label, round=rnd, chars=len(text), blocking=blocking,
                          issues=issues, mtld=lex.get("mtld"), mattr=lex.get("mattr"),
                          gate_status=gate.status, applied=applied, note=note, style_distance=style_dist)
        return rec, report, gate

    def _gate_text(self, text: str) -> GateResult:
        """对一段正文跑外部门禁（闸门本身约 40s，跑一次算一次钱）。"""
        tmp = _write_tmp(text)
        try:
            return run_gate(self.gate_cmd, tmp, timeout=self.gate_timeout,
                            runner=self.runner)
        finally:
            tmp.unlink(missing_ok=True)

    def _finalize_gate(self, text: str, plan, story_review: str,
                       max_passes: int = 2):
        """定稿后跑闸门：未过就按命中条目整篇重写，最多再跑一次。"""
        gate = self._gate_text(text)
        passes = 1
        while passes < max_passes and gate.blocked and gate.findings:
            rev = restyle(text, gate.findings, self.client, plan,
                          cfg=self.config, extra_system=story_review)
            if not rev.applied:
                break
            text = rev.text
            gate = self._gate_text(text)
            passes += 1
        return text, gate, passes

    # ---------------------------------------------------------------- 主流程
    def run(self, theme: str, *, genre: str = "小说", perspective: str = "",
            target_chars: int = 0, candidates: int | None = None,
            max_rounds: int | None = None, out: str | Path | None = None,
            report_path: str | Path | None = None, offline: bool = False,
            from_path: str | Path | None = None, refs: list[str] | None = None,
            deliver_kind: str = "") -> AgentResult:
        agent_cfg = getattr(self.config, "agent", None)
        if target_chars:
            self.config.generation.target_chars = int(target_chars)
        brief = CreationBrief(theme=theme, genre=genre or "小说", perspective=perspective,
                              target_chars=self.config.generation.target_chars)
        plan = build_plan(brief, self.config, client=self.client, use_llm=not offline)
        if offline or self.client is None or not self.client.available:
            raise ConfigError(
                "Agent 模式需要可用的模型 API",
                hint="先 `inksoul config --init` 填 api_key；只想看文体规划用 `inksoul plan`",
            )
        n = max(1, int(candidates or (agent_cfg.candidates if agent_cfg else plan.candidates)))
        limit = int(max_rounds if max_rounds is not None
                    else (agent_cfg.max_rounds if agent_cfg else DEFAULT_ROUNDS))

        extra_bits: list[str] = []
        if from_path:
            try:
                prev = Path(from_path).expanduser().read_text(encoding="utf-8")
                extra_bits.append("【已有前文，续写必须与前文衔接（最近 3000 字）】\n" + prev[-3000:])
            except OSError as exc:
                raise ConfigError("读不到续写前文：%s" % exc, hint="检查 --from 路径") from exc
        for ref in refs or []:
            p = Path(ref).expanduser()
            if not p.is_file():
                extra_bits.append("【参考资料缺失：%s】" % p.name)
                continue
            try:
                extra_bits.append("【参考资料 %s】\n%s" % (p.name, p.read_text(encoding="utf-8")[:3000]))
            except OSError:
                extra_bits.append("【参考资料读取失败：%s】" % p.name)
        extra_user = "\n\n".join(extra_bits)

        pack = StoryPack(mode=self.story_mode, target_chars=self.config.generation.target_chars)
        story_prompt = pack.prompt_block()
        story_review = pack.review_block()

        # 0) 侦察：开启工具面时先让模型查资料（PTC 程序化调用 / 标准 function calling）
        tool_steps: list[dict] = []
        if self.toolbox is not None:
            recon_msgs = [
                {"role": "system", "content": PTC_SYSTEM if self.tool_mode == "ptc" else RECON_SYSTEM},
                {"role": "user", "content": "【题材与要求】" + chr(10) + brief.prompt_block()},
            ]
            if self.tool_mode == "ptc":
                recon = run_ptc_loop(self.client, recon_msgs, self.toolbox,
                                     max_rounds=self.tool_steps)
                tool_steps = recon.programs
                tail = recon.text or ("程序已执行 %d 段" % len(recon.programs))
            else:
                recon = run_tool_loop(self.client, recon_msgs, self.toolbox,
                                      max_steps=self.tool_steps)
                tool_steps = [s.as_dict() for s in recon.steps]
                tail = recon.text
            if tail:
                note = "【侦察笔记（工具调用所得，供写作参考）】" + chr(10) + tail[:1500]
                extra_user = (extra_user + chr(10) + chr(10) + note) if extra_user else note

        # 1) 多候选：按 rank 择优（闸门 → 阻断 → 问题总数）
        pool: list[tuple[RoundRecord, str, object, GateResult]] = []
        for i in range(n):
            draft: Draft = generate(brief, plan, self.client, candidate_id=i,
                                    extra_system=story_prompt, extra_user=extra_user)
            rec, rep, gate = self._grade(draft.text, label="候选#%d" % i,
                                         with_gate=not self.gate_final_only)
            pool.append((rec, draft.text, rep, gate))
            if n > 1 and rec.rank()[:3] == (0, 0, 0):
                break  # 第一个全干净的候选就不再花 token
        best_rec, best_text, best_report, best_gate = min(pool, key=lambda p: p[0].rank())
        history: list[RoundRecord] = [r for r, _, _, _ in pool]

        # 2) 复核 → 改进 → 回滚（多轮收敛：直到闸门 PASS / 无问题 / 预算或轮数用完）
        stop = "达到轮次上限（%d）" % limit
        started = time.monotonic()
        stall = 0
        # 内置闸门是纯 Python，便宜，可以每轮都跑；外部闸门 40s 级，仍留到定稿
        cheap_gate = self.gate_cmd.strip().startswith("__inksoul__:")
        for rnd in range(1, limit + 1):
            passed = (best_gate.status.upper() == STATUS_PASS.upper()
                      and not best_report.review.issues)
            if passed:
                stop = "复核通过：无问题且闸门 PASS"
                break
            if not best_report.review.issues and not best_gate.blocked:
                stop = "复核通过：无阻断级问题"
                break
            if REVISION_BUDGET_SEC - (time.monotonic() - started) <= 0:
                stop = "修订预算用完（%.0fs）" % REVISION_BUDGET_SEC
                break
            blocking = [i for i in best_report.review.issues if i.severity >= 0.6]
            if best_gate.blocked and best_gate.findings:
                rev = restyle(best_text, best_gate.findings, self.client, plan,
                              cfg=self.config, extra_system=story_review)
            elif blocking:
                rev = revise(best_text, best_report.review, self.client, plan,
                             cfg=self.config, max_rounds=1, extra_system=story_review,
                             min_severity=0.6, max_items=8)
            elif any(i.text for i in best_report.review.issues):
                # 只剩低严重度问题（0.3~0.6）：也走逐句替换——比整篇重写便宜且能定位
                rev = revise(best_text, best_report.review, self.client, plan,
                             cfg=self.config, max_rounds=1, extra_system=story_review,
                             min_severity=0.3, max_items=8)
            else:
                findings = ["%s：%s" % (i.kind, i.suggestion)
                            for i in best_report.review.issues[:6] if i.suggestion]
                if not findings:
                    stop = "复核通过：无阻断级问题"
                    break
                rev = restyle(best_text, findings, self.client, plan,
                              cfg=self.config, extra_system=story_review)
            if not rev.applied:
                note = rev.notes[0] if rev.notes else "无改写产出"
                stop = ("有 %d 条阻断级问题但修订未落地（%s）" % (len(blocking), note)
                        if blocking else "无阻断级问题，风格重写未产出改动")
                break
            rec, rep, gate = self._grade(rev.text, label="修订#%d" % rnd, rnd=rnd,
                                         applied=rev.applied,
                                         note=(rev.notes[0] if rev.notes else ""),
                                         with_gate=not self.gate_final_only or cheap_gate)
            history.append(rec)
            if rec.rank() < best_rec.rank():
                best_rec, best_text, best_report, best_gate = rec, rev.text, rep, gate
                stall = 0
                if (gate.status.upper() == STATUS_PASS.upper()
                        and not rep.review.issues):
                    stop = "修订 %d 轮后闸门 PASS" % rnd
                    break
            else:
                stall += 1
                if stall >= 2:
                    stop = "连续 %d 轮无改善，已回滚到问题最少的那一版" % stall
                    break

        # 3) 定稿后过闸门：只在最终稿上跑（1 次，未过再补 1 次）
        gate_passes = 0
        source_label = best_rec.label
        if self.gate_cmd and self.gate_final_only:
            best_text, best_gate, gate_passes = self._finalize_gate(
                best_text, plan, story_review)
            # 定稿可能被闸门后置重写改过，重跑一次分析，让报告里的数字对应最终正文
            rec2, rep2, _unused = self._grade(best_text, label="定稿",
                                              rnd=best_rec.round, with_gate=False)
            rec2.gate_status = best_gate.status
            rec2.note = "定稿后重跑分析（%d 次闸门）" % gate_passes
            try:
                history[history.index(best_rec)] = rec2  # 原地替换，保持轨迹条数与选中下标不变
            except ValueError:
                history.append(rec2)
            best_rec, best_report = rec2, rep2
            if not best_gate.blocked and not rep2.review.blocking:
                stop = "定稿过闸门 PASS（%d 次）" % gate_passes
            elif best_gate.blocked:
                stop = "定稿仍未过闸门：%s" % (best_gate.verdict or best_gate.status)

        notes = ["候选 %d 个，选中「%s」" % (len(pool), source_label),
                 "轨迹 %d 条，定稿 rank=%s（闸门,阻断,问题数,池距）" % (len(history), best_rec.rank())]
        notes.extend(pack.notes)
        if from_path:
            notes.append("已按 --from 续写模式生成（前文尾部 3000 字进提示）")
        if refs:
            notes.append("参考文件 %d 个" % len(refs))
        if tool_steps:
            if self.tool_mode == "ptc":
                notes.append("侦察阶段执行程序 %d 段（PTC 程序化调用）" % len(tool_steps))
            else:
                notes.append("侦察阶段调用工具 %d 次（%s）" % (
                    len(tool_steps),
                    "、".join(dict.fromkeys(str(s.get("tool") or "?") for s in tool_steps))))
        if gate_passes:
            notes.append("定稿后过闸门 %d 次（未逐候选跑，省时）" % gate_passes)
        if self.gate_cmd and best_gate.status != STATUS_PASS:
            notes.append("注意：外部门禁未 PASS，定稿仍需人工处理")
        chosen = next(i for i, r in enumerate(history) if r is best_rec)
        result = AgentResult(text=best_text, plan=plan, rounds=history,
                             chosen=chosen, stop_reason=stop,
                             candidates=len(pool),
                             gate=best_gate if self.gate_cmd else None,
                             analysis=best_report.as_dict(), skills=pack.manifest(),
                             notes=notes, tool_steps=tool_steps)
        if deliver_kind:
            try:
                text_out = build_deliverable(deliver_kind, pack, brief, self.client)
                result.deliverables[deliver_kind] = text_out
                result.notes.append("已生成 %s 资料（%d 字）" % (deliver_kind, len(text_out)))
            except InkSoulError as exc:
                result.notes.append("生成 %s 资料失败：%s" % (deliver_kind, exc))
        if out:
            path = Path(out).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(best_text, encoding="utf-8")
            result.notes.append("正文已写入 %s" % path)
        if report_path:
            rp = Path(report_path).expanduser()
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(result.to_json(), encoding="utf-8")
            result.notes.append("报告已写入 %s" % rp)
        return result


def _write_tmp(text: str) -> Path:
    fh = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    with fh:
        fh.write(text)
    return Path(fh.name)