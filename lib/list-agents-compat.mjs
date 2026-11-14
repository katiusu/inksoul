/**
 * list_agents 兼容层：让同一份 bundle patch 同时适配 DSH 0.2.1 与 0.2.2+。
 *
 * 0.2.1 把 list_agents 做成独立插件，发布在
 *   '@deepseek-ai/dsh-tool-subagent-control/list-agents'
 * 这个子路径上；0.2.2-rc.1 起该子路径被删除，改由主包 lib/index.js 自行注册。
 *
 * 本模块只做一件事：子路径仍然存在时把那个插件挂上去，不存在时静默返回。
 * 于是在 0.2.2+ 上是空操作（主包已经注册），在 0.2.1 上补回 list_agents。
 */
export const name = 'tool-subagent-list-agents-compat'

export async function apply(ctx) {
  let mod
  try {
    mod = await import('@deepseek-ai/dsh-tool-subagent-control/list-agents')
  } catch {
    return
  }
  if (typeof mod.apply !== 'function') return
  ctx.plugin({ name: mod.name, inject: mod.inject, apply: mod.apply })
}
