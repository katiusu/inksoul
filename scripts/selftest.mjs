import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.argv[2]
const withGate = process.argv.includes('--with-gate')
const { apply } = await import(join(root, 'lib', 'index.js'))
const tools = []
const sections = []
const ctx = {
  systemPrompt: { section: (s) => sections.push(s) },
  inject: (deps, fn) => { fn({ tools: { register: (def) => { tools.push(def); return () => {} } } }) },
}
apply(ctx, { enabled: true })

const results = []
let failed = 0
function check(name, ok, detail) {
  results.push([ok ? 'PASS' : 'FAIL', name, detail === undefined ? '' : detail])
  if (!ok) failed += 1
}
const get = (n) => tools.find(t => t.name === n)

check('policy section', sections.some(s => s.name === 'inksoul:policy'), sections.map(s => s.name).join(','))
check('five tools', tools.length === 5, tools.map(t => t.name).join(','))

const doctor = await get('inksoul_doctor').execute({})
check('doctor', /核心功能可用/.test(doctor.content), doctor.content.split(String.fromCharCode(10)).slice(-1)[0])

const text = '她推开门。雨声灌进来，屋里没人。桌上那盏灯还亮着。她站了一会儿，把伞靠在墙角。' + String.fromCharCode(10) + '窗外的水顺着玻璃往下淌，像有人在慢慢擦。她把手贴上去，凉的。'
const an = await get('inksoul_analyze').execute({ text })
const chars = (an.content.match(/"chars":\s*(\d+)/) || [])[1]
const clauses = (an.content.match(/"clause_count":\s*(\d+)/) || [])[1]
check('analyze text', Number(chars) > 0 && Number(clauses) > 0, 'chars=' + chars + ' clauses=' + clauses)

const dir = join(root, 'corpus')
mkdirSync(dir, { recursive: true })
const long = '她推开门。雨声灌进来，屋里没人。桌上那盏灯还亮着。她站了一会儿，把伞靠在墙角。窗外的水顺着玻璃往下淌，像有人在慢慢擦。她把手贴上去，凉的。'
writeFileSync(join(dir, 'a.txt'), long.repeat(8), 'utf8')
writeFileSync(join(dir, 'b.txt'), '雨下了一整个下午。她把窗关严，仍旧觉得冷。茶凉了，她没有再倒。他数着台阶往上走，一共十七级。第十七级上有一道裂缝。'.repeat(8), 'utf8')
const co = await get('inksoul_corpus').execute({ dir, top: 3 })
const coLines = co.content.split(String.fromCharCode(10)).filter(Boolean)
const coOk = /Burrows|骨架|相似/.test(co.content) && !/\[exit|错误：/.test(co.content)
check('corpus', coOk, coLines[coLines.length - 1].slice(0, 70))

if (withGate) {
  const f = join(root, 'gate-sample.txt')
  writeFileSync(f, '她推开门。雨声灌进来，屋里没人。' + String.fromCharCode(10), 'utf8')
  const g = await get('inksoul_gate').execute({ path: f, preset: 'deslop' })
  check('gate', /status:/.test(g.content) && /RECEIPT:/.test(g.content), (g.content.match(/status:[^|]*/) || [''])[0])
}

for (const [s, n, d] of results) console.log(s + '  ' + n + (d ? '  — ' + d : ''))
console.log(failed === 0 ? 'SELFTEST OK (' + results.length + ' checks)' : 'SELFTEST FAILED (' + failed + '/' + results.length + ')')
process.exit(failed === 0 ? 0 : 1)
