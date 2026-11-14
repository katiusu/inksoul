"""生成控制：文体规划 → 候选初稿 → 局部修订 → 交付。

设计原则（docs/generation_strategy.md）
------------------------------------
- 不追求「每句都不同」：目标是把无意识的模板复用压下去，同时**保护**有意的修辞复现。
- 修订只回传「问题小句 + 前后一句」的窗口，不整篇重写——既省钱又避免改坏全篇。
- 没有 API Key 时也能工作：``offline=True`` 返回文体规划与写作提示，不伪造正文。
"""
from __future__ import annotations

import difflib
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

#: 语域先验：与体裁正交。同一体裁下，「情色直写」和「冷硬悬疑」的句法不该共用一份说明书。
#: 键名进 CLI（--register）；未登录值回退到「文学书面」，不报错。
REGISTER_PRESETS: dict[str, dict] = {
    # 「文学书面」是有意留空的语域：不覆盖 voice/rhythm/dialogue，
    # 这三项仍由体裁先验决定，它只追加禁用项与句式策略。
    "文学书面": {
        "sentence_policy": [
            "小句骨架轮换：陈述/把字/被动/存现交替出现，但不要每句都换",
            "长句只用于确有因果或递进的地方，其余句子照直说",
        ],
        "forbid": ["整段无事件推进的景物描写", "把环境当情绪的容器"],
    },
    "口语都市": {
        "voice": "贴近人物日常说话方式的限制视角，允许短促与语病",
        "rhythm": "短句为主，段落短，不追求句末节奏",
        "dialogue": "对白占三成以上；靠称呼、口头禅、回避的话题区分说话人，不用「他说」「她道」标签；"
                    "心里冒出的话直接用引号写出，不要由叙述者转述",
        "sentence_policy": [
            "小句骨架轮换：陈述/把字/被动/存现交替出现，但不要每句都换",
            "段落收在动作或一句对话上，不要先拉长再收短",
            "动作、反应、台词各自成段：一段只做一件事，不要把三样并进一段",
        ],
        "forbid": ["书面语连接词（因此/然而/于是）", "四字格与成语堆叠", "人物在心里替自己解释"],
    },
    "爽文快推": {
        "voice": "贴近主角的短视角，信息与胜负感优先",
        "rhythm": "短句密集，每段至少一个推进点",
        "dialogue": "对白推动冲突，短、带刺；冲突当场用台词讲出来，不转述成「他们争执了几句」",
        "sentence_policy": [
            "短句为主，一句一个动作或一条信息",
            "段落不超过四五句，段尾落在新信息上",
            "关键转折用一句台词完成，不要用叙述交代",
        ],
        "forbid": ["长篇铺陈", "留白式结尾"],
    },
    "冷硬悬疑": {
        "voice": "冷静的外部观察，限制在主角的感官与判断",
        "rhythm": "短句，省略连词，留断点",
        "dialogue": "对白简短，答非所问，信息靠漏；直接写台词，不补「他冷冷地说」这类标签，语气交给标点",
        "sentence_policy": [
            "省略连词，句子之间用句号断开",
            "长句只用于判断和推演，不用来铺陈景物",
            "一个动作一段，段尾停住不解释",
        ],
        "forbid": ["用形容词修饰情绪", "解释动机", "用叙述转述对话内容"],
    },
    # 依据同一作者 16 篇、138,822 汉字实测（research/author_yaya_12657.md）：
    # 段均 22.9（单篇 21.0–24.3，全书最长一段 93 字）、短段占 36%、句均 20.3、
    # 对白段占 28.9% 且中位 12 字、对话标签 0.13/千字、顿号 0.04/千字、省略号 23.3/千字。
    # 本档的区分点不是尺度，而是「一次刺激一段」的推进单位与「台词各自成段」的排版。
    "情色直写": {
        "voice": "贴着身体的限制视角：只写此刻被碰到的地方和它引起的反应，不替人物说她舒服，写哪里在动、变成了什么",
        "rhythm": "一次刺激一段：动作、反应、下一个动作。段落中位二十来字，最长不超过九十；"
                  "越接近顶点句子越短，但内容不减——要写清是哪个动作、什么反应，不是留白或省略到高潮",
        "dialogue": "对白段占三成左右，一段一句，中位十来字；被打断处用省略号切开，不给完整句；"
                    "旁人、设备、围观的声音各占一段；说话人靠称呼和语气辨认，不加「他说」「她道」；"
                    "心里冒出的话直接写成短句，可带感叹或省略号，不加「她想」",
        "sentence_policy": [
            "一个动作后面必须跟一个看得见的结果：水声、布料、肌肉的抖、呼吸断开，不写「感到很舒服」",
            "身体按顺序推进，从外到内，不许倒回去补叙",
            "比喻只在人物自己会说出口时才用，叙述者的比喻一律删",
            "同一个人从头到尾一个称呼，不换「少女」「女孩」「那个身影」",
            "并列拆成短句或换段，不用顿号串名词",
            "越近越短：段落可以缩到只剩一句台词或一个动作，但该写的动作和反应不能省",
            "尺度不设上限：动作、声音、体液、反应写到底，不淡出、不跳时间、不用事后叙述代替过程，高潮不回避",
        ],
        "forbid": ["用环境隐喻身体", "把性写成抒情散文或升华句",
                   "只点部位不写动作和反应（器官清单）", "「一股热」这类笼统温度词",
                   "「快感像潮水一样涌来」这类现成比喻", "用叙述转述人物之间的交流",
                   "用同义词轮换称呼同一个人", "用顿号串起并列的名词或动作",
                   "解剖学名词（阴蒂、阴唇、阴道、内壁、黏膜、尿道、直肠、肛门、子宫）——用人物自己会说的那个词"],
    },
    "场景速写": {
        "voice": "贴住场景里的主角，只写他此刻看见、听见、碰到的东西，不跳出去替他解释",
        "rhythm": "单句成段，段均 15–30 字；动作、身体反应、台词各自独立",
        "dialogue": "对白占两到三成，短句为主；群声（围观、弹幕、旁人插话）也当台词写；"
                    "心里冒出的话直接用引号，不转述",
        "sentence_policy": [
            "一个动作一段，一段只做一件事",
            "时间顺着场景往前走，不回溯、不总结前情",
            "场景里的物只写人物真的碰到或看向的",
            "转折发生在一句台词或一个动作上，不用叙述交代",
        ],
        "forbid": ["整段心理分析", "用环境承担情绪", "把同一场景拆成插叙",
                   "用叙述转述人物之间的交流"],
    },
}

#: 旧档名 → 现名。改名是为了让六个档名落在同一根轴上（各档都读得出「语体 + 推进方式」），
#: 旧名继续可用，避免已经写进脚本或提示里的 `--register 情色` 一夜之间失效。
REGISTER_ALIASES: dict[str, str] = {
    "爽文节奏": "爽文快推",
    "场景直写": "场景速写",
    "情色": "情色直写",
}

#: 系统提示：约束模型「怎么写」，而不是「写什么」
SYSTEM_PROMPT = (
    "你是一位中文文学写作者。你的任务不是解释、不是点评，而是直接给出成品正文。\n"
    "硬性要求：\n"
    "1. 不要用总结句收尾，不要写「总之」「综上」这类说明文腔调。\n"
    "2. 不要连续三句使用同一句式框架；不要为了变化而堆砌形容词或强行换同义词。\n"
    "3. 情绪不直接命名（不写「他很难过」），也不要把它交给环境去承担。写人物此刻要做什么、\n"
    "   被什么挡住、身体先出现什么反应；环境只在他真的看向、摸到、闻到某物时才出现。\n"
    "   人物心里翻腾的话，就写成他自己会说的那一句（可以直接加引号），不要由叙述者替他总结。\n"
    "4. 人物说话方式要能互相区分：词汇量、句长、口头禅、回避的话题；靠称呼和语气区分，\n"
    "   不要靠「他说」「她道」这类标签承接连篇对白。\n"
    "5. 不要用数字、计数、日期、重复动作为结构造仪式感（数到十七、第 28 天、三张纸）。\n"
    "   重复只能来自人物自己没察觉的口头禅或习惯动作。\n"
    "6. 不要用顿号串名词。并列的东西拆成短句或换段写，一句里顿号最多两个；"
    "   罗列式清单（灯光、声音、气味、温度）一律拆开。\n"
    "7. 只输出正文，不输出标题、提纲、说明或 markdown 标记。"
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
    register: str = "文学书面"     # 语域：文学书面/口语都市/爽文快推/冷硬悬疑/情色直写/场景速写
    # 小说默认第三人称限制视角：留空等于让模型自己挑，实测常滑向第一人称。
    perspective: str = ""          # 第一人称/第三人称限制/全知；留空按体裁补（见 __post_init__）
    target_chars: int = 0          # 0 表示用配置默认
    style_notes: str = ""          # 用户给的文风要求
    must_keep: list[str] = field(default_factory=list)   # 必须保留的句子/设定
    audience: str = ""

    def __post_init__(self) -> None:
        # 视角留空时按体裁补：小说类默认第三人称限制视角（留空等于让模型自己挑，
        # 实测常滑向第一人称）；散文保留传统的第一人称思绪。
        # 语域先在这里规范化：提示词里写的必须与 plan 实际采用的同一档，
        # 否则用户拼错一个词，模型看到「语域：情色」而规则套的是「文学书面」。
        if self.register:
            self.register = REGISTER_ALIASES.get(self.register, self.register)
            if self.register not in REGISTER_PRESETS:
                self.register = "文学书面"
        if not self.perspective:
            # 只给叙事体裁补默认视角：散文保留第一人称思绪，小说/对话用第三人称限制视角；
            # 诗歌与未知体裁强加「第三人称限制视角」是错的，留空交给体裁先验。
            if self.genre == "散文":
                self.perspective = "第一人称"
            elif self.genre in ("小说", "对话"):
                self.perspective = "第三人称限制视角"

    def prompt_block(self) -> str:
        parts = [f"题材与要求：{self.theme}", f"体裁：{self.genre}"]
        if self.register:
            parts.append(f"语域：{self.register}")
        if self.perspective:
            parts.append(f"叙事视角：{self.perspective}")
        if self.target_chars:
            parts.append(f"目标篇幅：约 {self.target_chars} 字")
        if self.style_notes:
            parts.append(f"文风要求：{self.style_notes}")
        if self.must_keep:
            parts.append("必须保留：" + "；".join(self.must_keep))
        return "\n".join(parts)


def _human_target_lines():
    """人类池分位区间，作为写正文时的显式风格目标（池缺失则空）。"""
    try:
        from .style_pool import load_pool

        pool = load_pool()
        stats = (pool or {}).get("genres", {}).get("网文") or {}
        stats = stats.get("dims") or stats
        rows = [
            ("长句占比", "long_sentence_share", "%.2f"),
            ("连接词/千字", "conj_per_kchar", "%.1f"),
            ("信息密度", "information_density_mean", "%.2f"),
            ("骨架复用率", "reuse_rate", "%.2f"),
        ]
        out = []
        for label, key, fmt in rows:
            st = stats.get(key) or {}
            if "p10" in st and "p90" in st:
                out.append("%s %s–%s" % (label, fmt % st["p10"], fmt % st["p90"]))
        # 对白占比不给区间：p10 只有 0.04，写「0.04–0.44」等于默许通篇没有台词。
        # 改取人类池均值的一半作硬下限——低于它就不是这一体裁的叙述方式了。
        dlg = stats.get("dialogue_ratio") or {}
        if "mean" in dlg:
            out.append("对白占比 ≥%.2f（人类池均值 %.2f；低于此值视为不合格）"
                       % (dlg["mean"] * 0.5, dlg["mean"]))
        return out
    except Exception:  # noqa: BLE001
        return []


@dataclass
class StylePlan:
    """文体规划：带进生成与修订的策略。"""

    genre: str
    voice: str
    rhythm: str
    dialogue: str
    register: str = "文学书面"
    sentence_policy: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    target_chars: int = 1200
    candidates: int = 3
    temperatures: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_prompt(self) -> str:
        lines = [
            "【文体规划】",
            f"- 语域：{self.register}",
            f"- 叙述声音：{self.voice}",
            f"- 节奏：{self.rhythm}",
            f"- 对话：{self.dialogue}",
        ]
        if self.sentence_policy:
            lines.append("- 句式策略：" + "；".join(self.sentence_policy))
        if self.forbidden:
            lines.append("- 避免：" + "；".join(self.forbidden))
        targets = _human_target_lines()
        if targets:
            lines.append("- 人类写法目标（人类网文池 p10–p90）：" + "；".join(targets))
            lines.append("- 以上是统计目标：靠叙事推进与细节控制达成，不要机械凑数，也不要写成指标清单")
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
    # 语域与体裁正交：语域先验覆盖 voice/rhythm/dialogue 三项，其余沿用体裁先验。
    # 未登录的语域静默回退到文学书面，不让拼错一个词就报错。
    reg_name = REGISTER_ALIASES.get(brief.register, brief.register)
    if reg_name not in REGISTER_PRESETS:      # 拼错或旧值：静默落到文学书面，别把无效档名写进提示
        reg_name = "文学书面"
    reg = REGISTER_PRESETS.get(reg_name) or {}
    plan = StylePlan(
        genre=brief.genre,
        register=reg_name,
        # 人称只进 prompt_block 的「叙事视角」一行，不参与 voice 覆盖：
        # 一填人称就把六个语域的 voice 全顶掉，是 v0.7.0 的回归。
        voice=reg.get("voice") or preset["voice"],
        rhythm=reg.get("rhythm") or preset["rhythm"],
        dialogue=reg.get("dialogue") or preset["dialogue"],
        sentence_policy=list(reg.get("sentence_policy") or [
            "小句骨架轮换：陈述/把字/被动/存现交替出现，但不要每句都换",
            "段落至少有一处长句展开，一处短句收束",
        ]),
        forbidden=(list(reg.get("forbid") or [])
                   + ["「不禁」「仿佛时间静止」「心中五味杂陈」这类现成句", "三连排比式形容词堆叠"]),
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


def _locate(text: str, needle: str, *, min_ratio: float = 0.6) -> tuple[int, int] | None:
    """在正文里定位一条问题句：返回 (start, end)，失败返回 None。

    审查阶段的小句可能被规范化过（引号/空白/省略号），精确 find 会失配。
    先做精确匹配，再把两侧都压成「只留字母数字汉字」的串做 difflib 对齐，
    用索引映射回原文，保证替换范围覆盖整条问题句而不是残片。
    """
    if not needle:
        return None
    idx = text.find(needle)
    if idx >= 0:
        return idx, idx + len(needle)
    norm_n, core = [], "".join(c for c in needle if c.isalnum())
    if len(core) < 6:
        return None
    norm_t, pos = [], []
    for i, ch in enumerate(text):
        if ch.isalnum():
            norm_t.append(ch)
            pos.append(i)
    if not norm_t:
        return None
    matcher = difflib.SequenceMatcher(None, "".join(norm_t), core, autojunk=False)
    block = matcher.find_longest_match(0, len(norm_t), 0, len(core))
    if block.size >= max(6, int(len(core) * min_ratio)):
        return pos[block.a], pos[block.a + block.size - 1] + 1
    return None


_SENT_SPLIT = re.compile(r"[。！？\n]+")


def _tag_total(text: str) -> int:
    """窗口内标记总数（轻量），用于改写前后对比。"""
    from .markers import total_tags
    return total_tags(text)


def _sentence_cv(text: str) -> float | None:
    lens = [len(s.strip()) for s in _SENT_SPLIT.split(text) if len(s.strip()) >= 2]
    if len(lens) < 5:
        return None
    mean = sum(lens) / len(lens)
    if mean <= 0:
        return None
    var = sum((x - mean) ** 2 for x in lens) / len(lens)
    return (var ** 0.5) / mean


def _char_ngram_cosine(a: str, b: str, n: int = 3) -> float:
    from collections import Counter
    ca = Counter(a[i:i + n] for i in range(max(0, len(a) - n + 1)))
    cb = Counter(b[i:i + n] for i in range(max(0, len(b) - n + 1)))
    if not ca or not cb:
        return 0.0
    inter = sum((ca & cb).values())
    return inter / ((sum(ca.values()) ** 0.5) * (sum(cb.values()) ** 0.5))


def _mtld_of(text: str) -> float | None:
    try:
        from .lexical import mtld
        from .text_processor import process
        words = [w for w in process(text).words if w]
        return mtld(words) if len(words) >= 50 else None
    except Exception:
        return None


def _style_distance(text: str):
    """到人类池的距离（越低越像人）；池/依赖缺失时 None。"""
    try:
        from .style_pool import distance_of_text, load_pool

        return distance_of_text(text, load_pool())
    except Exception:  # noqa: BLE001
        return None


def _fidelity_checks(text: str, out: str) -> dict:
    """restyle 保真检查：长度 + 语义（3-gram 余弦）+ 方差（句长 CV / MTLD）。

    依据 Sourati 等 2026：AI 润色把文本方差压低 21–50%，而语义余弦仍有 87% 样本 >0.95。
    所以「像不像原文」不够，必须同时看「散度有没有被抹平」。
    """
    n = len(text)
    ratio = len(out) / max(1, n)
    sim = _char_ngram_cosine(text, out)
    cv_a, cv_b = _sentence_cv(text), _sentence_cv(out)
    mt_a, mt_b = _mtld_of(text), _mtld_of(out)
    v: list[str] = []
    if n >= 500 and not (0.85 <= ratio <= 1.15):
        v.append("字数 %.0f%%（要求 85–115%%）" % (100 * ratio))
    if n >= 500 and sim < 0.50:
        v.append("3-gram 余弦 %.2f（< 0.50，可能抽掉内容）" % sim)
    # 只拦「下降」：Sourati 说的失败模式是散度被抹平，不是被放开
    if cv_a and cv_b and (cv_a - cv_b) / cv_a > 0.15:
        v.append("句长 CV %.2f→%.2f（下降 >15%%，散度被抹平）" % (cv_a, cv_b))
    if mt_a and mt_b and (mt_a - mt_b) / mt_a > 0.15:
        v.append("MTLD %.0f→%.0f（下降 >15%%，词汇多样性被压平）" % (mt_a, mt_b))
    return {"ratio": ratio, "sim": sim, "cv": (cv_a, cv_b),
            "mtld": (mt_a, mt_b), "violations": v}


def _retry_sentence(client: LLMClient, issue, window: dict, plan: StylePlan,
                    extra_system: str, original: str) -> str:
    """一次重采样：明确要求避开刚被拦下的结构。"""
    try:
        resp = client.chat(
            [{"role": "system", "content": _system(SYSTEM_PROMPT, extra_system)},
             {"role": "user", "content": revision_prompt(
                 [f"{issue.kind}：{issue.suggestion}",
                  "不要用被动句、名词化框架或四字格堆叠"],
                 window, plan)}],
            temperature=0.8, max_tokens=400)
    except InkSoulError:
        return ""
    out = _clean_output(resp.text).split("\n")[0].strip()
    if not out or out == original:
        return ""
    if len(out) > len(original) * 3 + 40:
        return ""
    return out


def revise(text: str, review_report: ReviewReport, client: LLMClient | None,
           plan: StylePlan, *, cfg: InkSoulConfig | None = None,
           max_rounds: int | None = None, offline: bool = False,
           extra_system: str = "", min_severity: float = 0.45,
           max_items: int = 8, recheck: bool = True,
           style_guard: bool = True) -> RevisionResult:
    """按审查问题做局部修订：逐条替换，替换后做**局部复检**（D1）。

    复检口径：同一 ±200 字窗口里，新句不能把标记堆得比原来更高；
    一次重采样仍不改善就放弃这句——不用新问题换旧问题。
    style_guard：额外要求该窗口到人类池的距离不上升（容忍 +0.05）。
    """
    if offline or client is None or not client.available:
        return RevisionResult(text=text, rounds=0, applied=0,
                              skipped=len(review_report.issues),
                              notes=["离线或未配置模型：跳过修订，仅返回问题清单"])
    gen = cfg.generation if cfg else GenerationConfig()
    rounds_limit = gen.max_revision_rounds if max_rounds is None else max_rounds
    result = text
    applied = skipped = missed = rejected = 0
    rounds = 0
    for _round in range(max(0, rounds_limit)):
        targets = [i for i in review_report.issues
                   if i.severity >= min_severity and i.text]
        if not targets:
            break
        changed = False
        for issue in targets[:max_items]:
            span = _locate(result, issue.text)
            if span is None:
                missed += 1
                skipped += 1
                continue
            start, end = span
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
                rejected += 1
                skipped += 1
                continue
            if len(new_sentence) > len(issue.text) * 3 + 40:
                rejected += 1
                skipped += 1
                continue
            if recheck:
                w0, w1 = max(0, start - 200), min(len(result), end + 200)
                before_tags = _tag_total(result[w0:w1])
                after_tags = _tag_total(result[w0:start] + new_sentence + result[end:w1])
                # 容差：单条命中属于噪声，不因此否决改写
                if after_tags > max(before_tags + 1, 1):
                    retry = _retry_sentence(client, issue, window, plan,
                                            extra_system, result[start:end])
                    if retry:
                        after_tags = _tag_total(result[w0:start] + retry + result[end:w1])
                    if not retry or after_tags > max(before_tags + 1, 1):
                        rejected += 1
                        skipped += 1
                        continue
                    new_sentence = retry
            if style_guard:
                win_before = result[w0:w1]
                win_after = result[w0:start] + new_sentence + result[end:w1]
                d0, d1 = _style_distance(win_before), _style_distance(win_after)
                if d0 is not None and d1 is not None and d1 > d0 + 0.05:
                    retry = _retry_sentence(client, issue, window, plan,
                                            extra_system, result[start:end])
                    if retry:
                        win_after = result[w0:start] + retry + result[end:w1]
                        d1 = _style_distance(win_after)
                    if not retry or d1 is None or d1 > d0 + 0.05:
                        rejected += 1
                        skipped += 1
                        continue
                    new_sentence = retry
            # 模糊定位可能停在句号前；新句自带标点时补吞原标点，避免出现「。。」
            while (end < len(result) and result[end] in "。！？；，、"
                   and new_sentence[-1:] in "。！？；，、"):
                end += 1
            result = result[:start] + new_sentence + result[end:]
            applied += 1
            changed = True
        rounds += 1
        if not changed:
            break
    if applied == 0 and missed == 0 and rejected == 0:
        note = "无可修订项（没有 severity≥%.1f 的问题）" % min_severity
    else:
        note = ("局部替换式修订：应用 %d 处，定位失败 %d 处，改写不合格 %d 处"
                "（只改命中问题的小句）" % (applied, missed, rejected))
    return RevisionResult(text=result, rounds=rounds, applied=applied, skipped=skipped,
                          notes=[note])


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
    if len(text) >= 500 and len(out) < int(len(text) * 0.7):
        return RevisionResult(
            text=text, rounds=1, applied=0, skipped=0,
            notes=["重写稿字数掉到 %.0f%%（%d→%d 字），判定为丢内容，保留原稿"
                   % (100.0 * len(out) / max(1, len(text)), len(text), len(out))])
    d0, d1 = _style_distance(text), _style_distance(out)
    if d0 is not None and d1 is not None and d1 > d0 + 0.15:
        return RevisionResult(
            text=text, rounds=1, applied=0, skipped=0,
            notes=["重写稿离人类池更远（%.2f→%.2f，容忍 +0.15），保留原稿" % (d0, d1)])
    checks = _fidelity_checks(text, out)
    if checks["violations"]:
        return RevisionResult(
            text=text, rounds=1, applied=0, skipped=0,
            notes=["重写稿未过保真检查，保留原稿：%s" % "；".join(checks["violations"])])
    return RevisionResult(text=out, rounds=1, applied=len(findings), skipped=0,
                          notes=["闸门未过 → 按命中条目整篇重写（情节不变）",
                                 "保真：字数 %.0f%%｜3-gram 余弦 %.2f｜句长 CV %s｜MTLD %s"
                                 % (100.0 * checks["ratio"], checks["sim"],
                                    "→".join("%.2f" % x for x in checks["cv"] if x) or "样本不足",
                                    "→".join("%.0f" % x for x in checks["mtld"] if x) or "样本不足")])


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
    def plan(self, theme: str, *, genre: str = "小说", register: str = "文学书面",
             perspective: str = "",
             use_llm: bool = True) -> StylePlan:
        brief = CreationBrief(theme=theme, genre=genre or "小说", register=register,
                              perspective=perspective,
                              target_chars=self.config.generation.target_chars)
        return build_plan(brief, self.config, client=self.client, use_llm=use_llm)

    # ------------------------------------------------------------------ 生成
    def generate(self, theme: str, *, genre: str = "小说", register: str = "文学书面",
                 perspective: str = "",
                 max_rounds: int | None = None, offline: bool = False,
                 candidates: int | None = None) -> GenerationResult:
        from .analyzer import Analyzer

        brief = CreationBrief(theme=theme, genre=genre or "小说", register=register,
                              perspective=perspective,
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
        # 选稿：阻断问题少者优先；平票时按「离均值多远」择优（骨架复用低、模式熵高），
        # 而不是按 candidate_id 顺序取第一稿——后者在阻断恒为 0 时会退化成
        # 「永远选温度最低那稿」，把多候选择优变成多候选陪跑。
        def _rank(pair):
            draft_i, report_i = pair
            blocking = len(report_i.review.blocking) if report_i.review else 0
            fp = report_i.fingerprint
            return (blocking, -(fp.pattern_entropy or 0.0), fp.reuse_rate or 0.0)

        best_draft, best_report = min(drafts, key=_rank)
        result_text = best_draft.text
        rev = revise(result_text, best_report.review, self.client, plan,
                     cfg=self.config, max_rounds=max_rounds)
        final_report = analyzer.analyze(rev.text, with_review=True)
        return GenerationResult(
            text=rev.text, plan=plan,
            analysis=[final_report.as_dict()],
            notes=[f"候选 {n} 个，选中 #{best_draft.candidate_id}（阻断最少，平票取复用最低/熵最高）",
                   f"修订应用 {rev.applied} 处，跳过 {rev.skipped} 处"],
            candidates=n, revisions=rev.applied,
        )