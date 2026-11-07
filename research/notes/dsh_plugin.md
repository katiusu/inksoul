# DSH 插件能力边界（架构调研）

调查对象：`@deepseek-ai/dsh@0.2.1-rc.2`，安装于 `/usr/local/lib/node_modules/@deepseek-ai/dsh/`；
本机实际运行的 profile 是 `/root/.dsh/profiles/web/`（Web GUI 用的就是这个）。
所有引用的行号均来自本机已装文件，未修改任何 DSH 安装目录或 `/root/.dsh` 内的文件。

---

## 结论摘要

1. **插件 = 一个 Cordis 插件模块（ESM）**，导出 `name` / `inject` / `Config` / `apply(ctx, config)` 四个东西，`apply` 里拿到宿主的服务对象（`ctx.tools`、`ctx.systemPrompt`、`ctx.commands`、`ctx.skills`、`ctx.agents`、`ctx.fs`、`ctx.subprocess` …）。没有单独的"插件 SDK"清单，能力 = `inject` 里点的服务 + Node 原生 API。
2. **工具注册**：`ctx.tools.register(defineTool({ name, description, parameters, output: { schema, render }, async execute(args, exec) }))`。
   `defineTool` 在 `dsh-tools/lib/index.js:839`；`ctx.tools` 服务在 `:2799`（`super(ctx, "tools")`）。
3. **提示词注入**三档：`ctx.systemPrompt.section({name, order, text})`（静态段落，排序用 `SECTION_ORDERS`）、`ctx.systemPrompt.context({name, order, text: (context)=>string})`（每步重新求值的动态上下文，能按 agent/会话门控）、`ctx.skills.register({name, description, whenToUse, content, ...})`（按需加载的 skill，不占常驻上下文）。
4. **hook 点存在且分两类**：`ctx.on(event, fn)` 观察型事件，和 `ctx.waterfall(event, ...)` 可拦截/改写型瀑布。工具管线四段：`tools/pre-execute` → 守卫 → `tools/execute` → `tools/post-execute` → `tools/result`（`dsh-tools/README.md` 的 Extension points 段，实现在 `dsh-tools/lib/index.js:3325 / 3434 / 3607 / 3520`）。提示词组装也有瀑布：`system-prompt/assemble`（`dsh-system-prompt/lib/index.js:398`）。
5. **slash command**：`ctx.commands.register({ definitionId, name, description, input?, handler })`（`dsh-commands/lib/index.js:266`，字段校验在 `:149-172`）。
6. **配置**：插件自己 `export const Config = z.object({...})`（schemastery），值写在 profile 的 `cordis.patch.yml` 条目里；**持久状态**可放 `ctx.storage`（`dsh-storage/lib/index.js:109`）或干脆自己写 JSON/Markdown 文件（`dsh-plugin-memory` 就是这么干的：`<dshHome>/memory.json`，见 `lib/config-store.js:23`）。
7. **运行能力：全开**。插件跑在宿主 Node 进程内，可直接 `import 'node:child_process'` 起 Python 子进程、`fetch()` 发 HTTP、`node:fs` 读写文件。`ctx.fs`（带沙箱策略）只是**一个可选服务**，不是进程级隔离——自己 import `node:fs` 就不受它管。
8. 结构化结果：`output.render(args, value)` 产生模型可见 content blocks；另有 `presentCall/presentResult`、`presentationMeta`、`card` 渲染意图供 Host/Web 端做卡片。Web 端实际是按 `tool.call.toolview` 选渲染器（`dsh-tools/README.md` "Host presentation descriptors" 段）。
9. **两层插件**：宿主层（`main`/`exports["."]`，跑在 Node）与 client 层（`exports["./client"]` + `package.json` 的 `dsh.client.platform`）。HMR 由 `@deepseek-ai/dsh-hmr` 负责重载插件源码与 profile 配置。

**对 InkSoul 最关键的判断**：能力边界不是瓶颈。插件能起 Python、读写项目文件、发 HTTP、往 system prompt 塞任意长度的写作规范、注册 `/inksoul` 命令、注册工具。真正的约束是：**插件无法决定 UI 长什么样**（只有 content blocks + 有限的 card 意图），也**没有"流式改写模型输出"的 hook**（`agent/assistant-stream` 是观察型事件，见"未找到证据的问题"）。

---

## 最小插件骨架（真实字段，标注证据文件）

### package.json（以本机已装的第三方插件 `dsh-catgirl-plugin` 为范本）

证据：`/root/.dsh/plugin-src/dsh-catgirl-plugin/package.json`

```json
{
  "name": "dsh-catgirl-plugin",
  "version": "0.2.0",
  "type": "module",
  "main": "index.js",
  "exports": {
    ".": "./index.js",
    "./cordis.patch.yml": "./cordis.patch.yml",
    "./package.json": "./package.json"
  },
  "dependencies": { "@deepseek-ai/schemastery": "^3.18.2" },
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }
}
```

要点：
- `"type": "module"` —— ESM，插件是动态 `import()` 的模块。
- `main`/`exports["."]` 指向入口；`exports` 里**必须**暴露 `./cordis.patch.yml`（如果它作为 bundle 提供补丁层）。
- `dsh.bundle.patch` 指向自带的 YAML 补丁层，用来把插件自己挂进 loader 树。
- 官方包同款字段：`/usr/local/lib/node_modules/@deepseek-ai/dsh-base/package.json` 也有 `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`；`dsh-web-app` 的 `patch` 是数组（多个 preset 层）。

### 入口模块形态

证据：`/root/.dsh/plugin-src/dsh-catgirl-plugin/index.js`（全文 90 行，可直接照抄）

```js
export const name = 'catgirl'                       // :27
export const inject = ['systemPrompt', 'tools']     // :29  声明依赖的宿主服务
export const Config = z.object({                    // :39  schemastery 配置 schema
  name: z.string().default('喵酱'),
  intensity: z.number().min(1).max(3).default(2),
  traits: z.array(z.string()).default([]),
  enableNyaTool: z.boolean().default(false),
})
export function apply(ctx, config) {                // :46
  ctx.effect(() => ctx.systemPrompt.section({       // :59  注册提示词段落
    name: PERSONA_SECTION, order: PERSONA_ORDER, text: persona,
  }), 'catgirl.persona()')
  ctx.effect(() => ctx.tools.register({ ... }), 'catgirl.nya()')  // :66 注册工具
}
```

官方包的形态完全一致：`/usr/local/lib/node_modules/@deepseek-ai/dsh-tool-ask-user/lib/index.js:215-218`

```js
const name = "tool-ask-user";
const inject = ["tools", "userQuestions"];
const Config = z.object({ mode: ..., timeout: ... });   // :211
function apply(ctx, config = {}) { ... }
export { Config, apply, inject, name };                  // :324
```

补充约定（`dsh-plugin-memory`）：如果同时给直接调用者用，可以 `export default apply`，但 DSH loader 会先解包 default 导出，注释写得很清楚：
`/root/.dsh/profiles/web/node_modules/dsh-plugin-memory/lib/index.js:594` —— "DSH's loader unwraps a package's default export before it starts the Cordis plugin."

### 加载方式（三件套，全是真实路径）

1. profile 目录 `/root/.dsh/profiles/web/`，`package.json` 的 `dependencies` 里写插件包（本机大量 `"link:/root/.dsh/plugin-src/xxx"`），`dsh.profile.bundles` 是**有序**的 bundle 列表（`/root/.dsh/profiles/web/package.json`）。
2. 每个 bundle 自带的 `cordis.patch.yml` 被依次叠加。
3. 用户层补丁 `/root/.dsh/profiles/web/cordis.patch.yml` 最后应用，条目格式（真实内容）：
   ```yaml
   - id: agent-default-model
     name: "@deepseek-ai/dsh-agent-default-model"
     config:
       provider: deepseek-official
       model: deepseek-flash
       reasoningEffort: max
   ```
   字段含义由 `@deepseek-ai/cordis-plugin-loader/README.md` 定义：`id` / `name` / `config` / `group` / `disabled` / `inject`。
4. 命令行安装：`dsh plugin --profile <name> <pnpm args>`（`/usr/local/lib/node_modules/@deepseek-ai/dsh/README.md`，"Entry modes" 表）。
5. `cordis.yml` 本体是空数组 `[]`（`/root/.dsh/profiles/web/cordis.yml`），树全靠 patch 层组合——**所以插件配置天然就是"写在 patch YAML 里的 config"**。

---

## 工具注册 API

### 准确签名

`/usr/local/lib/node_modules/@deepseek-ai/dsh-tools/lib/index.js:839`

```js
function defineTool(options) {
  const userExecute = options.execute;
  const userFinalizeContent = options.finalizeContent;
  const userProjectContent = options.projectContent;
  const userRender = options.output.render;
  const userPresentationMeta = options.output.presentationMeta;
  const userPresentCall = options.presentCall;
  const userPresentResult = options.presentResult;
  const userIsConcurrencySafe = options.isConcurrencySafe;
  ...
  const parameters = parameterSchemaSpecToJsonSchema(options.parameters);   // :849
  const outputSchema = valueSchemaSpecToJsonSchema(options.output.schema);  // :850
  ...
  async execute(args, exec) {
    const violations = validate(args);
    if (violations.length > 0) throw new ToolArgsError(violations);         // :861
    return userExecute(args, exec);
  }
}
```

注册入口：`ctx.tools.register(toolOrDefinition)` —— `ToolRuntime` 服务 `super(ctx, "tools")` 在 `dsh-tools/lib/index.js:2799`。

### 参数 schema（作者侧 DSL，不是裸 JSON Schema）

支持 `string | number | integer | boolean | null | array | object | json | oneOf`，每个属性可写 `required: true`、`description`、`enum`、`const`、`items`、`properties`、`additionalProperties`。官方文档示例（`dsh-tools/README.md`，"Register a tool" 段，TS 原文）：

```ts
ctx.tools.register(defineTool({
  name: 'read_file',
  description: 'Read a file from disk.',
  parameters: {
    path: { type: 'string', required: true, description: 'Absolute file path' },
    offset: { type: 'number' },
    limit: { type: 'number' },
  },
  output: {
    schema: { type: 'string' },
    render: (_args, value) => [{ type: 'text', text: value }],
  },
  async execute(args, exec) {
    return readFile(args.path, { encoding: 'utf8', signal: exec.signal })
  },
}))
```

`parameterSchemaSpecToJsonSchema`（`dsh-tools/lib/index.js:803`）把 DSL 编译成受控的 JSON Schema 子集；不支持的写法**直接抛 `JsonSchemaError`（code `UNSUPPORTED_SCHEMA`）**，不会静默接受（`lib/index.js:31-38`）。
对象节点若出现 `type: "object"`，`additionalProperties` 必须显式给 `true`/`false`（`lib/index.js` 的 `authorError(`${path}.additionalProperties must be explicitly true or false`)`）。

### handler 拿到的 context（`exec`）

`dsh-tools/lib/index.js:3229-3267` 构造：

```js
const base = {
  token, callId, rootCallId, name, signal,
  ...agent !== void 0 ? { agent } : {},
  ...parent !== void 0 ? { parent } : {},
  ...exec.schema !== void 0 ? { schema: exec.schema } : {},
  deferContext(context) { deferredContexts.push(context); },
  concludeTurn() { concludingExecutions.add(this); },
};
const execution = { ...base, arguments: deepFreeze(detached) };
```

即：`exec.arguments`（冻结的入参）、`exec.signal`（取消信号，**协作式**，必须自己 observe）、`exec.agent`（当前 agent，可用于按会话门控）、`exec.callId`、`exec.deferContext(ctx)`（往后续上下文追加内容）、`exec.concludeTurn()`。

### 返回值形态

- `execute` 只返回 **canonical JSON value**（必须匹配 `output.schema`，宿主在 `dsh-tools/lib/index.js:3646` 用 `validateJsonSchemaValue(tool.output.schema, detached, "value")` 校验）。
- 模型看到的内容是 `output.render(args, value)` 返回的 content blocks 数组，例如 `[{ type: "text", text: ... }]`（`dsh-tool-ask-user/lib/index.js:296-302`）。

### 错误怎么报

- **参数非法**（模型给错）→ 框架自己抛 `ToolArgsError`（`dsh-tools/lib/index.js:814`，code `INVALID_ARGS`），变成普通错误结果，**不结束本轮**。
- **工具体抛异常** → `toolErrorResult`（`dsh-tools/lib/index.js:3719-3733`）：
  ```js
  return { content: [{ type: "text", text: `Error: ${message}` }], isError: true, error: { message, ...info ? { info } : {} } };
  ```
  即 `throw` 即可，模型收到 `Error: ...` 的文本结果，`isError: true`，不中断 turn。
- 取消：`ABORTED_BEFORE_DISPATCH` / `ABORTED` / `TOOL_TIMEOUT` / `UNKNOWN_TOOL` 是独立的更具体错误码（`dsh-tools/README.md` "Execution and cancellation" 段）。

### 工具可见性/收窄

- `ctx.tools.restrict(filter)` 按 agent 做 allow/deny 掩码，`ctx.tools.get(name, scope)`、`ctx.tools.schemas(scope)`（`dsh-tools/README.md` "Restrict tools per agent"）。
- 注册即自动出现在 system prompt 的工具清单里——不需要手动写提示词段（`dsh-tools/README.md`："Registering a tool is enough to make it visible — the registry feeds its schemas into the system-prompt assembly automatically."）。

---

## 提示词注入

### 1) 静态段落 `ctx.systemPrompt.section`

`/usr/local/lib/node_modules/@deepseek-ai/dsh-system-prompt/lib/index.js:253`

```js
section(section) {
  if (!Number.isFinite(section.order)) throw new TypeError(`prompt section "${section.name}" order must be a finite number`);
  return this.layers.effect(this.ctx, (layer) => layer.sections.insert(section.name, section), { label: "systemPrompt.section()" });
}
```

- 字段：`{ name, order, text, interpolate?, complete? }`。
- `order` 决定插入位置，官方给出中央排序表 `SECTION_ORDERS`（`dsh-system-prompt/lib/index.js:10`）：`HARNESS_IDENTITY: -1000`、`DEPLOYMENT_PERSONA_PREFIX: 0`、`PLAN_POLICY: 500`、`TOOL_BASH: 1000`、`TOOLS_SDK: 5000`、`DEPLOYMENT_PERSONA_SUFFIX: 10200` …… 用 `ctx.systemPrompt.getSectionOrder("TOOL_BASH")` 取具名位置，别硬编码数字。
- 重名规则：**同一 layer 内重名报错**；scoped section 会遮蔽同名全局 section（`lib/index.js:215-216` 的报错文案，以及 `dsh-persona` 的注释：全局挂载会与注册表的 persona 段冲突并 fail loud）。所以第三方要自造名字（catgirl 用 `'catgirl:persona'`，注释里明说避开 `deployment:persona`）。
- `text` 支持 `{{variable}}` 插值，变量要先 `ctx.systemPrompt.variable(name, provider)` 注册；未知变量在渲染时**抛错**（`lib/index.js:170-183` 的 `interpolate`）。

### 2) 动态上下文 `ctx.systemPrompt.context`

`/usr/local/lib/node_modules/@deepseek-ai/dsh-system-prompt/lib/index.js:279`

```js
context(context) {
  if (!Number.isFinite(context.order)) throw new TypeError(`prompt context "${context.name}" order must be a finite number`);
  return this.layers.effect(this.ctx, (layer) => layer.contexts.insert(context.name, context), { label: "systemPrompt.context()" });
}
```

`text` 可以是函数，每步按当前 `context`（含 `context.agent`）重新求值，返回空串则整段消失。真实用例（`dsh-plugin-memory/lib/index.js:297-318`）：

```js
bootDispose = ctx.systemPrompt.context({
  name: 'memory-boot',
  order: -200,
  text: (context) => {
    const resolved = store.get()
    const agent = context?.agent
    if (agent && !tracker.shouldInject(agent.id, resolved)) return ''
    const toneGuide = resolved.toneGuideEnabled ? buildToneGuide({...}) : ''
    return renderBootBlock(memoryDir, { bootFiles, bootMaxChars, bootFileBudgets, toneGuide })
  },
})
```

**这就是"每轮把记忆/写作规范/项目状态读进上下文"的官方姿势**，而且能按 agent 和会话活跃度门控、能在配置变更后立刻生效（不用重启）。
上下文排序表在 `CONTEXT_ORDERS`（`lib/index.js:41`）：`WORKING_DIRECTORY: 100`、`SANDBOX_POLICY: 110`、`APPROVAL_POLICY: 115`、`SUBAGENT_DELEGATION: 120`、`TEAM_IDENTITY: 125`、`HARNESS_SOURCE: 200`、`WEB_SURFACE: 210`。

### 3) Skill（按需加载的指令包）

`ctx.skills.register({...})` —— `/usr/local/lib/node_modules/@deepseek-ai/dsh-skill/lib/index.js:193`，注释说明"项目级条目 > runtime 条目 > user 级条目；同层同名先到先得，后到者拿到 no-op disposer"。真实用例（`dsh-plugin-memory/lib/index.js:322-329`）：

```js
skillDispose = ctx.skills.register({
  name: MEMORY_SKILL_NAME,
  description: MEMORY_SKILL_DESCRIPTION,
  whenToUse: MEMORY_SKILL_WHEN_TO_USE,
  content: memorySkillContent(),
  source: 'dsh-plugin-memory',
  resourceBase: { kind: 'directory', path: memoryDir },
})
```

默认 `invocation` 是 `{ modelInvocable: true, userInvocable: true }`（`dsh-skill/lib/index.js:203-207`）。skill 只在模型主动加载时进上下文——**大量写作规范应该走 skill，常驻人格/铁律走 section**。

### 4) 整段替换/补充 persona

`dsh-persona` 插件：`inject = ["systemPrompt"]`，`apply` 里写 `PERSONA_PREFIX_SECTION` / `PERSONA_SUFFIX_SECTION` 两个槽位，`complete: true` 表示完整替换（`/usr/local/lib/node_modules/@deepseek-ai/dsh-persona/lib/index.js:44-56`）。注意它的注释：这个 row 是 **scope-only** 的，挂在全局会与 `systemPrompt` 自己的 persona 注册冲突。

---

## hook 点

### 一、可拦截的瀑布（`ctx.waterfall`，能改输入/改结果）

| 事件 | 位置 | 语义 |
|---|---|---|
| `tools/pre-execute` | `dsh-tools/lib/index.js:3325` | 每次都问 `{kind: allow/deny/ask}`；`ask` 走审批流 |
| `tools/execute` | `dsh-tools/lib/index.js:3434` | 包裹真正 dispatch，可做超时/重试/度量（README 明说"Only the tools/execute view may replace the required signal"） |
| `tools/post-execute` | `dsh-tools/lib/index.js:3607` | 检查或替换结果，可 block 并回喂 feedback，可追加 context |
| `system-prompt/assemble` | `dsh-system-prompt/lib/index.js:398` | 整份 prompt assembly 最后一道改写 |
| `agent/pre-step` | `dsh-agent-loop/lib/index.js:911` | 每步模型调用前的决策 |

守卫（非 waterfall，单调不可逆）：`ctx.tools.guard(guard)`，返回 reason 即拒绝，后面的 listener 不能翻案（`dsh-tools/README.md` "Enforce policy on calls"）。

### 二、观察型事件（`ctx.on`，只读）

从 `@deepseek-ai/*/lib/index.js` 里 `ctx.on("...")` 的实际调用点统计（出现次数）：

```
session/event 29 · agent/pre-step 12 · session/disposed 8 · session/created 8
agent/error 7 · agent/disposed 7 · agent/created 7 · agent/status 6
agent/inbox/claimed 4 · workspace/session-stop 4 · workspace/session-activity 4
tools/post-execute 4 · tools/pre-execute 3 · tools/execute 3 · tools/result 2
fs/observed 3 · agent/request-error 3 · agent/inbox/discarded 3 · agent/assistant-stream 3
session/flush 2 · llm/stream 2 · fs/write-intent 2 · fs/edit-intent 2 · system-prompt/assemble 2
tools/change 1 · subagent/end 1 · subagent/provider-added 1 · workflow/agent-start 1 · workflow/phase 1 ...
```

对 InkSoul 有意义的几个：
- `agent/created`（`dsh-plugin-memory/lib/index.js:345` 用它给每个新 agent 挂召回）：会话/agent 生命周期的入口。
- `agent/pre-step`：每步前，可用于"写作轮次计数/节奏控制"。
- `session/event`：会话事件流总入口（29 处使用，最稳的观察点）。
- `tools/pre-execute` / `tools/post-execute`：能对**所有**工具调用做审计或拦截（例如禁止某些工具破坏稿件文件）。
- `system-prompt/assemble`：能在最后一步整体改写 prompt（比 section 更强，但要小心把自己绕进去）。

**没有找到**"会话结束时"这种一次性收尾事件的显式名字——只有 `session/disposed`、`session/flush`、`workspace/session-stop`，语义需要再验证（见末节）。

---

## 命令与状态

### slash command

`/usr/local/lib/node_modules/@deepseek-ai/dsh-commands/lib/index.js:266`

```js
register(definition) {
  const registered = normalizeDefinition(definition);
  return this.layers.effect(this.ctx, (layer) => layer.commands.insert(registered.definition.name, registered), { label: "commands.register()" });
}
```

字段校验（`:149-172`）：`name` 必须匹配 `COMMAND_NAME`，`description` 非空字符串，`handler` 必须是函数，可选 `input: { hint, attachments? }`、`recordInput`、`definitionId`。

真实注册（`/usr/local/lib/node_modules/@deepseek-ai/dsh-command-compact/lib/index.js:93-98`）：

```js
yield ctx.commands.register({
  definitionId: CommandDefinitionId("@deepseek-ai/dsh-command-compact"),
  name: "compact",
  description: "Compact older conversation history",
  handler
});
```

`handler(invocation)` 拿到的 `invocation` 有 `rawInput`（原始参数串）、`agent`、`signal`、`commandId`（见 `executeCompact(ctx, invocation)` 与 `:60-72`）。返回值形状是 `{ kind: "success" | "error", text: string, sourceEventSeq?: number }`。

即 `/inksoul` 完全可行：`name: "inksoul"`，`handler` 里读 `invocation.rawInput` 做子命令分发，返回 `{ kind:"success", text:"..." }`；注意 handler 是**人类命令**通道，返回的 text 直接给人看，不经过模型。

### 插件自己的配置

- 声明：`export const Config = z.object({...})`（schemastery）。宿主的 loader 会按 schema 校验并在配置变化时重启/热更该插件（`cordis-plugin-loader/README.md` 的 "Volatile configuration" 段）。
- 落盘位置：profile 的 `cordis.patch.yml`，条目 `{ id, name, config }`。本机 `dsh-peak-chip` 就把几十个运行时字段写在自己的 config 里（`/root/.dsh/profiles/web/cordis.patch.yml`，`id: peak-chip`），可见**config 事实上被当作持久键值存储用**。
- 运行时改配置：`ctx.hmr` / loader 的 `internal/config`，或插件自己维护独立配置文件（下一节）。

### 插件自己的持久状态

三条已验证的路：

1. **自己写文件**（推荐，最简单可控）。
   `dsh-plugin-memory` 的 `lib/config-store.js:23`：
   ```js
   return join(process.env.DSH_HOME || join(homedir(), '.dsh'), MEMORY_CONFIG_FILENAME)
   ```
   读写用 `node:fs`（`config-store.js:15` 的 `existsSync, readFileSync, renameSync, writeFileSync, mkdirSync`）。状态本体是 Markdown + git（`/root/.memory/`）。
2. **`ctx.storage` 服务**：`/usr/local/lib/node_modules/@deepseek-ai/dsh-storage/lib/index.js:109`（`super(ctx, "storage")`），后端通过 `backend` 注册，数据形态通过 `mount(form, facility)` 挂载，`ctx.storage.domain` 是 domain 形态。
3. **插件 config**（见上）——适合少量开关，不适合大块数据。

### 加 HTTP 路由（给 Web GUI 用）

`dsh-plugin-memory/lib/index.js:500-545`：

```js
ctx.inject(['webServer'], (webCtx) => {
  const disposeRoute = webCtx.webServer.register({
    kind: 'exact',
    path: CONFIG_ROUTE_PATH,          // '/api/memory/config'
    handler: async (req, res) => { ... res.writeHead(200, ...); res.end(JSON.stringify(next)) },
  })
  webCtx.effect(() => disposeRoute, 'memory.config-route()')
})
```

注意注释里的关键事实（`index.js` 文件头第 4 点）：**settings 面板的写入接口只服务硬编码的 namespace 白名单，插件 namespace 永远不能远程写**，所以插件要自己做路由 + 自己的 config store。

---

## 运行能力（子进程/HTTP/文件）

插件代码跑在**宿主 Node 进程内**，`apply(ctx, config)` 里 `import` 什么就能用什么，没有能力白名单。

| 能力 | 结论 | 证据 |
|---|---|---|
| spawn 子进程 | 可以 | `dsh-subprocess-local/lib/index.js:9` `import { execFile, spawn, spawnSync } from "node:child_process"`；服务层 `dsh-subprocess/lib/index.js:88` `super(ctx, "subprocess")` |
| spawn **Python** | 可以 | `dsh-experimental-ptc-runtime-python/lib/index.js:1267`（"python subprocess spawned without a fd-3 pipe"）、`:1805`（"python spawn error: ..."）——官方 PTC Python runtime 就是起 python 进程并走 fd-3 管道 |
| 第三方插件自带脚本执行 | 可以 | `dsh-dev-mode/skills/dev-pipeline/scripts/lib.mjs:90` `fetch(...)`；`dsh-batch-tool-calls/scripts/release.mjs:10` `import { execFileSync } from 'node:child_process'`；`superpowers-dsh/skills/writing-skills/render-graphs.js:18` `import { execFileSync } from 'child_process'` |
| HTTP 请求 | 可以 | `dsh-peak-chip/lib/index.js:1063` `const response = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) })`；`:592` 同理 |
| 读写文件 | 可以 | `dsh-plugin-memory/lib/boot.js:14` `import { existsSync, readFileSync, statSync } from 'node:fs'`；`lib/config-store.js:15` 含 `writeFileSync/mkdirSync` |
| 监听本地端口 | 未见直接证据 | 有 `ctx.webserver` 之类的宿主服务（memory 插件用的 `webServer.register`），但没找到插件自建 `http.createServer` 的例子 |

### 权限模型要注意的地方

- DSH 的文件策略（本会话是 `danger-full-access`，也可为 workspace-write 等）作用在 **`ctx.fs` 服务**上（`dsh-fs-sandbox`、`dsh-fs-observation-policy` 这类包），并由 `fs/write-intent`、`fs/edit-intent`、`fs/observed` 事件监视。
- **直接 `node:fs` 不经过这层**。`dsh-plugin-memory` 就绕过了（它读写 `/root/.memory`）。也就是说：插件作者如果要尊重用户策略，应该走 `ctx.fs`；如果只是自己的数据目录，直接 `node:fs` 是现实做法。
- 工具调用的审批/沙箱是**对模型发起的工具调用**生效（`tools/pre-execute` → `verifyGlobalConsent` → `prepareOperation` 在 `dsh-tools/lib/index.js:3325-3352`），不是对插件自身代码生效。插件在 `apply` 或工具体里自己起进程，不会触发那条审批链。

---

## 结构化输出与 UI 呈现

- 模型看到的永远是 `output.render(args, value) => ContentBlock[]`，block 目前可见的类型是 `{ type: "text", text }`（`dsh-tool-ask-user/lib/index.js:296-302`；`dsh-tool-present` 也是同一套）。
- 另有 `presentCall(args)` / `presentResult(args, result)` / `output.presentationMeta(args, value)` / `isConcurrencySafe(args)` / `timeoutMs` / `deferLoading` 这些可选字段（`defineTool`，`dsh-tools/lib/index.js:839-880`）。
- **重要**：`dsh-tools/README.md` 的 "Host presentation descriptors" 段明说——*"The built-in Web Client does not consume those values. It selects a renderer through `tool.call.toolview` and derives card props from raw call arguments, result content, failure state, and persisted metadata."* 也就是说 **presentCall/presentResult 只对 Host-local 消费者有效，官方 Web 端不读**。
- 有 `card` 渲染意图：`dsh-tools/lib/index.js:1535` 出现 `card: "generic"`，来源是 `src/presentation.ts`（"The `card`-tagged UI render intents"）。
- **结论**：InkSoul 想在 GUI 里出漂亮的"稿件卡片"，靠插件侧 `render` 只能给文本；要么接受纯文本/markdown 呈现，要么自己写 **client 层插件**（下一节），要么复用 `present`/deliverables 这类宿主能力。

---

## HMR 与 client 层插件（app 层 vs client 层）

- **HMR**：`@deepseek-ai/dsh-hmr` —— "Reload plugin source and profile configuration while an application is running. Module replacements, Include refreshes and profile configuration changes share one queue."（`dsh-hmr/README.md` 摘要）。base bundle 在 launcher 提供 `profileContext` 时会启用 HMR（`root: []`）；headless/sdk/acp 默认禁用。对 InkSoul 的意义：改插件源码 + 改 `cordis.patch.yml` 里的 `config` 都会触发重载，**开发时不用重启宿主**；但**状态要放在插件外面**（文件/storage），否则热重载会丢。
- **client 插件**：`package.json` 里
  ```json
  "exports": { ".": "...", "./client": "./lib/client.js" },
  "dsh": { "client": { "platform": "web" } }
  ```
  （`/root/.dsh/profiles/web/node_modules/dsh-plugin-memory/package.json`）
  宿主侧校验在 `/usr/local/lib/node_modules/@deepseek-ai/dsh-client-modules/lib/client.js:63-68`：`dsh.client.platform` 必须是字符串，可选 `inject` / `external` 字符串数组，可选 `immediately` 布尔。
- 本机实例：`dsh-plugin-memory` 有 `lib/client.js`（浏览器侧设置面板）；`dsh-catgirl-plugin` 有 `client/` 目录（`decorate-test.mjs`，做渲染装饰）。
- **对 InkSoul 的影响**：纯写作 agent **不需要** client 插件（工具 + prompt + command 足够）；但如果要在 GUI 里做"看稿、对比稿、导出"的自定义面板，就得拆分 `./client` 入口 + 自己的 `webServer` 路由，复杂度显著上升。v1 应避免。

---

## 对 InkSoul 的含义（哪些可行、哪些不可行）

### 可行（有代码证据）

1. **`/inksoul` 命令族**：`ctx.commands.register`（`dsh-commands/lib/index.js:266`）。子命令用 `invocation.rawInput` 自己解析。但注意 handler 是给人看的通道，要"让模型干活"需要 `invocation` 里能拿到 agent 再往会话里注入消息——这一点本机**未找到直接证据**（见末节）。
2. **常驻写作宪法 + 动态项目状态**：`ctx.systemPrompt.section`（静态铁律，`order` 用 `getSectionOrder`）+ `ctx.systemPrompt.context`（每轮读 `稿件/状态.json`，按 agent 门控）。memory 插件是完整参考实现。
3. **大体量规范按需加载**：`ctx.skills.register({ name, description, whenToUse, content, resourceBase })`——去 AI 味规范、体裁模板这类几千字的物料应该做成 skill，别塞常驻 prompt。
4. **生成/改写/校验工具**：`defineTool` + `execute` 里 `spawn` Python（走 `/root/deslop/postwrite.sh` 那类脚本）或直接 `node:fs` 写稿、`fetch` 调模型/外部服务。
5. **持久记忆与状态**：自己写 `<dshHome>/inksoul/*.json|md`（memory 插件同款），或 `ctx.storage`。
6. **HMR 开发闭环**：改源码/改 config 自动重载。
7. **可观测与门禁**：`tools/pre-execute` 拦危险工具、`tools/post-execute` 审计结果、`agent/pre-step` 做轮次控制。

### 不可行 / 高风险

1. **不能定制 GUI 卡片**（除非写 client 插件）。`presentCall/presentResult` 官方 Web 端不消费。
2. **没有"流式改写模型输出"的 hook**：`agent/assistant-stream` 只观察到 3 个 `ctx.on` 调用点，未找到 waterfall 版本 → 无法在 token 流上做去 AI 味重写。**去 AI 味必须在生成后做**（工具/后处理脚本），不能实时。
3. **不能可靠地"插件自己发起一次模型对话"**：没找到 `ctx.agent.send(...)` 之类的公开 API 证据。子 agent 能力由 `dsh-subagent` / `dsh-tool-subagent` 提供（工具层），插件想编排多轮写作大概率要走"注册工具 + 让主 agent 调用"，或注册 subagent provider（`subagent/provider-added` 事件存在，但挂在哪个服务未验证）。
4. **不能假设 `/sdcard` 是普通文件系统**：本项目工作区在 sdcardfs 上，`write`/`edit` 工具的原子发布在这里报 `EINVAL: 无法原子发布文件`（见本机 `~/.dsh/AGENTS.md` §5），插件写稿也必须走 `bash`/`python3` 或先写 `/tmp` 再 `mv`。
5. **热重载会丢内存态**：所有会话级状态必须落盘。

### 建议的 v1 架构映射

| InkSoul 组件 | DSH 机制 |
|---|---|
| 人格 / 写作铁律 | `ctx.systemPrompt.section`（`order` 取 `DEPLOYMENT_PERSONA_PREFIX` 附近，名字避开 `deployment:*`） |
| 体裁规范、去 AI 味规则 | `ctx.skills.register`（按需加载） |
| 项目状态（当前书/卷/章、伏笔表） | `ctx.systemPrompt.context`，每次从磁盘读，按 `context.agent` 门控 |
| 生成/改写/校验 | `defineTool` 若干：`write_chapter`、`revise_passage`、`consistency_check`；内部 `spawn` Python 跑 gate 脚本 |
| 持久化 | 插件自有目录 + JSON/Markdown（复用 `~/.dsh` 约定） |
| 人机入口 | `/inksoul` 命令（`ctx.commands.register`），只做状态展示与开关 |
| Web 面板 | v2 再做（client 插件 + `webServer.register`） |

---

## 未找到证据的问题

1. **插件能否编程式地往会话里注入用户/助手消息、或触发一次模型调用**：没找到公开 API（未在 `dsh-agent`/`dsh-agent-loop` 里确认 `send`/`submit` 之类方法）。这直接决定 `/inksoul` 能否"命令即生成"，建议下一步专门查 `dsh-agent/lib/index.js` 的 `Agents` 服务方法表。
2. **"会话结束"的精确 hook**：只确认了 `session/disposed`、`session/flush`、`workspace/session-stop` 三个事件名存在，语义（谁触发、能否异步等待、是否在 agent 销毁前）未验证。
3. **`ctx.storage` 的完整写入 API**：只读到 `Storage` 服务的 `mount/form/domain`（`dsh-storage/lib/index.js:109-145`），具体 data form 的读写方法没展开（`dsh-storage-domain` / `dsh-storage-json` 未细读）。若要存大结构建议直接用文件。
4. **`agent/assistant-stream` 是 `ctx.on` 还是也能 waterfall**：只在观察型统计里出现 3 次，未找到 waterfall 注册点；因此"流式输出中改写"按**不可行**处理，但需二次确认。
5. **工具 `output.schema` 校验失败时的具体错误码**：确认了校验发生在 `dsh-tools/lib/index.js:3646`，但没枚举对应的错误类（可能在 `createSuccessResult` 内部）。
6. **`ctx.fs` 的沙箱是否也覆盖插件自身的 `node:fs`**：从包结构看是服务级策略（`dsh-fs-sandbox`），未找到进程级/系统级拦截的证据；实际行为应以 `danger-full-access` 之外的策略下做一次写文件实验为准。
7. **插件市场/preset 的 `bundle` 与 `preset` 层级差异**：`dsh-web-app` 的 `dsh.bundle.patch` 是数组（`cordis.patch.yml` + `presets/*.patch.yml`），但"preset 层 vs bundle 层 vs 用户 patch 层"的精确解析顺序只从注释推断（"applied after every bundle layer"），未读到实现代码。
