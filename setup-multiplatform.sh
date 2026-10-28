#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "════════════════════════════════════════════════════════"
echo "  Pharma Lab — إعداد المنصات المتعددة"
echo "════════════════════════════════════════════════════════"

echo ""
echo "📱 [1/2] PWA..."
mkdir -p static
if [ ! -f static/icon-192.png ]; then
  python generate_icons.py
fi
echo "  ✅ PWA جاهز"

echo ""
echo "💻 [2/2] Desktop..."
mkdir -p desktop-build/app desktop-build/core desktop-build/static
cp -f app.py desktop-build/app/ 2>/dev/null || true
cp -f core/*.py desktop-build/core/ 2>/dev/null || true
cp -f static/*.png desktop-build/static/ 2>/dev/null || true
chmod +x desktop-build/build-desktop.sh 2>/dev/null || true
echo "  ✅ Desktop جاهز"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  ✅ اكتمل!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "PWA: streamlit run app.py → Add to Home Screen"
echo "Desktop: cd desktop-build && ./build-desktop.sh linux"
