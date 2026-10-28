"""Pharma SDL — Streamlit Web Application."""
import importlib.util

import streamlit as st

# Check RDKit availability (not available on Stlite/WASM)
HAS_RDKIT = importlib.util.find_spec("rdkit") is not None

st.set_page_config(page_title="Pharma SDL", page_icon="🧬", layout="wide")

# ═══════════════════════════════════════════════════════════
# PWA Setup
# ═══════════════════════════════════════════════════════════
import streamlit.components.v1 as _pwa

_pwa.html(
    """
<script>
(function() {
  if (!document.querySelector('link[rel="manifest"]')) {
    const link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/app/static/manifest.json';
    document.head.appendChild(link);
  }
  if (!document.querySelector('meta[name="theme-color"]')) {
    const meta = document.createElement('meta');
    meta.name = 'theme-color';
    meta.content = '#667eea';
    document.head.appendChild(meta);
  }
  ['apple-mobile-web-app-capable|yes',
   'apple-mobile-web-app-status-bar-style|black-translucent',
   'apple-mobile-web-app-title|Pharma Lab'].forEach(function(pair) {
    var parts = pair.split('|');
    var name = parts[0], val = parts[1];
    if (!document.querySelector('meta[name="' + name + '"]')) {
      var m = document.createElement('meta');
      m.name = name;
      m.content = val;
      document.head.appendChild(m);
    }
  });
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/app/static/service-worker.js')
      .then(function(r) { console.log('PWA SW registered:', r.scope); })
      .catch(function(e) { console.warn('PWA SW failed:', e); });
  }
  console.log('PWA initialized');
})();
</script>
    """,
    height=0,
)

st.title("🧬 Pharma SDL — مختبر الفارما الذاتي")
st.markdown("> من الكتاب إلى الكود — من النظرية إلى الاكتشاف")

def rdkit_warning() -> bool:
    """
    Show warning if RDKit is unavailable.
    Returns True if RDKit available, False otherwise.
    """
    if not HAS_RDKIT:
        st.warning(
            "RDKit غير متاح في هذه البيئة. "
            "استخدم النسخة الويب للحصول على الميزات الكاملة."
        )
        return False
    return True

