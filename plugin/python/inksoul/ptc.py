"""PTC（程序化工具调用）基座：模型写程序，程序调工具。

为什么换成 PTC
--------------
标准模式的 function calling 是一问一答：模型说「调 X」，宿主执行，结果回灌，再问下一轮。
上下文里于是反复出现「调用记录 + 结果」，跨多章批量诊断时尤其贵。
PTC 把这件事翻转过来：模型写一段程序，程序里自己循环调用工具，只有**最终结论**回到上下文。

安全边界
--------
- 代码在**独立子进程**里跑，父进程只收 stdout 与错误文本；
- 子进程内建受限 builtins（无 open/import/eval/exec，禁私有属性），并清空真实 __builtins__；
- 父进程先做 AST 校验，命中禁用节点直接拒跑，不进子进程；
- 单次运行有超时（默认 60s）与输出上限（20000 字）。
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

#: 禁止出现的名字（含调用）
_FORBIDDEN = {
    "open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "input", "breakpoint", "memoryview", "super",
    "classmethod", "staticmethod", "type",
}

_FENCE = chr(96) * 3


class PtcError(Exception):
    """程序被安全层拒绝（不是运行期错误）。"""


def validate_code(code: str) -> None:
    """AST 白名单校验；不合法抛 :class:`PtcError`。"""
    body = str(code or "")
    if not body.strip():
        raise PtcError("程序为空")
    try:
        tree = ast.parse(body, "<ptc>", "exec")
    except SyntaxError as exc:
        raise PtcError("语法错误：%s（第 %s 行）" % (exc.msg, exc.lineno)) from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise PtcError("不允许 import；工具已直接可用")
        if isinstance(node, ast.Attribute) and str(node.attr).startswith("_"):
            raise PtcError("不允许访问私有属性：%s" % node.attr)
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN:
            raise PtcError("不允许使用：%s" % node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _FORBIDDEN:
            raise PtcError("不允许调用：%s" % node.func.id)


def extract_code(text: str) -> str:
    """从模型回答里取出程序；没有代码块返回空串。"""
    body = str(text or "")
    start = body.find(_FENCE)
    while start != -1:
        nl = body.find(chr(10), start)
        if nl == -1:
            return ""
        lang = body[start + len(_FENCE):nl].strip().lower()
        end = body.find(_FENCE, nl)
        if end == -1:
            return ""
        code = body[nl + 1:end].strip()
        if lang in ("", "python", "py", "python3") and code:
            return code
        start = body.find(_FENCE, end + len(_FENCE))
    return ""


RUNNER_SRC = r"""
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
from pathlib import Path
from inksoul.toolbox import ToolBox

box = ToolBox.__new__(ToolBox)
box.config = None
box.gate_cmd = payload.get("gate_cmd") or ""
box.gate_timeout = float(payload.get("gate_timeout") or 120.0)
box.runner = None
box.roots = [Path(p) for p in payload.get("roots") or []]
box._specs = []

out_lines = []
def emit(*items):
    out_lines.append(" ".join(str(i) for i in items))

def _call(name, args):
    return json.loads(box.dispatch(name, args))

def read_prev(path, limit=3000):
    return _call("read_prev", {"path": path, "limit": limit})

def lookup_bible(query, top=3):
    return _call("lookup_bible", {"query": query, "top": top})

def measure(text):
    return _call("measure", {"text": text})

def run_gate(text, gate=""):
    return _call("run_gate", {"text": text, "gate": gate})

SAFE = {"abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "filter": filter, "float": float, "int": int, "isinstance": isinstance, "len": len,
        "list": list, "map": map, "max": max, "min": min, "print": emit, "range": range,
        "reversed": reversed, "round": round, "set": set, "sorted": sorted, "str": str,
        "sum": sum, "tuple": tuple, "zip": zip, "Exception": Exception,
        "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
        "IndexError": IndexError, "ZeroDivisionError": ZeroDivisionError}

ns = {"__builtins__": SAFE, "read_prev": read_prev, "lookup_bible": lookup_bible,
      "measure": measure, "run_gate": run_gate}
error = ""
try:
    exec(compile(payload["code"], "<ptc>", "exec"), ns)
except SystemExit:
    pass
except BaseException as exc:
    error = "%s: %s" % (type(exc).__name__, exc)
text = "\n".join(out_lines)
if len(text) > 20000:
    text = text[:20000] + "\n…（输出过长，已截断）"
print(json.dumps({"stdout": text, "error": error}, ensure_ascii=False))
"""


@dataclass
class ProgramResult:
    """一次程序执行的结果。"""

    code: str = ""
    stdout: str = ""
    error: str = ""
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.error

    def as_dict(self) -> dict:
        return {"code": self.code[:600], "stdout": self.stdout[:2000],
                "error": self.error, "elapsed": round(self.elapsed, 2)}


def run_program(code: str, box, *, timeout: float = 60.0, python: str | None = None) -> ProgramResult:
    """在子进程里执行程序；任何失败都收敛成 :class:`ProgramResult`。"""
    body = str(code or "")
    try:
        validate_code(body)
    except PtcError as exc:
        return ProgramResult(code=body, error=str(exc))
    payload = {"code": body,
               "roots": [str(p) for p in getattr(box, "roots", []) or []],
               "gate_cmd": getattr(box, "gate_cmd", "") or "",
               "gate_timeout": getattr(box, "gate_timeout", 120.0)}
    env = dict(os.environ)
    src_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = src_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    with tempfile.TemporaryDirectory(prefix="inksoul_ptc_") as td:
        pf = Path(td) / "payload.json"
        pf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        cmd = [python or sys.executable, "-c", RUNNER_SRC, str(pf)]
        started = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=float(timeout), env=env)
        except subprocess.TimeoutExpired:
            return ProgramResult(code=body, error="执行超时（%.0fs）" % float(timeout),
                                 elapsed=float(timeout))
        elapsed = time.time() - started
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0 and not raw:
            tail = (proc.stderr or "").strip()[-600:] or "子进程退出码 %s" % proc.returncode
            return ProgramResult(code=body, error=tail, elapsed=elapsed)
        line = raw.splitlines()[-1] if raw else ""
        try:
            data = json.loads(line)
        except Exception:
            tail = (proc.stderr or "").strip()[-600:] or "子进程没有返回结果"
            return ProgramResult(code=body, stdout=raw[-2000:], error=tail, elapsed=elapsed)
        return ProgramResult(code=body, stdout=str(data.get("stdout") or ""),
                             error=str(data.get("error") or ""), elapsed=elapsed)


PTC_SYSTEM = "\n".join([
    "你是写作前的资料侦察员，用程序化工具调用（PTC）方式工作。",
    "不要一问一答地调工具：把要查的东西写成一段 Python 程序，一次跑完、一次拿到结论。",
    "程序里这些函数直接可用（不用 import）：",
    "  read_prev(path, limit=3000) -> dict  读前文末尾；keys: path, chars, text",
    "  lookup_bible(query, top=3) -> dict   在设定库里按关键词找条目；keys: hits[(source, text)]",
    "  measure(text) -> dict                文体指标；keys: chars, sentences, avg_sentence, cv, comma_per_100, short_ratio",
    "  run_gate(text, gate=\"\") -> dict      文风闸门；keys: status, verdict, findings",
    "用 print() 输出你要看的东西；程序跑完把输出回给你。",
    "规则：",
    "1) 只输出一段 " + _FENCE + "python 代码块，或一句结论；",
    "2) 程序里可以循环、可以用列表和字典，不要一次只调一个工具；",
    "3) 已经有足够信息时，不要再写代码，直接给出不超过 400 字的侦察笔记。",
])


@dataclass
class PtcLoopResult:
    """PTC 侦察的产出：结论 + 每段程序的执行结果。"""

    text: str = ""
    programs: list[dict] = field(default_factory=list)
    stopped: str = ""

    def as_dict(self) -> dict:
        return {"text": self.text, "stopped": self.stopped, "programs": self.programs}


def run_ptc_loop(client, messages: list[dict], box, *, max_rounds: int = 2,
                 temperature: float = 0.3, max_tokens: int = 900,
                 timeout: float = 60.0, python: str | None = None) -> PtcLoopResult:
    """PTC 侦察循环：模型写程序 → 执行 → 回灌输出 → 直到模型给出结论。"""
    convo = [dict(m) for m in messages]
    programs: list[dict] = []
    for _ in range(max(1, int(max_rounds))):
        resp = client.chat(convo, temperature=temperature, max_tokens=max_tokens)
        text = (resp.text or "").strip()
        code = extract_code(text)
        if not code:
            return PtcLoopResult(text=text, programs=programs)
        res = run_program(code, box, timeout=timeout, python=python)
        programs.append(res.as_dict())
        convo.append({"role": "assistant", "content": text})
        shown = ("错误：" + res.error) if res.error else (res.stdout or "（程序没有输出）")
        convo.append({"role": "user", "content":
                      "【程序执行结果】" + chr(10) + shown + chr(10)
                      + "还缺信息就再写一段程序；够了就直接给结论，不要代码块。"})
    return PtcLoopResult(text="", programs=programs, stopped="max-rounds")
