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
    var link = document.createElement('link');
    link.rel = 'manifest';
    link.href = '/app/static/manifest.json';
    document.head.appendChild(link);
  }
  if (!document.querySelector('meta[name="theme-color"]')) {
    var meta = document.createElement('meta');
    meta.name = 'theme-color';
    meta.content = '#667eea';
    document.head.appendChild(meta);
  }
  var appleMetas = [
    ['apple-mobile-web-app-capable', 'yes'],
    ['apple-mobile-web-app-status-bar-style', 'black-translucent'],
    ['apple-mobile-web-app-title', 'Pharma Lab']
  ];
  appleMetas.forEach(function(pair) {
    if (!document.querySelector('meta[name="' + pair[0] + '"]')) {
      var m = document.createElement('meta');
      m.name = pair[0];
      m.content = pair[1];
      document.head.appendChild(m);
    }
  });
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/app/static/service-worker.js')
      .then(function(r) { console.log('PWA SW:', r.scope); })
      .catch(function(e) { console.warn('PWA SW failed:', e); });
  }
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



# ═══════════════════════════════════════════════════════════
# التبويبات — ربط الوحدات (8 تبويبات)
# ═══════════════════════════════════════════════════════════

st.header("🧬 مختبرات Pharma SDL")

tabs = st.tabs([
    "🏭 Make",
    "🔬 Test",
    "🧠 Analyze",
    "🧬 PROTAC",
    "💊 MIC Lab",
    "🎯 PROTAC Lab",
    "🔌 PubChem",
    "🧫 CYP2C19",
])

# ═══ Tab 0: Make ═══
with tabs[0]:
    st.subheader("توليد SMILES بـ RDKit")
    try:
        from core.maker import MoleculeMaker

        n = st.slider("عدد الجزيئات", 10, 100, 20, key="make_n")
        if st.button("توليد", key="make_btn"):
            with st.spinner("جاري التوليد..."):
                maker = MoleculeMaker(n=n, seed=42)
                st.success(f"✅ تم توليد {len(maker.mols)} جزيء")
                st.write("أول 5 SMILES:")
                for smi in maker.smiles_list[:5]:
                    st.code(smi)
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 1: Test ═══
with tabs[1]:
    st.subheader("محاكاة hERG + LDL-C")
    try:
        import numpy as np

        from core.oracle import MultiObjectiveOracle

        oracle = MultiObjectiveOracle(seed=42)
        sample = np.array([450.0, 3.0, 2, 6, 80.0, 5])
        herg = oracle.herg_toxicity(sample)
        ldl = oracle.ldl_reduction(sample)
        col1, col2 = st.columns(2)
        col1.metric("hERG", f"{herg:.1f}")
        col2.metric("LDL-C", f"{ldl:.1f}")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 2: Analyze ═══
with tabs[2]:
    st.subheader("تحليل Pareto")
    st.info("استخدم مختبر MIC/PROTAC للحصول على نتائج محاكاة كاملة.")
    try:
        from core.agent import MultiObjectiveAgent

        _agent = MultiObjectiveAgent
        st.write("✅ وكيل التعلم النشط متاح")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 3: PROTAC (overview) ═══
with tabs[3]:
    st.subheader("PROTAC — نظرة عامة")
    st.write("Vepdegestrant (Veppanu) — أول PROTAC معتمد (FDA 2026-05-01)")
    try:
        from core.protac import VEPDEGESTRANT

        st.write(f"DC50 = {VEPDEGESTRANT.dc50} nM")
        st.write(f"Dmax = {VEPDEGESTRANT.dmax}%")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 4: MIC Lab ═══
with tabs[4]:
    try:
        from core.mic_lab import render as render_mic

        render_mic()
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في MIC Lab: {e}")

# ═══ Tab 5: PROTAC Lab ═══
with tabs[5]:
    try:
        from core.protac_lab import render as render_protac

        render_protac()
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في PROTAC Lab: {e}")

# ═══ Tab 6: PubChem ═══
with tabs[6]:
    st.subheader("🔌 PubChem")
    try:
        from core.pubchem_client import fetch_drug_data

        query = st.text_input("اسم الدواء", value="aspirin", key="pubchem_q")
        if st.button("بحث", key="pubchem_btn"):
            with st.spinner("جاري البحث..."):
                data = fetch_drug_data(query)
            if data:
                st.success(f"✅ {data['name']} (CID: {data['cid']})")
                col1, col2, col3 = st.columns(3)
                col1.metric("MW", data.get("mw", "—"))
                col2.metric("LogP", data.get("logp", "—"))
                col3.metric("TPSA", data.get("tpsa", "—"))
                if data.get("smiles"):
                    st.code(data["smiles"])
            else:
                st.warning("لم يُعثر على الدواء")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 7: CYP2C19 ═══
with tabs[7]:
    try:
        from core.cyp2c19_lab import render as render_cyp

        render_cyp()
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في CYP2C19: {e}")
