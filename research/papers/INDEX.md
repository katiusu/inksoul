# papers/ 下载索引（2026-11-05 批次）

**结果**：14 篇中 **9 篇拿到全文**（8 个 PDF + 1 个全文 Markdown + 1 个 XML 全文），**5 篇无免费全文**。
取用顺序：官方 OA 发表版 → 作者预印本；付费墙未做任何绕过。

| # | 篇目 | 本地文件 | 来源 | 说明 |
|---|---|---|---|---|
| 1 | O'Sullivan 2025, Stylometric comparisons… (HSSC 12) | 01_osullivan_2025_stylometric.pdf | nature.com 官方 PDF | 期刊 OA，即发表版 |
| 2 | Yang 等 2024, Thematic choices & progression (System) | — | — | Elsevier 付费墙，S2 判 CLOSED，无 OA 副本 |
| 3 | Sourati 等 2026, Shrinking landscape of linguistic diversity (Nat Hum Behav) | 03_sourati_2026_diversity.pdf | arXiv:2502.11266 | 作者预印本（正式版付费） |
| 4 | Hao 等 2024, Syntactic complexity → Chinese L2 quality (Assessing Writing) | — | — | Elsevier 付费墙，无 OA 副本 |
| 5 | Liu, Li, Xiao 2024, Measuring linguistic complexity in Chinese (HSSC 11) | 05_liu_2024_chinese_complexity.pdf | nature.com 官方 PDF | 期刊 OA，即发表版 |
| 6 | Tudino & Qin 2024, Corpus-driven analysis… (Lingua) | — | — | 仅 SSRN 4891634 预印本，SSRN 被 Cloudflare 拦，未取到 |
| 7 | Xu 等 2025, Echoes in AI (PNAS 122(35)) | 07_xu_2025_plot_diversity.pdf + 07b_pnas_fulltext.xml | arXiv:2501.00273 / Europe PMC | 预印本 PDF + PMC 全文 XML，正文可引用 |
| 8 | Li & Zhang 2025, Weibo AIGT detection (CCL 2025) | 08_li_zhang_2025_weibo.pdf | ACL Anthology | 官方开放获取 |
| 9 | Yao, Kang, McCosker 2025, Missing the human touch? (Translation Spaces) | 09_yao_2025_translation_spaces.pdf | arXiv:2506.13013 | 作者预印本（正式版付费） |
| 10 | SSRN abstract_id=7251580 | — | — | Cloudflare 全拦（直连 / r.jina.ai / 短链），题录亦未知 |
| 11 | Emara 2025, ChatGPT vs nonnative story adaptations (Smart Learn Environ) | 11_emara_2025_fulltext.md | SpringerOpen 全文（经文本代理） | 期刊 OA；PDF 端点被 Cloudflare 拦，存的是全文正文 |
| 12 | Sukying & Barrot 2025, Syntactic complexity of AI texts (CCC 77(1)) | — | — | NCTE 订阅墙，页面只有摘要 |
| 13 | 2026 ACL, ChangAn | 13_acl2026_changan.pdf | ACL Anthology | 官方开放获取 |
| 14 | Kendro, Maloney, Jarvis 2026, Human-like lexical diversity? (IJAL) | 14_kendro_2026_lexdiv.pdf | arXiv:2508.00086 | 作者预印本（Wiley 版 BRONZE，直链 403） |

## 复核方式

- 每个 PDF 校验 %PDF 头与 %%EOF 尾；返回 HTML 的假文件（Springer counter、PNAS 直链、SSRN）已删除。
- OA 状态取自 OpenAlex open_access / best_oa_location 与 Semantic Scholar openAccessPdf；两者对 #2 #4 一致判 CLOSED。
- 未采用：Unpaywall（要求真实邮箱，示例邮箱 422）、Sci-Hub 类镜像。

## OpenAlex 可用性复核（2026-11-05，经 api.openalex.org works/doi: 查询）

判定依据：open_access.is_oa / oa_status / best_oa_location；原始响应见 openalex_check_2026-11-05.json。

| # | DOI | is_oa | oa_status | OpenAlex 给出的 PDF / OA 地址 | 本次是否拿到 |
|---|---|---|---|---|---|
| 1 | 10.1057/s41599-025-05986-3 | true | gold | nature.com/articles/s41599-025-05986-3.pdf | 已下 |
| 2 | 10.1016/j.system.2024.103494 | false | **closed** | 无 | 无任何 OA 副本 |
| 3 | 10.1038/s41562-026-02550-0 | true | green | arxiv.org/pdf/2502.11266 | 已下（预印本） |
| 4 | 10.1016/j.asw.2024.100847 | false | **closed** | 无 | 无任何 OA 副本 |
| 5 | 10.1057/s41599-024-03510-7 | true | gold | best_oa_location 无 pdf_url，落地页为 doi.org | 已下（nature 直链） |
| 6 | 10.1016/j.lingua.2024.103838 | true | green | dx.doi.org/10.2139/ssrn.4891634（SSRN 预印本） | 未取到（SSRN 反爬） |
| 7 | 10.1073/pnas.2504966122 | true | hybrid | arxiv.org/pdf/2501.00273 | 已下（预印本 + PMC XML） |
| 8 | 10.18653/v1/2025.ccl-1.64 | — | OpenAlex 未收录（DOI 404） | — | 已下（ACL Anthology 直链） |
| 9 | 10.1075/ts.24043.yao | true | green | arxiv.org/pdf/2506.13013 | 已下（预印本） |
| 10 | 无 DOI（SSRN 7251580） | — | 无法查询 | — | 题录未知，OpenAlex 无从入手 |
| 11 | 10.1186/s40561-025-00388-z | true | gold | slejournal.springeropen.com/counter/pdf/… | 已下（经文本代理取全文正文） |
| 12 | 无 DOI（ERIC EJ1492719） | — | 无法查询 | — | 仅 ERIC 摘要，NCTE 订阅墙 |
| 13 | 10.18653/v1/2026.acl-long.245 | true | hybrid | aclanthology.org/2026.acl-long.245.pdf | 已下 |
| 14 | 10.1111/ijal.70115 | true | bronze | onlinelibrary.wiley.com/doi/pdfdirect/… | 已下（arXiv 预印本） |

**结论**：12 个有 DOI 的条目中 9 个 OA、3 个 closed。#2 #4 属 Elsevier，OpenAlex 明确无 OA 副本，不是"我们没找到"；#6 唯一的 OA 是 SSRN 预印本，卡在反爬而非授权。
## 优先阅读六篇（2026-11-06 下载）

| 文件 | 论文 | 来源版本 | 页/大小 |
|---|---|---|---|
| 20_doshi_2024_diversity.pdf | Doshi & Hauser 2024, *Generative AI enhances creativity but reduces the diversity of novel content*, Sci Adv 10, DOI 10.1126/sciadv.adn5290 | arXiv:2312.00506（science.org 直链 403、PMC PDF 返 HTML） | 77 页 / 9.2 MB |
| 21_reinhart_2025_style.pdf | Reinhart 等 2025, *Do LLMs write like humans?*, PNAS, DOI 10.1073/pnas.2422455122 | arXiv:2410.16107（Accepted manuscript 版，首页标 DRAFT） | 7 页 / 2.5 MB |
| 22_munozortiz_2024_dependency.pdf | Muñoz-Ortiz, Gómez-Rodríguez, Vilares 2024, *Contrasting Linguistic Patterns in Human and LLM-Generated News Text*, AI Review 57:265, DOI 10.1007/s10462-024-10903-2 | arXiv:2308.09067（实为 Springer 排版正刊版；PMC/ResearchSquare 均被拦） | 28 页 / 2.5 MB |
| 23_herbold_2023_essays.pdf | Herbold 等 2023, *A large-scale comparison of human-written versus ChatGPT-generated essays*, Sci Rep 13:18617, DOI 10.1038/s41598-023-45644-9 | nature.com 直链（正刊版） | 11 页 / 1.1 MB |
| 24_brysbaert_2014_concreteness.pdf | Brysbaert, Warriner, Kuperman 2014, *Concreteness ratings for 40 thousand generally known English word lemmas*, BRM, DOI 10.3758/s13428-013-0403-5 | link.springer.com content/pdf（bronze，正刊版） | 8 页 / 206 KB |
| 25_chakrabarty_2024_art.pdf | Chakrabarty 等 2024, *Art or Artifice? Large Language Models and the False Promise of Creativity*, CHI, DOI 10.1145/3613904.3642731 | arXiv:2309.14556（正刊版 ACM DL 未开 OA） | 34 页 / 2.9 MB |

版本提示：#20 #21 #25 是预印本，#22 #23 #24 是出版社排版正刊版。引用页码时注意 #20（arXiv 77 页 vs Sci Adv 正刊页数不同）。

**补充检索**（同日）：Semantic Scholar 与 Crossref 对 #2 #4 #6 均无摘要正文（Elsevier 不开放 abstract 字段）；ERIC Open API 取到 #12 官方摘要（见题录笔记）。
