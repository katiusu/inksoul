#!/bin/sh
# 开发安装：打包 → 解到 profile/node_modules/dsh-inksoul（实体文件，非 pnpm 硬链）。
# 为什么不用 dsh plugin add 落文件：pnpm 硬链到 store，lib/index.js 的 ESM import 会从 store 真实路径
# 找宿主包 @deepseek-ai/*，找不到（ERR_MODULE_NOT_FOUND）；解包成实体文件后从 profile/node_modules 向上解析正常。
# 用法：sh scripts/dev-install.sh [profile]   （默认 web）
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
profile=${1:-web}
d="/root/.dsh/profiles/$profile/node_modules/dsh-inksoul"
cd "$root"
rm -f dsh-inksoul-*.tgz
npm pack --silent >/dev/null
tgz=$(ls dsh-inksoul-*.tgz | head -1)
mkdir -p "$(dirname "$d")"
rm -rf "$d.tmp" && mkdir -p "$d.tmp"
tar -xzf "$tgz" -C "$d.tmp" --strip-components=1
rm -rf "$d" && mv "$d.tmp" "$d"
node -e "import('$d/lib/index.js').then(m=>console.log('IMPORT OK inject='+JSON.stringify(m.inject)),e=>{console.log('IMPORT FAIL',e.code,e.message);process.exit(1)})"
echo "installed -> $d ($(du -sh "$d" | cut -f1))"
