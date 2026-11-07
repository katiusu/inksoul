# InkSoul 中文 NLP 工具实测（aarch64 PRoot / Python 3.12）

> 证据口径：凡标「实测」的条目都贴了本机真实运行的命令与输出行；标「文档」的只有官方文档/源码原文，没有跑通；标「未验证」的明确说明卡在哪一步。
> 实验时间：2026-10-31，本机 Android 真机内 Ubuntu PRoot。临时脚本在 `/tmp/inksoul/`，未写入仓库。

## 环境

```
$ uname -m
aarch64
$ python3 -VV
Python 3.12.3
$ python3 -m pip --version
pip 26.2.1 from /usr/lib/python3/dist-packages/pip (python 3.12)
$ df -h / | tail -1
/dev/block/dm-45  107G   91G   16G  86% /
```

- **PEP 668 生效**：默认 `pip install` 会被拒，必须加 `--break-system-packages`（实测 `pip install --no-input requests` 原文：`error: externally-managed-environment` / `× This environment is externally managed`）。
- `/sdcard` 是 sdcardfs，本仓的文件落盘用 `bash` + heredoc（`write` 工具会报 `EINVAL: 无法原子发布文件`）。
- 关键卡点：**torch**。`torch 2.15.0` 在 PyPI 有 `torch-2.15.0-cp312-cp312-manylinux_2_28_aarch64.whl`（实测 `pip index` 可见），体积 **486 MB**；本机从 PyPI 直连反复被重置（`curl: (18) Transferred a partial file`），换阿里云镜像后 6 分钟只下到 140 MB（约 0.3–0.4 MB/s）→ 按 lead 要求冻结，撤销下载并清理残留（`df` 前后一致，16G 可用未变）。

## A 分词 / 词性

### jieba（实测可用）
```
$ python3 -c "import jieba; print(jieba.__version__)"
0.42.1
$ python3 -c "import jieba, jieba.posseg as pseg; print('/'.join(jieba.cut('她没有回答，只是看着窗外。', HMM=True)))"
她/没有/回答/，/只是/看着/窗外/。
$ python3 -c "import jieba.posseg as pseg; [print(f'{w.word}/{w.flag}') for w in pseg.cut('她把门轻轻带上')]"
她/r
把/p
门/n
轻轻/d
带/v
上/f
```
- 自定义词典：`jieba.add_word('轻轻带上')` 后再切，`轻轻带上` 被整体保留（实测）。
- 速度：`202862 tokens/s`（实测，jieba 自带 benchmark 口径，非本机严格计时）。
- 结论：分词/POS 可用，但**不带依存**，`flag` 是 jieba 自己的词性集（r/p/n/d/v/f…），不能直接当 UD 用。

### pkuseg（不可用）
- `pip install pkuseg` 解析到 0.0.25，PyPI 上只有 cp35–cp37 的 x86_64 / win / mac 轮子（实测 `pip index versions` 列出的文件名），aarch64+3.12 无轮子 → 源码构建失败，报错原文：
  ```
  ERROR: Failed to build 'pkuseg' when getting requirements to build wheel
  ```
- 替代分支 `spacy-pkuseg` 有 `cp312` aarch64 轮子，**实测能装上**（1.0.2）；但其分词质量本机未评测（未做任务级对比）。

### LAC / 百度（不可用）
- `lac 2.1.2` 只有 sdist（`LAC-2.1.2.tar.gz`，64.8 MB），依赖 `paddlepaddle`；`paddlepaddle 3.3.1` 的 PyPI 文件列表里 **linux aarch64 轮子为空**（实测按 `cp312 + aarch64`、以及任意 aarch64 两次过滤均为 `[]`）。
- 结论：aarch64 上装不起来，**不可用**。

### HanLP 2.x（安装可行，跑不通）
- `pip install hanlp` 能完成依赖解析（无 TensorFlow 依赖，`2.1.7`），但硬依赖 `torch>=1.6.0`；torch 未装成 → `import hanlp` 报 `ModuleNotFoundError: No module named 'torch'`。
- 模型（文档，未下载）：`CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH` 对应
  `https://file.hankcs.com/hanlp/mtl/close_tok_pos_ner_srl_dep_sdp_con_electra_small_20210111_124159.zip`
- 许可证：仓库 `LICENSE` 首行为 `Apache License Version 2.0`（实测读取）。

## B 依存句法（本机状态表）

| 工具 | 能否在本机跑 | 依存标签体系 | 是否给 head 索引 | 速度 | 模型大小 | 许可证 |
|---|---|---|---|---|---|---|
| **spacy 3.8.18 + zh_core_web_sm 3.8.0** | ✅ **实测跑通** | UD（`nsubj/dobj/conj/ccomp/advmod/neg/aux:asp/case/nmod:prep/punct/ROOT`…） | ✅ `token.head.i`（整数下标）+ `dep_` | 实测 **214.6 句/秒**（短句，单核） | 轮子 48.5 MB | MIT（spaCy）/ MIT（模型） |
| **LTP 4.2.14** | ❌ 未跑通（卡 torch） | 自研 **14 标签**：`ADV ATT CMP COO DBL FOB HED IOB LAD POB RAD SBV VOB WP`（源码 `python/core/data/conllu/vocabs/deprel.txt` 原文） | ✅ 文档示例 `result.dep` 含 head/deprel（CoNLL-U 风格） | 未实测 | 未实测（`LTP/small` 未下载） | Apache-2.0 |
| **HanLP 2.1.7** | ❌ 未跑通（卡 torch） | UD/CoNLL（官方 pretrained MTL 模型名里 `DEP`/`SDP`/`CON` 分别对应依存/语义依存/成分） | 文档：CoNLL 输出含 head 列 | 未实测 | MTL-ELECTRA-small zip 未下载（官方文档标注该组模型为百 MB 级） | Apache-2.0 |
| **Stanza 1.15.0** | ❌ 未跑通（`stanza` 元数据要求 `torch>=1.13`） | UD 中文（`nsubj/obj/advmod/conj/ccomp/punct/ROOT`…） | UD `Token`/`Word` 有 `head`/`deprel` | 未实测 | 未实测 | Apache-2.0 |

**跑不通的原话**：`python3 -c "import ltp"` / `import hanlp` / `import stanza` 三者在本机均因缺 torch 失败，且 torch 的 aarch64 轮子在本机下载不可完成（见「环境」）。**不是库本身不支持 aarch64**——三者的纯 Python 依赖（`ltp-core`、`ltp-extension`、`transformers`）都能正常解析。

## C 结构相似度与 demo（实测输出）

可装性（实测）：`apted` ✅、`zss 1.2.0` ✅、`networkx 3.7` ✅（`weisfeiler_lehman_graph_hash` 可用）。

`/tmp/inksoul/dep_demo.py`：spacy 解析 → 以 `(head.dep_, deprel)` 建树 → networkx `weisfeiler_lehman_graph_hash` 结构哈希 + 子树直方图余弦 + APTED 编辑距离。

```
A) 每句依存边集合（head --deprel--> child）与 WL 结构哈希

【她没有回答，只是看着窗外。】 len=13 tokens=9
  edges: 回答-ROOT->回答 | 回答-conj->看 | 回答-neg->没有 | 回答-nsubj->她 | 回答-punct->。 | 回答-punct->， | 看-advmod->只是 | 看-aux:asp->着 | 看-dobj->窗外
  WL(struct)= 7e0130ced9e4fce654d90cf7be46f421

【他没有解释，只是低头整理衣袖。】 len=15 tokens=9
  edges: 整理-advmod->只是 | 整理-compound:vc->低头 | 整理-dobj->衣袖 | 解释-ROOT->解释 | 解释-conj->整理 | 解释-neg->没有 | 解释-nsubj->他 | 解释-punct->。 | 解释-punct->，
  WL(struct)= cc9f48ddf7962521152fa4b554bb135f

【雨停了。】 len=4 tokens=4
  edges: 停-ROOT->停 | 停-aux:asp->了 | 停-nsubj->雨 | 停-punct->。
  WL(struct)= c111ddf8ce6b02174caded3d26da8d49

【她把门轻轻带上，回头看了一眼空荡的客厅。】 len=20 tokens=14
  edges: 客厅-amod->空荡 | 看-ROOT->看 | 看-aux:asp->了 | 看-aux:ba->把 | 看-compound:vc->回头 | 看-dep->轻带 | 看-dobj->客厅 | 看-nsubj->她 | 看-punct->。 | 看-punct->， | 空荡-advmod->一眼 | 空荡-case->的 | 轻带-case->上 | 轻带-nmod:assmod->门轻
  WL(struct)= 8a37765d5eab9310848bc103e4ebdb1b

【天色暗下来的时候，院子里的灯还没亮。】 len=18 tokens=13
  edges: 下来-mark->的 | 下来-nsubj->天色暗 | 亮-ROOT->亮 | 亮-advmod->还 | 亮-neg->没 | 亮-nmod:topic->时候 | 亮-nsubj->灯 | 亮-punct->。 | 亮-punct->， | 时候-acl->下来 | 灯-nmod->院子 | 院子-case->的 | 院子-case->里
  WL(struct)= d458418faa53970a4d30b6fa012db0b5

B) WL 哈希两两是否相等（1=结构完全同构）
   1 0 0 0 0
   0 1 0 0 0
   0 0 1 0 0
   0 0 0 1 0
   0 0 0 0 1

C) WL 子树直方图余弦相似度
       句1    句2    句3    句4    句5
  句1 1.000 0.568 0.302 0.260 0.252
  句2 0.568 1.000 0.264 0.260 0.252
  句3 0.302 0.264 1.000 0.277 0.209
  句4 0.260 0.260 0.277 1.000 0.235
  句5 0.252 0.252 0.209 0.235 1.000

D) APTED 树编辑距离（节点标签=deprel）
       句1    句2    句3    句4    句5
  句1     0     1     5     9    10
  句2     1     0     6    10    10
```

**解读（这是语法指纹方案的关键证据）**
1. 精确 WL 哈希对**任何两句都不相等**——句子长度/标点节点数不同就必然不等，不宜直接当"同结构"判据。
2. 归一化后的信号**能分开**：句1/句2（同构式「否定+只是+V」）WL 余弦 **0.568**，与其余句 0.25–0.31；APTED 距离 **1**，其余 5–13。→ 这个组合可用作指纹的连续相似度分量。
3. 但 spacy 中文分词有硬伤且会污染指纹：句4 把「门轻轻带上」切成 `门轻/带/上`（边里出现 `轻带-nmod:assmod->门轻`），句1 把「看着」切成 `看/着`、句5 把「天色暗下来」切成 `天色暗`。**换分词器（jieba / LTP cws）会改变树形**，指纹前必须先固定并验证分词层。
4. 已试归一化变体（去 punct/aux/advmod/neg/case/mark 后重算）：句1 剩 4 节点、句2 剩 5 节点，仍不同构，余弦矩阵全 0 → 粗暴删边会把相似性一起抹掉，归一化要按「保留子树骨架」设计而不是删节点。

## D 语料

| 资源 | 实测可达性 |
|---|---|
| 中文维基 dump | ✅ `dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-pages-articles.xml.bz2` 存在（HTTP 可达） |
| 古登堡中文 | ❌ `gutendex.com/books?languages=zh` 返回 **403**（Cloudflare 拦截） |
| chinese-poetry（GitHub） | ✅ `garychowcmu/daizhigev20` 200、`chinese-poetry` 200（古文/诗词，非现代小说） |
| `wangzichaochaochao/Chinese-Novel-Dataset` | ❌ 404（仓库已不存在） |

结论：**现成的"现代中文小说/散文"公开语料本机没有一键可用源**；能核实可用的是中文维基 dump（体量大、需自行抽取正文）与古文类 GitHub 仓库。THUCNews 按题意不是文学，不计入。

## E 成本估算

实测基准：spacy dep **214.6 句/秒**（单核，短句）。以下为**外推估算**，非实测：
- 1 万字小说 ≈ 700 句（按平均 14 字/句）→ 依存解析 **约 3–4 秒**。
- 指纹：WL 哈希每句 O(n) ≈ 毫秒级，700 句 < 1 秒；两两比较 700²/2 ≈ 24.5 万对，若每对 APTED ≈ 1 ms → **约 4 分钟**（这是主要成本，建议先按段落/章节分块比较，只对候选对跑 APTED）。
- LTP/HanLP/Stanza 的 to-ken 速度**未实测**（torch 未装成），不给数字；按它们同为 transformer 编码器推断会在 spacy 之下，需要真机跑通后再测。

## 结论：推荐栈与理由 / 不可用项

- **生产栈（当前唯一可跑通）**：`jieba`（分词，可控可扩词典）+ `spacy zh_core_web_sm`（依存，UD 标签含 head 索引）+ `networkx` WL 子树直方图余弦 + `apted` 树编辑距离。理由：全部实测跑通、纯 aarch64 轮子、总模型 48.5 MB、单核 214 句/秒，足够 1 万字级分析。
- **想要更贴中文的标签体系（SBV/VOB/ATT…）**：首选 **LTP 4**（14 标签、`HED` 单根、Apache-2.0、`ltp-core`/`ltp-extension` 有 aarch64 轮子），但必须先解决 torch 486 MB 的下载问题——建议在 PC 侧下好 `torch-2.15.0-cp312-cp312-manylinux_2_28_aarch64.whl` 再拷入，本机直连不可靠。
- **不可用**：原版 `pkuseg`（无 cp312/aarch64 轮子且源码构建失败）、`LAC`（依赖 paddlepaddle，无 aarch64 轮子）、古登堡中文接口（403）。
- **未跑通、只有文档**：HanLP 2.1.7 / Stanza 1.15.0（同卡 torch；模型未下载）。

### 关键问题的答案：多小句流水句是单根树还是多小句结构？

**单根树。** 实测（spacy，`他推开门，走进屋里，坐在椅子上，看着桌面。`）：

```
0	他	PRON	nsubj	head=1(推)
1	推	VERB	ROOT	head=1(推)
2	开门	VERB	ccomp	head=1(推)
3	，	PUNCT	punct	head=1(推)
4	走进	VERB	conj	head=1(推)
5	屋里	NOUN	dobj	head=4(走进)
7	坐	VERB	conj	head=4(走进)
9	椅子	NOUN	nmod:prep	head=7(坐)
12	看	VERB	conj	head=1(推)
14	桌面	NOUN	dobj	head=12(看)
15	。	PUNCT	punct	head=1(推)
ROOT nodes: ['推']
```
四个小句全部挂到**唯一根「推」**上，用 `conj/ccomp + punct` 表示并列，没有"每小句一棵树"的输出。LTP 的 `HED`（head）设计与之同义（源码 deprel 词表里 `HED` 是唯一句根标签）、HanLP/Stanza 的 CoNLL-U 也规定单根（`head=0` 唯一）——**这一点是文档/源码证据，未在本机跑通验证**。
→ 对 InkSoul 的直接含义：**小句级句法指纹不能指望解析器直接给**，必须自己在指纹层做小句切分（按 `punct` 边 + 连词/`conj` 链切段），每段单独取子树再哈希；否则「四小句」与「一大句」在结构上被合并，指纹会丢层级。
