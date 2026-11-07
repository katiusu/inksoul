"""汉语结构归一化（N1–N10）。

目标：把「内容词」抹掉、把「功能骨架」保留并分类，使「他慢慢地推开了房门」
与「她轻轻地关上了窗户」落到同一骨架，而不会把无关句子判成同构。

归一表是**数据资产**，必须版本化；换表即需要重建基线（见 docs/algorithm_design.md §4）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .nlp.backend import Token

NORM_TABLE_VERSION = "v1"

# ---------------------------------------------------------------- 词表
# N1 否定
NEG_WORDS = {"不", "没", "没有", "别", "未", "甭", "无非", "不再", "并不", "从未", "毫不", "未曾", "勿"}
# N2 限定副词
LIM_WORDS = {"只", "只是", "仅仅", "仅", "不过", "就", "才", "光是", "偏偏", "独", "单"}
# 程度
DEG_WORDS = {"很", "太", "非常", "极", "最", "更", "越", "十分", "特别", "格外", "异常", "略", "稍", "颇", "挺", "好生"}
# 时间
TIME_ADV = {"已经", "刚刚", "刚", "忽然", "突然", "终于", "曾经", "立刻", "马上", "顿时", "随即", "一直", "始终", "仍在", "还在", "正", "正在", "早", "早已"}
# 情态
MOD_WORDS = {"大概", "也许", "似乎", "仿佛", "好像", "或许", "恐怕", "显然", "居然", "竟然", "简直", "几乎", "确实", "果然", "不免", "难免"}
# 频率
FREQ_ADV = {"又", "再", "还", "也", "总", "总是", "常常", "经常", "偶尔", "不时", "反复", "一遍遍", "一再"}
# N3 介词
PREP_BA = {"把", "将"}
PREP_BEI = {"被", "让", "叫", "给"}
PREP_LOC = {"在", "于", "从", "向", "往", "朝", "沿", "顺着", "到"}
PREP_DAT = {"给", "对", "对于", "跟", "同", "和", "与", "替", "为"}
PREP_OTHER = {"用", "以", "按", "按照", "根据", "通过", "关于", "除了", "连", "由", "自从", "至于"}
# N4 体标记
ASP_WORDS = {"着", "了", "过", "起来", "下去", "下来", "上来"}
# N5 结构助词
DE_N = {"的"}
DE_ADV = {"地"}
DE_COMP = {"得"}
# N8 连词语义类
CONJ_CAUSE = {"因为", "所以", "由于", "因此", "因而", "以致", "既然", "故"}
CONJ_CONTRAST = {"但是", "但", "可是", "然而", "不过", "却", "虽然", "尽管", "反而", "偏偏"}
CONJ_COND = {"如果", "要是", "假如", "假使", "除非", "只要", "只有", "无论", "不管", "即使", "就算", "哪怕"}
CONJ_ADD = {"而且", "并且", "并", "和", "与", "以及", "何况", "况且", "甚至", "也", "还"}
CONJ_TEMP = {"然后", "接着", "随后", "后来", "最后", "于是", "终于", "同时", "此后", "之后"}
CONJ_LIMIT = {"只是", "不过", "仅", "只是说"}
# N7 趋向补语
DIR_WORDS = {"起来", "下来", "下去", "上来", "出去", "进去", "回来", "过来", "过去", "开来"}
DIR_CHARS = set("上下开起进出回过")
# N10 言语动词
SPEECH_VERBS = {"说", "道", "问", "答", "喊", "叫", "嚷", "嘟囔", "低声说", "回答", "反问", "笑道", "叹道", "念道", "写道"}
# 语气词
PART_WORDS = {"呢", "吧", "啊", "呀", "吗", "嘛", "罢了", "而已", "么", "啦", "哦", "嗯"}
# 存现/判断
EXIST_VERBS = {"有", "存在", "出现", "浮现", "站着", "坐着", "躺着", "剩下", "弥漫", "充斥"}
JUDGE_COPULA = {"是", "正是", "就是", "并非", "不是", "算", "算是"}
# 常见「把/被」误并词（不得拆分）
MERGE_EXCEPT = {"把握", "把守", "把手", "把柄", "把戏", "把式", "把关", "把持",
                "被动", "被告", "被单", "被子", "被褥", "被害", "将就", "将来",
                "将军", "将近", "将要", "将士", "叫喊", "叫嚣", "让开"}

PLACE_CHARS = set("上下里外前后中内边旁间处")
VERB_FIRST = set("推拉关打拿放走跑坐站看听读写说问答想记抬低回摇点伸出提扔握转翻揉摸索捏扯拽抱背扛捧端拖拔插按拍敲踢跳蹲躺趴跪踩追赶躲抖颤摸擦扫洗抱抬")
DIR_CHARS_VERB = set("上下开起进出回过掉住走开")

_VERB_LEXICON: set[str] | None = None


def _verb_lexicon() -> set[str]:
    """加载常用叙事动词表（可扩展的数据资产）。"""
    global _VERB_LEXICON
    if _VERB_LEXICON is None:
        from pathlib import Path

        path = Path(__file__).with_name("data") / "verbs_zh.txt"
        words: set[str] = set()
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                words.update(line.split())
        except OSError:
            words = set()
        _VERB_LEXICON = words
    return _VERB_LEXICON

# 功能类 → 是否内容槽（匹配时作通配）
CONTENT_CLASSES = {"N", "V", "A", "NAME", "IDIOM", "QUANT", "M", "CL", "TIME", "LOC", "ONO"}
# 骨架锚点（必须精确匹配）
ANCHOR_CLASSES = {"PRON", "NEG", "ADV_LIM", "ADV_DEG", "ADV_TIME", "ADV_MOD", "ADV_FREQ",
                  "ADV", "PREP_BA", "PREP_BEI", "PREP_LOC", "PREP_DAT", "PREP_OTHER",
                  "CONJ_CAUSE", "CONJ_CONTRAST", "CONJ_COND", "CONJ_ADD", "CONJ_TEMP", "CONJ_LIMIT",
                  "DE_N", "DE_ADV", "DE_COMP", "ASP", "PART", "DIR", "SPEECH", "P", "X", "INTJ"}

_ADV_SUB = [
    (NEG_WORDS, "NEG"),
    (LIM_WORDS, "LIM"),
    (DEG_WORDS, "DEG"),
    (TIME_ADV, "TIME"),
    (MOD_WORDS, "MOD"),
    (FREQ_ADV, "FREQ"),
]
_PREP_SUB = [
    (PREP_BA, "BA"),
    (PREP_BEI, "BEI"),
    (PREP_LOC, "LOC"),
    (PREP_DAT, "DAT"),
    (PREP_OTHER, "OTHER"),
]
_CONJ_SUB = [
    (CONJ_CAUSE, "CAUSE"),
    (CONJ_CONTRAST, "CONTRAST"),
    (CONJ_COND, "COND"),
    (CONJ_ADD, "ADD"),
    (CONJ_TEMP, "TEMP"),
    (CONJ_LIMIT, "LIMIT"),
]

# jieba flag → 基础类
_JIEBA_MAP = {
    "r": "PRON", "rr": "PRON", "rz": "PRON", "ry": "PRON",
    "nr": "NAME", "nrfg": "NAME", "nrt": "NAME", "nrf": "NAME", "PER": "NAME",
    "n": "N", "ng": "N", "nz": "N", "ns": "LOC", "nt": "N", "an": "N", "vn": "V",
    "v": "V", "vg": "V", "vd": "V", "vi": "V", "vn_": "V",
    "a": "A", "ad": "A", "ag": "A",
    "d": "ADV", "df": "ADV", "dg": "ADV",
    "p": "PREP", "pba": "PREP", "pbei": "PREP",
    "c": "CONJ", "cc": "CONJ",
    "m": "NUM", "mq": "QUANT", "q": "CL",
    "f": "LOC", "s": "LOC", "t": "TIME", "tg": "TIME",
    "i": "IDIOM", "l": "IDIOM",
    "u": "U", "uj": "U", "ud": "U", "ug": "U", "ul": "U", "uv": "U", "uz": "U", "udeng": "U",
    "y": "PART", "e": "INTJ", "o": "ONO", "x": "X", "w": "P", "z": "ADV", "zg": "ADV",
}
# spaCy UD POS → 基础类
_UD_MAP = {
    "PRON": "PRON", "PROPN": "NAME", "NOUN": "N", "VERB": "V", "AUX": "V", "ADJ": "A",
    "ADV": "ADV", "ADP": "PREP", "CCONJ": "CONJ", "SCONJ": "CONJ", "PART": "U",
    "NUM": "NUM", "DET": "X", "INTJ": "INTJ", "X": "X", "SYM": "X", "PUNCT": "P",
    "SPACE": "X", "SYM_": "X",
}
# UD 依存关系 → 功能细化（当后端给依存时优先用，覆盖 POS 猜法）
_DEP_NEG = {"neg"}
_DEP_LIM = {"advmod"}
_DEP_ASP = {"aux:asp", "aux", "aux:ba", "aux:bei"}
_DEP_CONJ = {"cc", "conj", "mark"}
_DEP_DE = {"case", "mark:rel"}


@dataclass
class NormRule:
    rule_id: str
    description: str


def _is_cjk_word(word: str) -> bool:
    return bool(word) and all("\u3400" <= c <= "\u9fff" for c in word)


def _lookup_sub(word: str, table: list[tuple[set[str], str]]) -> str | None:
    for words, sub in table:
        if word in words:
            return sub
    return None


def normalize_token(tok: Token, *, prev: Token | None = None, next_: Token | None = None,
                    has_dep: bool = False) -> tuple[str, str]:
    """返回 (norm, sub)。"""

    w, flag = tok.word, tok.pos

    # 标点
    if tok.is_punct:
        return "P", ""

    # ---- 词表优先（很多功能词在 jieba 里被误标成 v/n/s）
    if w in NEG_WORDS:
        return "ADV", "NEG"
    if w in ASP_WORDS and w in {"着", "了", "过"}:
        return "ASP", ""
    if w in DE_N:
        return "DE", "N"
    if w in DE_ADV:
        return "DE", "ADV"
    if w in DE_COMP:
        return "DE", "COMP"
    if w in PART_WORDS:
        return "PART", ""
    if w in PREP_BA:
        return "PREP", "BA"
    if w in SPEECH_VERBS:
        # N10：只有「说/道/问/答 + 引语」才算对话标记；「回答」这类若无引语按普通动词处理，
        # 否则「她没有回答」与「他没有解释」会被误判成不同结构（见 docs/syntax_fingerprint.md §1.3）
        if next_ is not None and (next_.word[:1] in "「『\"“" or next_.pos in ("w", "PUNCT")):
            return "SPEECH", ""
        return "V", ""

    base = _JIEBA_MAP.get(flag) or _UD_MAP.get(flag) or "X"

    # ---- 分词器纠偏（jieba 常把动词标成名词/处所词，见 docs/algorithm_design.md §1.5）
    if base in ("N", "LOC", "A") and len(w) <= 3:
        if w in _verb_lexicon():
            return "V", ""
        if flag == "s":
            if len(w) == 1:
                return ("LOC" if w in PLACE_CHARS else "N"), ""
            if w[-1] in DIR_CHARS_VERB and (w[0] in VERB_FIRST or (next_ is not None and next_.word in ASP_WORDS)):
                return "V", ""

    # ---- 依存信息优先（spaCy 时更准）
    dep = tok.deprel or ""
    if has_dep and dep:
        if dep in _DEP_NEG:
            return "ADV", "NEG"
        if dep in ("aux:ba",):
            return "PREP", "BA"
        if dep in ("aux:bei",):
            return "PREP", "BEI"
        if dep in ("aux:asp",):
            return "ASP", ""
        if dep in ("case",) and w in DE_N:
            return "DE", "N"
        if dep in ("mark",) and w in DE_COMP:
            return "DE", "COMP"

    # ---- 介词细化
    if base == "PREP" or w in PREP_LOC or w in PREP_DAT or w in PREP_OTHER or w in PREP_BEI:
        sub = _lookup_sub(w, _PREP_SUB)
        if sub:
            return "PREP", sub
        if base == "PREP":
            return "PREP", "OTHER"

    # ---- 副词细化
    if base == "ADV":
        sub = _lookup_sub(w, _ADV_SUB)
        if sub:
            return "ADV", sub
        if w in DIR_WORDS:
            return "DIR", ""
        return "ADV", ""

    # ---- 连词细化
    if base == "CONJ":
        sub = _lookup_sub(w, _CONJ_SUB)
        return "CONJ", (sub or "ADD")

    # ---- 助词 / 体标记 / 语气
    if base == "U" or flag in ("u", "uj", "ul", "uv", "uz", "ug", "ud"):
        if w in ASP_WORDS:
            return "ASP", ""
        if w in DE_N:
            return "DE", "N"
        if w in DE_ADV:
            return "DE", "ADV"
        if w in DE_COMP:
            return "DE", "COMP"
        if w in PART_WORDS:
            return "PART", ""
        return "PART", ""

    # ---- 动词特别处理：判断/存现/趋向/兼语标志
    if base == "V":
        if w in DIR_WORDS and _is_directional_complement(tok, prev):
            return "DIR", ""
        return "V", ""

    # ---- 名词类：四字格（N9）
    if base in ("N", "A", "IDIOM") and flag == "i":
        return "IDIOM", ""
    if base == "N" and len(w) == 4 and _is_cjk_word(w) and flag in ("n", "nz", "a"):
        # 仅当词形符合「成语」外观（四字、全汉字、非常用双字复合）时才标 IDIOM，低置信
        return "N", ""

    # ---- 数词量词合并（N6）由 spec 层做，这里只给基础类
    if base == "NUM":
        return "NUM", ""
    if base == "CL":
        return "CL", ""
    if base == "QUANT":
        return "QUANT", ""
    if base == "LOC":
        return "LOC", ""
    if base == "TIME":
        return "TIME", ""
    if base == "ONO":
        return "ONO", ""
    if base == "INTJ":
        return "INTJ", ""
    if base == "P":
        return "P", ""
    if base in ("N", "V", "A", "NAME", "PRON", "IDIOM"):
        return base, ""
    return "X", ""


def _is_directional_complement(tok: Token, prev: Token | None) -> bool:
    """趋向补语判定：位于动词之后，且不是句首。"""
    if prev is None:
        return False
    return prev.pos in ("v", "VERB", "AUX") or bool(getattr(prev, "norm", "").startswith("V"))


def render(norm: str, sub: str) -> str:
    """骨架串里的可读符号。"""
    if norm == "P":
        return sub or "P"
    if norm in ("ADV", "PREP", "CONJ", "DE") and sub:
        return f"{norm}_{sub}"
    if norm == "ASP":
        return "ASP"
    return norm


def apply(tokens: list[Token], *, has_dep: bool = False) -> list[Token]:
    """就地填 norm/sub，并做 N6 数量短语折叠、N10 引语标注。"""
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else None
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        norm, sub = normalize_token(tok, prev=prev, next_=nxt, has_dep=has_dep)
        tok.norm, tok.sub = norm, sub
    # 第二遍：「只是/不过」的副词 vs 连词消歧（依赖邻词归一结果）
    for i, tok in enumerate(tokens):
        if tok.word not in ("只是", "不过") or not tok.norm.startswith("CONJ"):
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is None:
            continue
        if nxt.norm in ("V", "A", "ADV", "ASP", "DIR", "NEG") or nxt.word in NEG_WORDS:
            tok.norm, tok.sub = "ADV", "LIM"
    # 第三遍：「没有/没」在无后续动词、后接名词或标点时本身作谓语动词
    for i, tok in enumerate(tokens):
        if tok.norm != "ADV" or tok.sub != "NEG":
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is None or nxt.is_punct or nxt.norm in ("N", "PRON", "QUANT", "NUM", "CL", "LOC", "TIME", "NAME"):
            tok.norm, tok.sub = "V", ""
    _merge_quantities(tokens)
    return tokens


def _merge_quantities(tokens: list[Token]) -> None:
    """N6：NUM+CL → QUANT（把「一抹」「一缕」折叠成一个槽，避免骨架被量词切碎）。"""
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if a.norm == "NUM" and b.norm == "CL":
            a.norm, a.sub = "QUANT", ""
            b.norm, b.sub = "QUANT_MERGE", ""
    tokens[:] = [t for t in tokens if t.norm != "QUANT_MERGE"]
    for i, t in enumerate(tokens):
        t.index = i


def skeleton(tokens: list[Token]) -> list[str]:
    """L1：小句骨架串（保留线性语序）。"""
    return [render(t.norm, t.sub) for t in tokens]


def skeleton_signature(tokens: list[Token]) -> str:
    return " ".join(skeleton(tokens))


def to_pattern(skel: list[str]) -> tuple[str, ...]:
    """把骨架串转成带通配的匹配模式：内容槽 → `*`，功能锚点保留。"""
    return tuple("*" if s in CONTENT_CLASSES or s in ("QUANT", "NUM", "CL") else s for s in skel)


def is_anchor(sym: str) -> bool:
    return sym in ANCHOR_CLASSES
