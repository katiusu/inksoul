#!/bin/sh
# 插件自测：把包拷到 /tmp（sdcard 不能建软链）、软链宿主包、用桩 ctx 逐个跑工具。
# 用法：sh scripts/selftest.sh [--with-gate]
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
dest=${TMPDIR:-/tmp}/inksoul-selftest
rm -rf "$dest"
mkdir -p "$dest/node_modules"
cp -r "$root/lib" "$root/python" "$root/package.json" "$root/cordis.patch.yml" "$dest/"
ln -s /usr/local/lib/node_modules/@deepseek-ai "$dest/node_modules/@deepseek-ai"
cp "$root/scripts/selftest.mjs" "$dest/selftest.mjs"
node "$dest/selftest.mjs" "$dest" "$@"
