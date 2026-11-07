"""生成控制：文体规划 → 候选初稿 → 局部修订 → 交付。

设计原则（docs/generation_strategy.md）
------------------------------------
- 不追求「每句都不同」：目标是把无意识的模板复用压下去，同时**保护**有意的修辞复现。
- 修订只回传「问题小句 + 前后一句」的窗口，不整篇重写——既省钱又避免改坏全篇。
- 没有 API Key 时也能工作：``offline=True`` 返回文体规划与写作提示，不伪造正文。
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from .config import GenerationConfig, InkSoulConfig
from .errors import ConfigError, InkSoulError
from .llm import LLMClient
from .reviewer import ReviewReport

#: 体裁对应的默认文体策略（规则先验，可被模型覆盖）
GENRE_PRESETS: dict[str, dict] = {
    "小说": {"voice": "限制视角叙述，动作与感官优先", "rhythm": "长短交替，段落收束于短句",
             "dialogue": "对话承担信息与性格，少用标签语"},
    "散文": {"voice": "第一人称思绪与物象交织", "rhythm": "长句为主，允许慢速铺陈",
             "dialogue": "几乎不用对话，用引文与内心独白"},
    "对话": {"voice": "以对白推动，动作只作节拍", "rhythm": "短句密集，留白多",
             "dialogue": "说话方式即性格：词汇、句长、口头禅分层"},
    "诗歌": {"voice": "意象并置，少用连接词", "rhythm": "行内断句，重音落在实词",
             "dialogue": "不用对话"},
}

#: 系统提示：约束模型「怎么写」，而不是「写什么」
SYSTEM_PROMPT = (
    "你是一位中文文学写作者。你的任务不是解释、不是点评，而是直接给出成品正文。\n"
    "硬性要求：\n"
    "1. 不要用总结句收尾，不要写「总之」「综上」这类说明文腔调。\n"
    "2. 不要连续三句使用同一句式框架；不要为了变化而堆砌形容词或强行换同义词。\n"
    "3. 情绪不直接命名（不写「他很难过」），用动作、生理反应、环境侧写承担。\n"
    "4. 人物说话方式要能互相区分：词汇量、句长、口头禅、回避的话题。\n"
    "5. 允许并鼓励有意的重复（排比、回环、动机再现），但要让它读起来是有意的。\n"
    "6. 只输出正文，不输出标题、提纲、说明或 markdown 标记。"
)


def _system(base: str, extra: str = "") -> str:
    """把 skill 摘录接到系统提示后面；没有摘录时原样返回。"""
    extra = (extra or "").strip()
    return base + "\n\n" + extra if extra else base


@dataclass
class CreationBrief:
    """用户的创作要求。"""

    theme: str
    genre: str = "小说"
    perspective: str = ""          # 第一人称/第三人称限制/全知
    target_chars: int = 0          # 0 表示用配置默认
    style_notes: str = ""          # 用户给的文风要求
    must_keep: list[str] = field(default_factory=list)   # 必须保留的句子/设定
    audience: str = ""

    def prompt_block(self) -> str:
        parts = [f"题材与要求：{self.theme}", f"体裁：{self.genre}"]
        if self.perspective:
            parts.append(f"叙事视角：{self.perspective}")
        if self.target_chars:
            parts.append(f"目标篇幅：约 {self.target_chars} 字")
        if self.style_notes:
            parts.append(f"文风要求：{self.style_notes}")
        if self.must_keep:
            parts.append("必须保留：" + "；".join(self.must_keep))
        return "\n".join(parts)


@dataclass
class StylePlan:
    """文体规划：带进生成与修订的策略。"""

    genre: str
    voice: str
    rhythm: str
    dialogue: str
    sentence_policy: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    target_chars: int = 1200
    candidates: int = 3
    temperatures: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_prompt(self) -> str:
        lines = [
            "【文体规划】",
            f"- 叙述声音：{self.voice}",
            f"- 节奏：{self.rhythm}",
            f"- 对话：{self.dialogue}",
        ]
        if self.sentence_policy:
            lines.append("- 句式策略：" + "；".join(self.sentence_policy))
        if self.forbidden:
            lines.append("- 避免：" + "；".join(self.forbidden))
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Draft:
    """一份候选稿。"""

    text: str
    plan: StylePlan
    candidate_id: int = 0
    temperature: float = 0.0
    usage: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class RevisionResult:
    """一轮修订的结果。"""

    text: str
    rounds: int = 0
    applied: int = 0
    skipped: int = 0
    notes: list[str] = field(default_factory=list)


def build_plan(brief: CreationBrief, cfg: InkSoulConfig | None = None, *,
               client: LLMClient | None = None, use_llm: bool = True) -> StylePlan:
    """构造文体规划：先用体裁先验，可选再用模型细化（失败则退回先验）。"""
    gen: GenerationConfig = (cfg.generation if cfg else GenerationConfig())
    preset = GENRE_PRESETS.get(brief.genre, GENRE_PRESETS["小说"])
    plan = StylePlan(
        genre=brief.genre,
        voice=brief.perspective or preset["voice"],
        rhythm=preset["rhythm"],
        dialogue=preset["dialogue"],
        sentence_policy=[
            "小句骨架轮换：陈述/把字/被动/存现交替出现，但不要每句都换",
            "段落至少有一处长句展开，一处短句收束",
        ],
        forbidden=["「不禁」「仿佛时间静止」「心中五味杂陈」这类现成句", "三连排比式形容词堆叠"],
        target_chars=brief.target_chars or gen.target_chars,
        candidates=max(1, gen.candidates),
        temperatures=list(gen.temperature_candidates),
        notes=["先验规划（未调用模型）"],
    )
    if not use_llm or client is None or not client.available:
        plan.notes.append("未配置模型或离线模式：只输出规划与写作提示，不生成正文")
        return plan
    try:
        resp = client.chat(
            [{"role": "system", "content": "你是中文文学编辑，只输出 JSON。"},
             {"role": "user", "content": json.dumps({
                 "任务": "为下面的创作要求制定文体策略",
                 "要求": brief.prompt_block(),
                 "输出字段": {"voice": "叙述声音一句话", "rhythm": "节奏安排一句话",
                              "dialogue": "对话处理一句话", "sentence_policy": ["2-4 条"],
                              "forbidden": ["2-4 条要避免的套话"]},
             }, ensure_ascii=False)}],
            temperature=0.4, json_mode=True)
        data = json.loads(resp.text)
        plan.voice = str(data.get("voice") or plan.voice)
        plan.rhythm = str(data.get("rhythm") or plan.rhythm)
        plan.dialogue = str(data.get("dialogue") or plan.dialogue)
        sp = data.get("sentence_policy")
        if isinstance(sp, list) and sp:
            plan.sentence_policy = [str(x) for x in sp][:6]
        fb = data.get("forbidden")
        if isinstance(fb, list) and fb:
            plan.forbidden = [str(x) for x in fb][:6]
        plan.notes.append("模型已细化文体规划")
    except (InkSoulError, json.JSONDecodeError) as exc:
        plan.notes.append(f"模型细化失败，沿用先验：{exc}")
    return plan


def generate(brief: CreationBrief, plan: StylePlan, client: LLMClient | None, *,
             offline: bool = False, candidate_id: int = 0,
             temperature: float | None = None, extra_system: str = "",
             extra_user: str = "") -> Draft:
    """生成一份候选稿。离线或缺 Key 时返回带提示的占位稿（明确标注未生成）。"""
    if offline or client is None or not client.available:
        raise ConfigError(
            "生成正文需要可用的模型 API",
            hint="配置 api_key（`inksoul config --init`）后重试；"
                 "只想看文体规划可加 `--plan-only`",
        )
    temps = list(plan.temperatures or []) or [getattr(client, "temperature", 0.8)]
    temp = temps[candidate_id % len(temps)] if temperature is None else temperature
    parts = [brief.prompt_block(), plan.as_prompt()]
    if (extra_user or "").strip():
        parts.append(extra_user.strip())
    parts.append(f"请直接写出正文，约 {plan.target_chars} 字。")
    user_prompt = "\n\n".join(parts)
    resp = client.chat(
        [{"role": "system", "content": _system(SYSTEM_PROMPT, extra_system)},
         {"role": "user", "content": user_prompt}],
        temperature=temp, max_tokens=max(512, int(plan.target_chars * 2.2)),
    )
    text = _clean_output(resp.text)
    return Draft(text=text, plan=plan, candidate_id=candidate_id,
                 temperature=temp, usage=resp.usage,
                 notes=[f"finish_reason={resp.finish_reason}", f"latency={resp.latency_s:.1f}s"])


def _clean_output(text: str) -> str:
    """去掉模型偶尔加的 markdown 代码围栏与前后说明。"""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def revision_prompt(issue_texts: list[str], window: dict, plan: StylePlan) -> str:
    """构造单个修订请求：只给问题小句的窗口，不整篇重写。"""
    window_text = "\n".join(
        f"{tag}：{text}" for tag, text in
        [("上一句", window.get("prev", "")), ("问题句", window.get("cur", "")),
         ("下一句", window.get("next", ""))] if text
    )
    return (
        "下面是同一篇作品里的一个局部。只改写「问题句」一句，保持叙述视角、时态、"
        "人物语气不变，不要扩写成一大段，不要解释。\n"
        f"【问题】{'；'.join(issue_texts)}\n"
        f"【上下文】\n{window_text}\n"
        f"{plan.as_prompt()}\n"
        "只输出改写后的那一句。"
    )


def revise(text: str, review_report: ReviewReport, client: LLMClient | None,
           plan: StylePlan, *, cfg: InkSoulConfig | None = None,
           max_rounds: int | None = None, offline: bool = False,
           extra_system: str = "") -> RevisionResult:
    """按审查问题做局部修订：逐条替换，替换后不重新分析（由调用方再跑一次 analyze 复核）。"""
    if offline or client is None or not client.available:
        return RevisionResult(text=text, rounds=0, applied=0,
                              skipped=len(review_report.issues),
                              notes=["离线或未配置模型：跳过修订，仅返回问题清单"])
    gen = cfg.generation if cfg else GenerationConfig()
    rounds_limit = gen.max_revision_rounds if max_rounds is None else max_rounds
    result = text
    applied = skipped = 0
    rounds = 0
    for _round in range(max(0, rounds_limit)):
        targets = [i for i in review_report.issues if i.severity >= 0.6 and i.text]
        if not targets:
            break
        changed = False
        for issue in targets[:8]:
            idx = result.find(issue.text)
            if idx < 0:
                skipped += 1
                continue
            window = _window(result, issue.text)
            try:
                resp = client.chat(
                    [{"role": "system", "content": _system(SYSTEM_PROMPT, extra_system)},
                     {"role": "user", "content": revision_prompt([f"{issue.kind}：{issue.suggestion}"], window, plan)}],
                    temperature=0.5, max_tokens=400)
            except InkSoulError:
                skipped += 1
                continue
            new_sentence = _clean_output(resp.text).split("\n")[0].strip()
            if not new_sentence or new_sentence == issue.text:
                skipped += 1
                continue
            if len(new_sentence) > len(issue.text) * 3 + 40:
                skipped += 1
                continue
            result = result[:idx] + new_sentence + result[idx + len(issue.text):]
            applied += 1
            changed = True
        rounds += 1
        if not changed:
            break
    return RevisionResult(text=result, rounds=rounds, applied=applied, skipped=skipped,
                          notes=["局部替换式修订：只改命中问题的小句，未整篇重写"])


def restyle(text: str, findings: list[str], client: LLMClient | None, plan: StylePlan, *,
            cfg: InkSoulConfig | None = None, offline: bool = False,
            extra_system: str = "") -> RevisionResult:
    """闸门未过时的整篇风格重写：只改文风，情节与信息量不变。"""
    if offline or client is None or not client.available:
        return RevisionResult(text=text, rounds=0, applied=0, skipped=len(findings),
                              notes=["离线或未配置模型：跳过风格重写"])
    if not findings:
        return RevisionResult(text=text, rounds=0, applied=0,
                              notes=["闸门未解析到命中条目，跳过风格重写"])
    gen = cfg.generation if cfg else GenerationConfig()
    problems = "\n".join("- " + x for x in findings[:12])
    user = "\n\n".join([
        "下面这篇正文没有通过文风闸门。请保持情节、人物、对话与信息量不变，重写全文，",
        "逐条消掉这些文风问题（不要解释改了什么）：",
        problems,
        plan.as_prompt(),
        "【正文】\n" + text,
        "只输出重写后的正文。",
    ])
    budget = max(gen.target_chars, len(text))
    resp = client.chat(
        [{"role": "system", "content": _system(SYSTEM_PROMPT, extra_system)},
         {"role": "user", "content": user}],
        temperature=0.6, max_tokens=max(1024, int(budget * 2.2)),
    )
    out = _clean_output(resp.text)
    if not out:
        return RevisionResult(text=text, rounds=1, applied=0, skipped=len(findings),
                              notes=["模型返回空稿，保留原稿"])
    return RevisionResult(text=out, rounds=1, applied=len(findings), skipped=0,
                          notes=["闸门未过 → 按命中条目整篇重写（情节不变）"])


def _window(text: str, snippet: str, span: int = 80) -> dict:
    idx = text.find(snippet)
    if idx < 0:
        return {"cur": snippet}
    before = text[:idx]
    after = text[idx + len(snippet):]
    prev = before.strip()[-span:].split("。")[-1] if before.strip() else ""
    nxt = after.strip().split("。")[0][:span] if after.strip() else ""
    return {"prev": prev.strip(), "cur": snippet, "next": nxt.strip()}


PROMPT_TEMPLATE = """请根据以下要求写一篇中文{brief.genre}，约 {plan.target_chars} 字。

{brief_block}

{plan_block}

直接输出正文。"""


@dataclass
class GenerationResult:
    """一次完整生成的结果（含自检与修订记录）。"""

    text: str
    plan: StylePlan
    analysis: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    candidates: int = 0
    revisions: int = 0


class GenerationController:
    """把「规划 → 多候选 → 自检 → 局部修订」串起来。

    选稿原则：先看有没有「阻断级」机械复用，再看候选顺序——**不做综合打分**，
    避免把创作变成指标优化游戏（docs/generation_strategy.md §5）。
    """

    def __init__(self, config: InkSoulConfig, *, client: LLMClient | None = None):
        self.config = config
        self.client = client if client is not None else LLMClient(config.model)

    # ------------------------------------------------------------------ 规划
    def plan(self, theme: str, *, genre: str = "小说", perspective: str = "",
             use_llm: bool = True) -> StylePlan:
        brief = CreationBrief(theme=theme, genre=genre or "小说", perspective=perspective,
                              target_chars=self.config.generation.target_chars)
        return build_plan(brief, self.config, client=self.client, use_llm=use_llm)

    # ------------------------------------------------------------------ 生成
    def generate(self, theme: str, *, genre: str = "小说", perspective: str = "",
                 max_rounds: int | None = None, offline: bool = False,
                 candidates: int | None = None) -> GenerationResult:
        from .analyzer import Analyzer

        brief = CreationBrief(theme=theme, genre=genre or "小说", perspective=perspective,
                              target_chars=self.config.generation.target_chars)
        plan = build_plan(brief, self.config, client=self.client, use_llm=not offline)
        if offline or not self.client.available:
            raise ConfigError(
                "生成正文需要可用的模型 API",
                hint="先 `inksoul config --init` 填 api_key；只想看规划用 `inksoul plan`",
            )
        analyzer = Analyzer(self.config)
        n = max(1, candidates or plan.candidates)
        drafts: list[tuple[Draft, object]] = []
        for i in range(n):
            draft = generate(brief, plan, self.client, candidate_id=i)
            report = analyzer.analyze(draft.text, with_review=True)
            drafts.append((draft, report))
        best_draft, best_report = min(
            drafts,
            key=lambda pair: (len(pair[1].review.blocking) if pair[1].review else 0,
                              pair[0].candidate_id),
        )
        result_text = best_draft.text
        rev = revise(result_text, best_report.review, self.client, plan,
                     cfg=self.config, max_rounds=max_rounds)
        final_report = analyzer.analyze(rev.text, with_review=True)
        return GenerationResult(
            text=rev.text, plan=plan,
            analysis=[final_report.as_dict()],
            notes=[f"候选 {n} 个，选中 #{best_draft.candidate_id}（按阻断问题数最少）",
                   f"修订应用 {rev.applied} 处，跳过 {rev.skipped} 处"],
            candidates=n, revisions=rev.applied,
        )