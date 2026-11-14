/**
 * dsh-inksoul —— InkSoul 的主产品形态：装进 DeepSeek Harness 的中文写作插件。
 *
 * 模型通过这里拿到五个一等工具（诊断 / 同质对比 / 文风闸门 / 生成闭环 / 自检），
 * 不需要 pip 安装、不需要 PATH 里有 inksoul：引擎源码随包分发在 python/inksoul，
 * 每次调用用 PYTHONPATH 指过去。插件本身就是产品，CLI 只是同一引擎的另一个入口。
 */
import { execFile } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join, delimiter } from 'node:path'
import z from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'

const name = 'inksoul'
const inject = ['tools', 'systemPrompt']
const SECTION_NAME = 'inksoul:policy'

/** 包内自带的 Python 源码目录（纯 Python、零第三方依赖；jieba 缺失时降级但不崩）。 */
const PY_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', 'python')

const Config = z.object({
  enabled: z.boolean().default(true),
  python: z.string().default(''),
  workdir: z.string().default(''),
  timeoutMs: z.number().default(600000),
  maxOutputChars: z.number().default(20000),
})

const DEFAULT_TIMEOUT = 600000
const DEFAULT_MAX_OUTPUT = 20000

function normalize(config) {
  const raw = config === undefined || config === null ? {} : config
  const num = (v, d) => (typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : d)
  return {
    enabled: raw.enabled !== false,
    python: typeof raw.python === 'string' ? raw.python.trim() : '',
    workdir: typeof raw.workdir === 'string' ? raw.workdir.trim() : '',
    timeoutMs: num(raw.timeoutMs, DEFAULT_TIMEOUT),
    maxOutputChars: num(raw.maxOutputChars, DEFAULT_MAX_OUTPUT),
  }
}

function pythonOf(cfg) {
  const fromEnv = typeof process.env.INKSOUL_PYTHON === 'string' ? process.env.INKSOUL_PYTHON.trim() : ''
  return cfg.python || fromEnv || 'python3'
}

function clip(text, limit) {
  if (typeof text !== 'string') return ''
  if (text.length <= limit) return text
  return text.slice(0, limit) + '\n…（已截断，共 ' + text.length + ' 字符；调大 maxOutputChars 可放宽）'
}

/** 跑 `python3 -m inksoul.cli <args>`，PYTHONPATH 指向包内 python/，不依赖任何本地安装。 */
function runCli(cfg, args, options) {
  const opts = options === undefined || options === null ? {} : options
  return new Promise((resolve) => {
    const env = {
      ...process.env,
      PYTHONPATH: [PY_ROOT, process.env.PYTHONPATH].filter(Boolean).join(delimiter),
      PYTHONIOENCODING: 'utf-8',
    }
    const child = execFile(
      pythonOf(cfg),
      ['-m', 'inksoul.cli'].concat(args),
      {
        cwd: cfg.workdir || process.cwd(),
        env,
        timeout: opts.timeoutMs === undefined ? cfg.timeoutMs : opts.timeoutMs,
        maxBuffer: 64 * 1024 * 1024,
        encoding: 'utf8',
      },
      (error, stdout, stderr) => {
        const code = error === null || error === undefined ? 0 : (typeof error.code === 'number' ? error.code : -1)
        const hint = error !== null && error !== undefined && error.code === 'ENOENT'
          ? 'python 可执行文件未找到：配置 python 选项或设置 INKSOUL_PYTHON'
          : ''
        resolve({ code, stdout: stdout || '', stderr: (stderr || '') + (hint ? '\n' + hint : '') })
      },
    )
    if (opts.stdin !== undefined && opts.stdin !== null) {
      child.stdin.on('error', () => {})
      child.stdin.end(String(opts.stdin))
    }
  })
}

/** 统一成 {content} 结构：失败也返回文本，不抛异常（模型能读懂并自己改参数）。 */
function asContent(result, cfg) {
  const parts = []
  if (result.stdout) parts.push(result.stdout.trimEnd())
  if (result.stderr.trim()) parts.push('[stderr]' + '\n' + result.stderr.trim())
  if (parts.length === 0) parts.push('（无输出）')
  const body = parts.join('\n')
  if (result.code !== 0) {
    return '[exit ' + result.code + ']' + '\n' + clip(body, cfg.maxOutputChars)
  }
  return clip(body, cfg.maxOutputChars)
}

const output = {
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: { content: { type: 'string' } },
  },
  render(args, value) {
    return [{ type: 'text', text: value.content }]
  },
}

const POLICY_ZH = [
  '## InkSoul：中文文本的机械性诊断与生成闭环',
  '',
  '需要「机械线索」而不是「AI 概率」时用这套工具；结论必须带原始指标，不要写成判定。',
  '',
  '- `inksoul_analyze`：单篇句法骨架指纹 / 分布 / 文体距离（`text` 走 stdin，`path` 走文件）。',
  '- `inksoul_corpus`：目录内多篇两两骨架相似度——判断是不是同一骨架反复复用。',
  '- `inksoul_markers`：AI 味标记族密度（中文 Biber 清单：名词化/定语链/并列/被动/连接词/抽象/比喻/四字格），对照人类网文 p50/p90/p99。',
  '- `inksoul_molds`：句法模具配额（小说体专用）—— 段级基线的复合偏离 z（超人类段 p95 才判 DRIFT）；下限项只做诊断，不再逐项否决。',
  '- `inksoul_gate`：对定稿跑文风闸门，返回逐条命中项；没 PASS 就不当定稿交付。preset=markers 是纯 Python 内置闸门，不依赖宿主脚本。',
  '- `inksoul_agent`：规划→多候选→复核→修订→闸门；要出正文才用，耗时按分钟算。`long/short/rewrite/publish/deai` 预设**强制**载入 `prose-deai` 与 story 主干规范：引擎会核对侦察阶段的工具调用记录，没有 `load_skill` 记录或漏读清单里的任一项就拒绝生成——这是前置条件，不是建议；`draft`/`cover` 不要求载入。',
  '',
  '调用 `inksoul_agent` 的输出纪律：只给结论与正文；不写「好的/我来/以下是/已为你完成」，不复述请求，不加总结段，不写免责声明。过程最多一行进度。',
  '- `inksoul_doctor`：环境自检；报错先跑它。',
  '',
  '边界：相似度高只说「骨架复用明显」，不说「抄袭」；与基线偏离大只说「偏离该基线分布」，不推「非人类」；存疑处标「需人工判断」。闸门未 PASS 时不要把稿子当定稿交出去。',
].join('\n')

function apply(ctx, config) {
  const cfg = normalize(config)
  if (!cfg.enabled) return

  if (ctx.systemPrompt !== undefined) {
    ctx.systemPrompt.section({ name: SECTION_NAME, order: 9600, text: POLICY_ZH })
  }

  ctx.inject(['tools'], (sctx) => {
    const disposers = []

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_doctor',
      description: 'InkSoul 环境自检：Python 版本、架构、可选依赖 jieba、已配置模型。报错时先跑这个。',
      parameters: {},
      output,
      async execute() {
        const r = await runCli(cfg, ['doctor'], { timeoutMs: 60000 })
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_gate',
      description: '对一篇现成中文稿跑文风闸门（去 AI 味精查），返回 status/verdict、逐条命中项与回执行。定稿后才用，单次约 30–90 秒；闸门没 PASS 就别把稿子当定稿交出去。',
      parameters: {
        path: { type: 'string', description: '稿子路径（相对 cwd 或绝对路径）' },
        preset: { type: 'string', description: '闸门预设：deslop（默认规范，需宿主有 /root/deslop）/full（全部闸门）/essay（作文）/zhuque（朱雀检测）/markers（内置标记族闸门，纯 Python）/off' },
        cmd: { type: 'string', description: '自定义闸门命令，{file} 会换成正文路径；给了就以它为准' },
        timeoutSec: { type: 'number', description: '超时秒数（默认 300）' },
      },
      output,
      async execute(args) {
        if (typeof args.path !== 'string' || args.path.trim() === '') return { content: '需要 path。' }
        const argv = ['gate', args.path]
        if (typeof args.cmd === 'string' && args.cmd.trim() !== '') {
          argv.push('--cmd', args.cmd)
        } else {
          const preset = typeof args.preset === 'string' && args.preset.trim() !== '' ? args.preset : 'deslop'
          argv.push('--preset', preset)
        }
        if (typeof args.timeoutSec === 'number' && args.timeoutSec > 0) argv.push('--timeout', String(Math.floor(args.timeoutSec)))
        const r = await runCli(cfg, argv, { timeoutMs: Math.max(cfg.timeoutMs, 900000) })
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_markers',
      description: '只看 AI 味标记族密度：动词名词化/轻动词、定语链、并列堆叠、受事被动、论述型连接词、评价性抽象、比喻模板、四字格。给出每千字密度与人类网文分位数位置；不要把它当成 AI 概率。',
      parameters: {
        text: { type: 'string', description: '待分析文本；给了就不读文件' },
        path: { type: 'string', description: '稿子路径（相对 cwd 或绝对路径）' },
        genre: { type: 'string', description: '对比体裁（默认 网文）' },
        gate: { type: 'boolean', description: 'true = 按内置闸门出 VERDICT/RECEIPT（直接可当交付凭据）' },
      },
      output,
      async execute(args) {
        const useText = typeof args.text === 'string' && args.text.trim().length > 0
        const target = useText ? '-' : args.path
        if (typeof target !== 'string' || target.trim() === '') return { content: '需要 text 或 path 之一。' }
        const argv = ['markers', target]
        if (typeof args.genre === 'string' && args.genre.trim() !== '') argv.push('--genre', args.genre)
        if (args.gate === true) argv.push('--gate')
        const r = await runCli(cfg, argv, { stdin: useText ? args.text : undefined })
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_molds',
      description: '句法模具配额（小说体专用，与 inksoul_markers 互补）。段级基线：每 1000 字窗算 19 项 z，复合偏离 z 超人类段 p95（默认 0.69）才判 DRIFT；单阈值 p90/p10 硬否决在人类段上假失败率 81.9%，已废弃。下限项（感叹/省略/问号/叠词/对白）只报「本段未出现」，不进否决——按 p10 硬补会把文写平。',
      parameters: {
        text: { type: 'string', description: '待测文本；给了就不读文件' },
        path: { type: 'string', description: '正文或段落路径（相对 cwd 或绝对路径）' },
        json: { type: 'boolean', description: 'true = 输出 JSON（含 rows 全量）' },
      },
      output,
      async execute(args) {
        const useText = typeof args.text === 'string' && args.text.trim().length > 0
        const target = useText ? '-' : args.path
        if (typeof target !== 'string' || target.trim() === '') return { content: '需要 text 或 path 之一。' }
        const argv = ['molds', target]
        if (args.json === true) argv.push('--json')
        const r = await runCli(cfg, argv, { stdin: useText ? args.text : undefined })
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_style',
      description: '段级风格距离（轻量）：返回该段到人类网文池的距离、六维 z、以及该改哪两维。写正文时每 800-1000 字一段都要跑一次；距离 >1.30 就要改这一段，改完再跑，别整章一次性验收。',
      parameters: {
        path: { type: 'string', description: '段落文件路径（相对 cwd 或绝对路径）' },
        threshold: { type: 'number', description: '超阈阈值（默认 1.30，人类 p90 = 1.29）' },
      },
      output,
      async execute(args) {
        if (typeof args.path !== 'string' || args.path.trim() === '') return { content: '需要 path（段落文件路径）。' }
        const argv = ['style', args.path]
        if (typeof args.threshold === 'number' && args.threshold > 0) argv.push('--threshold', String(args.threshold))
        const r = await runCli(cfg, argv, {})
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_analyze',
      description: '分析一篇中文文本的句法/文体特征（骨架指纹、句长分布、与体裁基线距离）。text 走标准输入，path 读文件；两者都给时以 text 为准。',
      parameters: {
        text: { type: 'string', description: '待分析文本；给了就不读文件' },
        path: { type: 'string', description: '待分析文件路径（相对 cwd 或绝对路径）' },
        baseline: { type: 'string', description: '可选：体裁基线 JSON 路径' },
        json: { type: 'boolean', description: '输出 JSON（默认 true）；false 返回给人读的审阅文本' },
      },
      output,
      async execute(args) {
        const wantJson = args.json !== false
        const useText = typeof args.text === 'string' && args.text.trim().length > 0
        const target = useText ? '-' : args.path
        if (typeof target !== 'string' || target.trim() === '') {
          return { content: '需要 text 或 path 之一。' }
        }
        const argv = ['analyze', target]
        if (wantJson) argv.push('--json')
        if (typeof args.baseline === 'string' && args.baseline.trim() !== '') argv.push('--baseline', args.baseline)
        const r = await runCli(cfg, argv, { stdin: useText ? args.text : undefined })
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_corpus',
      description: '扫描目录里的多篇文本，算两两句法骨架相似度，用来判断是否同一骨架反复复用。',
      parameters: {
        dir: { type: 'string', description: '目录路径（相对 cwd 或绝对路径）' },
        top: { type: 'number', description: '只保留最相似的 N 对（默认 5）' },
      },
      output,
      async execute(args) {
        if (typeof args.dir !== 'string' || args.dir.trim() === '') return { content: '需要 dir。' }
        const argv = ['corpus', args.dir]
        if (typeof args.top === 'number' && args.top > 0) argv.push('--top', String(Math.floor(args.top)))
        const r = await runCli(cfg, argv, {})
        return { content: asContent(r, cfg) }
      },
    })))

    disposers.push(sctx.tools.register(defineTool({
      name: 'inksoul_agent',
      description: '跑 InkSoul 生成闭环：规划→多候选→复核→修订→文风闸门。慢（分钟级），只在确实要出正文时用。long/short/rewrite/publish/deai 预设强制先 load_skill 载入 prose-deai 与 story 规范——侦察阶段没有 load_skill 记录或漏读任一项会被拒绝生成，draft/cover 不要求。输出只给正文与结论，不写开场白、不复述请求、不加总结段。',
      parameters: {
        brief: { type: 'string', description: '题材/一句话要求' },
        preset: { type: 'string', description: '预设档：draft/long/short/rewrite/publish/cover/deai（默认 long）' },
        target_chars: { type: 'number', description: '目标字数' },
        register: { type: 'string', description: '语域：文学书面/口语都市/爽文快推/冷硬悬疑/情色直写/场景速写（默认文学书面）' },
        perspective: { type: 'string', description: '叙事视角：如「第一人称」「第三人称限制视角」；留空按体裁' },
        genre: { type: 'string', description: '体裁：小说/散文/对话/诗歌（默认小说）' },
        gate: { type: 'string', description: '闸门：deslop/full/essay/zhuque/markers/off，或自定义命令（{file} 换正文路径）' },
        tools: { type: 'boolean', description: '开启 PTC 工具面（侦察阶段模型写程序调用 read_prev/lookup_bible/measure/run_gate）' },
        out: { type: 'string', description: '正文写到该路径（不填则只在输出里返回）' },
      },
      output,
      async execute(args) {
        if (typeof args.brief !== 'string' || args.brief.trim() === '') return { content: '需要 brief。' }
        const argv = ['agent', args.brief]
        if (typeof args.preset === 'string' && args.preset.trim() !== '') argv.push('--preset', args.preset)
        if (typeof args.genre === 'string' && args.genre.trim() !== '') argv.push('--genre', args.genre)
        if (typeof args.register === 'string' && args.register.trim() !== '') argv.push('--register', args.register)
        if (typeof args.perspective === 'string' && args.perspective.trim() !== '') argv.push('--perspective', args.perspective)
        if (typeof args.target_chars === 'number' && args.target_chars > 0) argv.push('--target-chars', String(Math.floor(args.target_chars)))
        if (typeof args.gate === 'string' && args.gate.trim() !== '') argv.push('--gate', args.gate)
        if (args.tools === true) argv.push('--tools')
        if (typeof args.out === 'string' && args.out.trim() !== '') argv.push('--out', args.out)
        const r = await runCli(cfg, argv, {})
        return { content: asContent(r, cfg) }
      },
    })))

    return () => {
      for (const dispose of disposers) {
        try { dispose() } catch (error) { void error }
      }
    }
  })
}

export { Config, PY_ROOT, SECTION_NAME, apply, inject, name, normalize, pythonOf, runCli }