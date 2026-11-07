#!/bin/sh
# 把引擎源码 src/inksoul 同步进插件包内嵌目录 python/inksoul。
# 插件是主产品，python/ 随包发布；改完 src/ 就重跑（npm prepack 也会自动跑）。
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$root/python/inksoul"
mkdir -p "$root/python"
cp -r "$root/src/inksoul" "$root/python/inksoul"
find "$root/python" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
echo "synced $(find "$root/python/inksoul" -name '*.py' | wc -l) .py files"
