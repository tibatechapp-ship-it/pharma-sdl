#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
TARGET="${1:-linux}"
echo "═══════════════════════════════════════════════════"
echo "  Pharma Lab — بناء سطح المكتب ($TARGET)"
echo "═══════════════════════════════════════════════════"
mkdir -p app core static
cp -f ../app.py app/ 2>/dev/null || true
cp -f ../core/*.py core/ 2>/dev/null || true
cp -f ../static/*.png static/ 2>/dev/null || true
if [ ! -d node_modules ]; then
  echo "📦 تثبيت Electron..."
  npm install
fi
case "$TARGET" in
  win)   npm run build:win ;;
  linux) npm run build:linux ;;
  mac)   npm run build:mac ;;
  all)   npm run build:all ;;
  *)     echo "الاستخدام: $0 [win|linux|mac|all]"; exit 1 ;;
esac
echo "✅ اكتمل! الملفات في: $(pwd)/dist"
ls -lh dist/ 2>/dev/null || true
