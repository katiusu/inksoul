#!/bin/sh
# 把 src/inksoul 同步进插件包（插件自带 Python 源码，装完不依赖 pip）。
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$root/plugin/python/inksoul"
mkdir -p "$root/plugin/python"
cp -r "$root/src/inksoul" "$root/plugin/python/inksoul"
find "$root/plugin/python" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
echo "synced $(find "$root/plugin/python/inksoul" -name '*.py' | wc -l) .py files"
