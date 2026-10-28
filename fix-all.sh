#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# fix-all.sh — إصلاح شامل لنشر Pharma Lab
# الاستخدام: bash fix-all.sh
# ═══════════════════════════════════════════════════════════════

set -e

REPO_DIR="$HOME/pharma-sdl"
GITHUB_REPO="tibatechapp-ship-it/pharma-sdl"
HF_SPACE="pharma-lab"
HF_USER="tibatechapp"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}▶${NC} $1"; }
ok() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
err() { echo -e "${RED}❌${NC} $1"; }

clear
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   🔧 fix-all.sh — إصلاح نشر Pharma Lab                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

log "فحص البيئة..."
if [ ! -d "$REPO_DIR" ]; then err "المجلد غير موجود: $REPO_DIR"; exit 1; fi
cd "$REPO_DIR"
ok "المجلد موجود: $REPO_DIR"

echo ""
log "المرحلة 1: تعطيل النشر..."
if [ -f ".github/workflows/deploy-hf.yml" ]; then
    mv .github/workflows/deploy-hf.yml .github/workflows/deploy-hf.yml.disabled
    git add .github/workflows/
    git commit -m "ci: disable HF deploy temporarily" || true
    git push origin main || true
    ok "تم تعطيل النشر"
else
    warn "النشر معطّل مسبقاً"
fi

echo ""
log "المرحلة 2: Streamlit Cloud"
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  🌐 افعل هذا الآن في المتصفح:                             ║"
echo "║                                                           ║"
echo "║  1. افتح: https://share.streamlit.io                      ║"
echo "║  2. Continue with GitHub                                  ║"
echo "║  3. New app                                               ║"
echo "║  4. Repository: $GITHUB_REPO              ║"
echo "║  5. Branch: main                                          ║"
echo "║  6. Main file: app.py                                     ║"
echo "║  7. Deploy!                                               ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

read -p "هل أنجزت النشر على Streamlit Cloud؟ (y/n): " streamlit_done
if [ "$streamlit_done" = "y" ]; then
    ok "رائع! التطبيق حي على Streamlit Cloud"
else
    warn "سأكمل، لكنك ستحتاج العودة لهذه الخطوة"
fi

echo ""
log "المرحلة 3: HF_TOKEN"
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  🔑 احصل على HF_TOKEN:                                    ║"
echo "║                                                           ║"
echo "║  1. افتح: https://huggingface.co/settings/tokens          ║"
echo "║  2. New token                                             ║"
echo "║     - Name: github-deploy                                 ║"
echo "║     - Type: Write  ← مهم                                  ║"
echo "║  3. Create token                                          ║"
echo "║  4. انسخ الـ token (يبدأ بـ hf_)                          ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

read -p "هل لديك HF_TOKEN الآن؟ (y/n): " has_token
if [ "$has_token" != "y" ]; then
    warn "توقف هنا. احصل على HF_TOKEN أولاً."
    exit 0
fi

read -sp "الصق HF_TOKEN (لن يظهر): " hf_token
echo ""

if [[ ! "$hf_token" =~ ^hf_ ]]; then
    err "الـ token يجب أن يبدأ بـ hf_"
    exit 1
fi
ok "صيغة الـ token صحيحة"

echo ""
log "المرحلة 4: إضافة HF_TOKEN إلى GitHub"
if command -v gh &> /dev/null; then
    log "استخدام gh CLI..."
    if ! gh auth status &> /dev/null; then
        warn "تحتاج تسجيل الدخول إلى gh أولاً"
        gh auth login
    fi
    echo "$hf_token" | gh secret set HF_TOKEN
    ok "تم إضافة HF_TOKEN عبر gh"
    echo ""
    log "التحقق من الأسرار:"
    gh secret list
else
    warn "gh CLI غير مثبت"
    echo ""
    echo "أضف السر يدوياً من:"
    echo "https://github.com/$GITHUB_REPO/settings/secrets/actions"
    echo ""
    read -p "هل أضفت HF_TOKEN يدوياً؟ (y/n): " manual_added
    if [ "$manual_added" != "y" ]; then
        err "توقف. أضف HF_TOKEN أولاً."
        exit 1
    fi
    ok "تم الإضافة يدوياً"
fi

echo ""
log "المرحلة 5: إعادة تفعيل النشر"
if [ -f ".github/workflows/deploy-hf.yml.disabled" ]; then
    mv .github/workflows/deploy-hf.yml.disabled .github/workflows/deploy-hf.yml
    git add .github/workflows/
    git commit -m "ci: re-enable HF deploy with secret configured"
    git push origin main
    ok "تم إعادة تفعيل النشر"
else
    warn "النشر مفعّل مسبقاً"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║  ✅ اكتمل الإصلاح!                                        ║"
echo "║                                                           ║"
echo "║  📊 روابط للمتابعة:                                        ║"
echo "║                                                           ║"
echo "║  🔗 GitHub Actions:                                       ║"
echo "║     https://github.com/$GITHUB_REPO/actions ║"
echo "║                                                           ║"
echo "║  🌐 Streamlit Cloud:                                      ║"
echo "║     https://tibatechapp-ship-it-pharma-sdl.streamlit.app  ║"
echo "║                                                           ║"
echo "║  🤗 Hugging Face:                                         ║"
echo "║     https://huggingface.co/spaces/$HF_USER/$HF_SPACE   ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

ok "الخطوة التالية: راقب Actions وتأكد من النشر"
