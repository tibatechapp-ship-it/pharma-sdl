"""Pharma SDL — Streamlit Web Application."""
import importlib.util

import streamlit as st

# Check RDKit availability (not available on Stlite/WASM)
HAS_RDKIT = importlib.util.find_spec("rdkit") is not None

st.set_page_config(page_title="Pharma SDL", page_icon="🧬", layout="wide")

# ═══════════════════════════════════════════════════════════
# PWA Setup — st.html (بديل st.components.v1.html المهمل بعد 2026-06)
# ═══════════════════════════════════════════════════════════

st.html(
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
    """
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


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_drug_cached(name: str) -> dict | None:
    """نداء PubChem مخزَّن (ساعة) — يمنع إعادة استدعاء API عند كل إعادة رسم."""
    from core.pubchem_client import fetch_drug_data

    return fetch_drug_data(name)



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
    "🤖 Predict",
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
        query = st.text_input("اسم الدواء", value="aspirin", key="pubchem_q")
        if st.button("بحث", key="pubchem_btn"):
            with st.spinner("جاري البحث..."):
                data = fetch_drug_cached(query)
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

# ═══ Tab 8: Predict — من الاستعلام إلى التنبؤ ═══
with tabs[8]:
    st.subheader("🤖 التنبؤ بالفعالية pIC50")
    st.caption(
        "RandomForest على بصمات Morgan — مدرَّب على قياسات IC50 الحقيقية "
        "لـ SARS-CoV-2 Mpro من ChEMBL (900 جزيء، data/mpro_sample.csv). "
        "فترة الثقة تأتي من تباين تنبؤات الأشجار."
    )
    try:
        from core.ml_potency import load_dataset, train_default_model

        @st.cache_resource(show_spinner="تدريب النموذج — مرة واحدة لكل جلسة…")
        def _potency_model():
            return train_default_model()

        model = _potency_model()
        m = model.metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("R² (اختبار)", f"{m['r2']:.2f}")
        c2.metric("RMSE", f"{m['rmse']:.2f}")
        c3.metric("جزيئات التدريب", f"{m['n_train']}")
        c4.metric("جزيئات الاختبار", f"{m['n_test']}")

        PRESETS = {
            "نيرماتريلڤير — مثبط معتمد (Paxlovid)": (
                "CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)"
                "C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C"
            ),
            "إنستريلفير — مثبط معتمد (Xocova)": (
                "CN1C=C2C=C(C(=CC2=N1)Cl)NC3=NC(=O)N(C(=O)N3CC4=CC(=C(C=C4F)F)F)"
                "CC5=NN(C=N5)C"
            ),
            "أسبرين — مزخرف (ليس مثبط Mpro)": "CC(=O)OC1=CC=CC=C1C(=O)O",
            "إيبوبروفين — مزخرف": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
        }
        sel = st.selectbox("أمثلة جاهزة", list(PRESETS), key="pred_sel")
        smi = st.text_input("أو الصق SMILES الخاص بك", value=PRESETS[sel], key="pred_smi")

        if st.button("تنبؤ", key="pred_btn", type="primary"):
            try:
                res = model.predict(smi)
                colA, colB = st.columns(2)
                colA.metric("pIC50 المتنبأ", f"{res['pic50']:.2f}")
                colB.metric("IC50 المكافئ", f"{res['ic50_nm']:,.0f} nM")
                lo, hi = res["ci95"]
                st.caption(
                    f"فترة ثقة 95% من تباين الأشجار: **{lo:.2f} – {hi:.2f}** "
                    f"(σ = {res['pic50_std']:.2f}) — كلما اتسعت كان الجزيء أبعد "
                    "عن منطقة التدريب (عدم يقين إبيستيمي)."
                )
                if res["icon"] in ("🏆", "✅"):
                    st.success(f"{res['icon']} الحكم: {res['verdict']}")
                elif res["icon"] == "🟡":
                    st.warning(f"{res['icon']} الحكم: {res['verdict']}")
                else:
                    st.info(f"{res['icon']} الحكم: {res['verdict']}")

                df = load_dataset()
                top3 = df.nlargest(3, "pchembl_value")
                st.markdown("**أقوى مثبطات مجموعة التدريب (قياسات ChEMBL الحقيقية):**")
                st.dataframe(
                    top3[["smiles", "pchembl_value"]],
                    hide_index=True,
                    width="stretch",
                )

                import plotly.graph_objects as go

                fig = go.Figure()
                fig.add_bar(
                    y=["جزيئك (تنبؤ)"], x=[res["pic50"]],
                    marker_color="#667eea", orientation="h", name="تنبؤ",
                )
                for i, row in enumerate(top3.itertuples(), 1):
                    fig.add_bar(
                        y=[f"أقوى مثبط حقيقي #{i}"], x=[row.pchembl_value],
                        marker_color="#2dd4a7", orientation="h", name="قياس",
                    )
                fig.update_layout(
                    height=280,
                    margin={"l": 0, "r": 0, "t": 10, "b": 0},
                    xaxis_title="pIC50",
                    showlegend=False,
                )
                st.plotly_chart(fig, width="stretch")
                st.caption(
                    "التنبؤ يُقارن بأقوى 3 مثبطات حقيقية في التدريب — "
                    "خط الزمرد = قياس مخبري، خط البنفسج = تنبؤ النموذج."
                )
            except ValueError as ve:
                st.error(f"⚠️ {ve}")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في Predict: {e}")
