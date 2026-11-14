"""标准模式的工具面（tool use / function calling）。

设计约束
--------
- **只给五个工具**：读前文 `read_prev`、查设定库 `lookup_bible`、量文体 `measure`、
  跑闸门 `run_gate`、载入写作规范 `load_skill`。工具面越窄，模型在参数上胡思乱想的
  空间越小，每次请求的 schema token 也越省。
- **只读为主**：`read_prev` / `lookup_bible` 限定在允许根目录（默认当前目录与
  InkSoul 主目录）内，越界直接报错，不做「路径猜谜」。
- **结果有上限**：每个工具返回 JSON 字符串，正文类结果截断，避免把整本书回灌进上下文。
- 闸门工具复用 :func:`inksoul.agent.run_gate`（局部导入，避免循环依赖）。
"""
from __future__ import annotations

import json
import os
import re
import statistics
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .config import InkSoulConfig

#: 句子切分（中文句末标点 + 换行）
_SENT_SPLIT = re.compile(r"[。！？!?…]+|\n+")
#: 单次读取上限（字符），防止一次把整本书塞进上下文
_READ_LIMIT = 200_000
#: 设定库文件后缀
_BIBLE_SUFFIX = (".md", ".txt")
#: skill 名白名单形状：目录名只允许这些字符，防路径穿越
_SKILL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
#: 单次载入规范的上限（字符）：一篇 SKILL.md 约 6–11k，够整篇读完
_SKILL_LIMIT = 14000


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def skill_roots(config=None) -> list[Path]:
    """本地 skill 根目录：环境级在左，项目级在右，左侧优先。"""
    return [Path(p).expanduser() for p in (
        "/root/.agents/skills",
        Path.home() / ".agents" / "skills",
        Path(getattr(config, "home", ".")).expanduser() / "skills",
        Path.cwd() / "skills",
    )]


def find_skill(name: str, config=None) -> Path | None:
    """按名字找 <root>/<name>/SKILL.md；名字走白名单，越界直接当没找到。"""
    name = str(name or "").strip()
    if not _SKILL_NAME.match(name):
        return None
    for root in skill_roots(config):
        target = root / name / "SKILL.md"
        if target.is_file():
            return target
    return None


def _pick_section(text: str, keyword: str) -> str:
    """取第一个标题含 keyword 的整节（到下一个同级或更高级标题为止）。"""
    lines = text.splitlines()
    start = level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,4}) (.+)$", line)
        if m and keyword in m.group(2):
            start, level = i, len(m.group(1))
            break
    if not start:
        return ""
    out = [lines[start]]
    for line in lines[start + 1:]:
        m = re.match(r"^(#{1,4}) ", line)
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out).strip()


@dataclass(frozen=True)
class ToolSpec:
    """一个工具的声明：名字 + 说明 + JSON Schema 参数。"""

    name: str
    description: str
    parameters: dict

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description,
                             "parameters": self.parameters}}


def default_specs() -> list[ToolSpec]:
    return [
        ToolSpec("read_prev",
                 "读取已写好的前文/参考稿，返回末尾一段（默认 3000 字）。用于续写衔接。",
                 {"type": "object",
                  "properties": {"path": {"type": "string", "description": "文件路径"},
                                 "limit": {"type": "integer", "description": "返回末尾多少字，默认 3000"}},
                  "required": ["path"]}),
        ToolSpec("lookup_bible",
                 "在设定库（bible/、设定/、settings/、notes/ 或 bible.md）里按关键词找设定条目。",
                 {"type": "object",
                  "properties": {"query": {"type": "string", "description": "关键词，空格分隔多个"},
                                 "top": {"type": "integer", "description": "最多返回几条，默认 3"}},
                  "required": ["query"]}),
        ToolSpec("measure",
                 "量一段文字的文体指标：字数、句数、平均句长、句长变异系数、逗号密度、短句占比。",
                 {"type": "object",
                  "properties": {"text": {"type": "string", "description": "要量的正文"}},
                  "required": ["text"]}),
        ToolSpec("run_gate",
                 "把一段正文交给文风闸门检查，返回 VERDICT 与 FAIL 命中行。",
                 {"type": "object",
                  "properties": {"text": {"type": "string", "description": "要检查的正文"},
                                 "gate": {"type": "string", "description": "闸门别名：deslop/full/essay/zhuque/off"}},
                  "required": ["text"]}),
        ToolSpec("load_skill",
                 "按名字载入本地写作/审查 skill 的完整规范正文（story-long-write / "
                 "story-short-write / story-review / prose-deai 等）。动笔前先载入投要求的那几份。",
                 {"type": "object",
                  "properties": {"name": {"type": "string",
                                          "description": "skill 名，如 prose-deai、story-long-write"},
                                 "section": {"type": "string",
                                             "description": "可选：只取某个二级标题的整节（写标题里的关键词即可）"},
                                 "limit": {"type": "integer",
                                           "description": "返回字符上限，默认 14000"}},
                  "required": ["name"]}),
    ]


class ToolBox:
    """工具执行器：把工具名 + 参数变成 JSON 字符串结果。"""

    def __init__(self, config: InkSoulConfig, *, gate_cmd: str = "",
                 gate_timeout: float = 120.0, runner=None, roots=None):
        self.config = config
        self.gate_cmd = gate_cmd
        self.gate_timeout = float(gate_timeout)
        self.runner = runner
        base = [Path.cwd(), Path(getattr(config, "home", ".")).expanduser()]
        self.roots = [Path(p).expanduser().resolve() for p in (roots or base)]
        self.skill_roots = skill_roots(config)
        self._specs = default_specs()
        # 真读到的规范名：agent 的技能前置闸门只认这个集合，不认调用记录里的字符串。
        self.loaded: set[str] = set()

    # ---------------------------------------------------------------- 声明
    def schema(self) -> list[dict]:
        return [s.schema() for s in self._specs]

    @property
    def names(self) -> list[str]:
        return [s.name for s in self._specs]

    # ---------------------------------------------------------------- 执行
    def dispatch(self, name: str, args: dict | None = None) -> str:
        """执行工具，永远返回 JSON 字符串；异常收敛成 `{"error": ...}`。"""
        try:
            if not isinstance(args, dict):
                return _dumps({"error": "参数必须是 JSON 对象，收到 %s" % type(args).__name__})
            args = dict(args)
            if name == "read_prev":
                return _dumps(self._read_prev(**args))
            if name == "lookup_bible":
                return _dumps(self._lookup_bible(**args))
            if name == "measure":
                return _dumps(self._measure(**args))
            if name == "run_gate":
                return _dumps(self._run_gate(**args))
            if name == "load_skill":
                return _dumps(self._load_skill(**args))
            return _dumps({"error": "未知工具：%s（可用：%s）" % (name, "、".join(self.names))})
        except TypeError as exc:
            return _dumps({"error": "参数不对：%s" % exc})
        except Exception as exc:  # 工具内部任何失败都不该炸掉整条流水线
            return _dumps({"error": "%s: %s" % (type(exc).__name__, exc)})

    # ---------------------------------------------------------------- 工具
    def _within(self, path: Path) -> bool:
        resolved = path.resolve()
        return any(resolved == root or root in resolved.parents for root in self.roots)

    def _read_prev(self, path: str = "", limit: int = 3000) -> dict:
        if not str(path or "").strip():
            return {"error": "path 为空"}
        target = Path(path).expanduser()
        if not self._within(target):
            return {"error": "路径不在允许范围内：%s" % path}
        if not target.is_file():
            return {"error": "文件不存在：%s" % path}
        text = target.read_text(encoding="utf-8", errors="replace")[:_READ_LIMIT]
        keep = max(200, min(int(limit or 3000), 20_000))
        return {"path": str(target.resolve()), "chars": len(text), "text": text[-keep:]}

    def _load_skill(self, name: str = "", section: str = "", limit: int = 0) -> dict:
        """按名字载入本地 SKILL.md 正文；只认 skill 根目录下的 <name>/SKILL.md。"""
        name = str(name or "").strip()
        if not name:
            return {"error": "name 为空", "available": self._skill_names()}
        if not _SKILL_NAME.match(name):
            return {"error": "skill 名不合法：%s" % name, "available": self._skill_names()}
        for root in self.skill_roots:
            target = root / name / "SKILL.md"
            if target.is_file():
                break
        else:
            return {"error": "没找到 skill：%s" % name, "available": self._skill_names()}
        text = target.read_text(encoding="utf-8", errors="replace")
        version = ""
        meta = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if meta:
            for line in meta.group(1).splitlines():
                if line.strip().startswith("version:"):
                    version = line.split(":", 1)[1].strip().strip('"')
            text = text[meta.end():]
        text = text.strip()
        self.loaded.add(name)      # 只有真读到正文才记账；失败分支在前面已 return
        if str(section or "").strip():
            text = _pick_section(text, str(section).strip()) or text
        cap = min(max(1, int(limit or _SKILL_LIMIT)), _SKILL_LIMIT)
        cut = len(text) > cap
        return {"name": name, "version": version, "path": str(target.resolve()),
                "chars": len(text), "truncated": cut, "text": text[:cap]}

    def _skill_names(self) -> list[str]:
        names: list[str] = []
        for root in self.skill_roots:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if (child / "SKILL.md").is_file() and child.name not in names:
                    names.append(child.name)
        return names

    def _bible_files(self) -> list[Path]:
        files: list[Path] = []
        for root in self.roots:
            for sub in ("bible", "设定", "settings", "notes"):
                d = root / sub
                if d.is_dir():
                    files.extend(sorted(p for p in d.rglob("*")
                                        if p.is_file() and p.suffix in _BIBLE_SUFFIX)[:40])
            f = root / "bible.md"
            if f.is_file():
                files.append(f)
        seen: set[str] = set()
        out: list[Path] = []
        for p in files:
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                out.append(p)
        return out[:80]

    def _lookup_bible(self, query: str = "", top: int = 3) -> dict:
        tokens = [t for t in re.split(r"\s+", str(query or "").strip()) if t]
        if not tokens:
            return {"error": "query 为空"}
        cap = max(1, min(int(top or 3), 10))
        hits: list[dict] = []
        for f in self._bible_files():
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for no, line in enumerate(lines, 1):
                s = line.strip()
                if s and any(t in s for t in tokens):
                    hits.append({"source": "%s:%d" % (f.name, no), "text": s[:200]})
                    if len(hits) >= cap:
                        return {"query": tokens, "hits": hits}
        return {"query": tokens, "hits": hits}

    def _measure(self, text: str = "") -> dict:
        body = str(text or "")
        if not body.strip():
            return {"error": "text 为空"}
        sents = [s.strip() for s in _SENT_SPLIT.split(body) if len(s.strip()) >= 2]
        lengths = [len(s) for s in sents]
        avg = statistics.fmean(lengths) if lengths else 0.0
        cv = (statistics.pstdev(lengths) / avg) if len(lengths) > 1 and avg else 0.0
        commas = body.count("，") + body.count(",")
        short = sum(1 for n in lengths if n <= 10)
        return {"chars": len(body), "sentences": len(lengths),
                "avg_sentence": round(avg, 1), "cv": round(cv, 3),
                "comma_per_100": round(100.0 * commas / max(1, len(body)), 2),
                "short_ratio": round(short / len(lengths), 3) if lengths else 0.0}

    def _run_gate(self, text: str = "", gate: str = "") -> dict:
        from .agent import run_gate
        from .config import resolve_gate
        body = str(text or "")
        if not body.strip():
            return {"error": "text 为空"}
        cmd = resolve_gate(gate) or self.gate_cmd
        if not cmd:
            return {"status": "skipped", "note": "未配置闸门"}
        fd, name = tempfile.mkstemp(prefix="inksoul_tool_", suffix=".txt")
        os.close(fd)  # mkstemp 返回的 fd 不关会累积泄漏（每次闸门 1 个）
        tmp = Path(name)
        try:
            tmp.write_text(body, encoding="utf-8")
            res = run_gate(cmd, tmp, timeout=self.gate_timeout, runner=self.runner)
        finally:
            tmp.unlink(missing_ok=True)
        return {"status": res.status, "verdict": res.verdict,
                "findings": res.findings, "receipt": res.receipt}


# ---------------------------------------------------------------- 工具循环
@dataclass
class ToolStep:
    """一次工具调用记录（进报告，便于事后复盘模型查了什么）。"""

    tool: str
    args: dict
    result: str

    def as_dict(self) -> dict:
        return {"tool": self.tool, "args": self.args, "result": self.result[:300]}


@dataclass
class ToolLoopResult:
    """侦察阶段的产出：最终回答 + 调用轨迹 + 停止原因。"""

    text: str = ""
    steps: list[ToolStep] = field(default_factory=list)
    stopped: str = ""          # ""（模型自己收尾）/ max-steps

    def as_dict(self) -> dict:
        return {"text": self.text, "stopped": self.stopped,
                "steps": [s.as_dict() for s in self.steps]}


def run_tool_loop(client, messages: list[dict], box: ToolBox, *, max_steps: int = 4,
                  temperature: float = 0.3, max_tokens: int = 700) -> ToolLoopResult:
    """标准模式的 function-calling 循环。

    模型可以连续调用工具；一旦某轮不再返回 `tool_calls`，就把 content 当结论。
    到 `max_steps` 还没收尾就停下，返回已发生的轨迹（不静默丢弃）。
    """
    convo = [dict(m) for m in messages]
    steps: list[ToolStep] = []
    for _ in range(max(1, int(max_steps))):
        resp = client.chat(convo, tools=box.schema(), tool_choice="auto",
                           temperature=temperature, max_tokens=max_tokens)
        calls = list(getattr(resp, "tool_calls", None) or [])
        if not calls:
            return ToolLoopResult(text=(resp.text or "").strip(), steps=steps)
        convo.append({"role": "assistant", "content": resp.text or "", "tool_calls": calls})
        for call in calls:
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            raw = fn.get("arguments") or "{}"
            if isinstance(raw, str):
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = {}
                    result = _dumps({"error": "arguments 不是合法 JSON"})
                else:
                    result = box.dispatch(name, args)
            else:
                args = dict(raw) if isinstance(raw, dict) else {}
                result = box.dispatch(name, args)
            convo.append({"role": "tool", "tool_call_id": call.get("id", ""),
                          "content": result})
            steps.append(ToolStep(tool=name, args=args, result=result))
    return ToolLoopResult(text="", steps=steps, stopped="max-steps")
