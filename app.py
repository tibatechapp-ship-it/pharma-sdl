"""Pharma SDL — Streamlit Web Application."""
import importlib.util

import pandas as pd
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
    "🎓 Capstone",
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

# ═══ Tab 9: Capstone — من الهدف إلى القرار ═══
with tabs[9]:
    st.subheader("🎓 خط الاكتشاف الكامل: هدف ← مكتبة ← ADME ← ML ← PK/PD ← تقرير")
    st.caption(
        "الهدف المعروض: **SARS-CoV-2 Mpro**. يبدأ الخط من مكتبة جزيئات، يفلترها "
        "بقواعد Lipinski+Veber، يتنبأ بالفعالية بنموذج ML، يحسب الجرعة اللازمة "
        "لتحقق 90% من الاحتلال (C90 من Hill مقابل Cmax فموي)، ثم يُصدر تقريراً."
    )
    try:
        import plotly.express as px
        import plotly.graph_objects as go

        from core.capstone import (
            build_markdown_report,
            build_pdf_report,
            c90_nm,
            fetch_analog_library,
            offline_library,
            run_pipeline,
        )
        from core.ml_potency import train_default_model

        @st.cache_data(ttl=3600, show_spinner="بحث التشابه في PubChem — يُخزَّن ساعة…")
        def _analog_cached(seed: str, max_cids: int) -> pd.DataFrame:
            return fetch_analog_library(seed, max_cids=max_cids)

        @st.cache_resource(show_spinner="تجهيز نموذج الفعالية…")
        def _capstone_model():
            return train_default_model()

        src = st.radio(
            "مصدر المكتبة",
            ["📚 محلية فورية (بلا شبكة)", "🌐 PubChem حي — مشابهات نيرماتريلڤير"],
            key="cap_src",
            horizontal=True,
        )
        c1, c2 = st.columns(2)
        n_lib = c1.slider(
            "حجم المكتبة", 30, 150, 80, step=10, key="cap_n",
            disabled=src.startswith("🌐"),
        )
        dose = c2.slider("الجرعة المرجعية (mg/12h)", 100, 600, 300, step=50, key="cap_dose")

        if st.button("🚀 تشغيل خط الاكتشاف", key="cap_btn", type="primary"):
            with st.status("⏳ ينفَّذ الخط — خمس مراحل…", expanded=True) as status:
                st.write("**1/5** تجميع المكتبة…")
                if src.startswith("🌐"):
                    NIRMATRELVIR = (
                        "CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)"
                        "C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C"
                    )
                    lib = _analog_cached(NIRMATRELVIR, 120)
                    if lib.empty:
                        st.write("⚠️ الشبكة فشلت — التحويل إلى المكتبة المحلية")
                        lib = offline_library(n=n_lib)
                        source = "محلية (احتياط بعد فشل الشبكة)"
                    else:
                        source = f"PubChem تشابه (nirmatrelvir) — {len(lib)} جزيء"
                else:
                    lib = offline_library(n=n_lib)
                    source = "محلية (mpro_sample)"
                st.write(f"&nbsp;&nbsp;&nbsp;↳ {len(lib)} جزيء ({source})")

                st.write("**2/5** فلترة ADME (Lipinski + Veber)…")
                st.write("**3/5** تنبؤ الفعالية بنموذج ML…")
                st.write("**4/5** تحليل PK/PD والقرار…")
                res = run_pipeline(lib, dose_mg=dose, source=source, model=_capstone_model())
                st.write("**5/5** تجهيز التقارير…")
                status.update(label="✅ اكتمل الخط", state="complete", expanded=False)

            st.session_state["cap_res"] = res

        res = st.session_state.get("cap_res")
        if res is not None:
            # ── القمع ──
            st.markdown("#### 🫗 قمع الفلترة")
            fig_funnel = px.bar(
                x=list(res.funnel.values()), y=list(res.funnel.keys()),
                orientation="h", text=list(res.funnel.values()),
                color=list(res.funnel.values()),
                color_continuous_scale=["#c7d2fe", "#667eea"],
            )
            fig_funnel.update_layout(
                height=260, margin={"l": 0, "r": 0, "t": 10, "b": 0},
                xaxis_title="الجزيئات", yaxis={"autorange": "reversed"},
                showlegend=False, coloraxis_showscale=False,
            )
            st.plotly_chart(fig_funnel, width="stretch")

            # ── مقاييس القرار ──
            valid = res.top.dropna(subset=["pic50"])
            if not valid.empty:
                best = valid.iloc[0]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("أقوى تنبؤ pIC50", f"{best.pic50:.2f}")
                m2.metric("IC50 المكافئ", f"{best.ic50_nm:,.0f} nM")
                m3.metric("C90 (احتلال 90%)", f"{c90_nm(best.pic50):,.0f} nM")
                m4.metric("الجرعة اللازمة", f"{best.dose_needed_mg} mg" if best.dose_needed_mg else "—")

            # ── جدول القرار ──
            st.markdown("#### 🏆 أعلى المرشحين — تنبؤ + قرار")
            show = valid[["pic50", "ci_lo", "ci_hi", "ic50_nm", "dose_needed_mg", "pkpd_icon", "pkpd_verdict", "smiles"]].head(10)
            show = show.copy()
            show.insert(0, "الترتيب", range(1, len(show) + 1))
            st.dataframe(
                show,
                hide_index=True,
                width="stretch",
                column_config={
                    "pic50": st.column_config.NumberColumn("pIC50", format="%.2f"),
                    "ci_lo": st.column_config.NumberColumn("CI−", format="%.2f"),
                    "ci_hi": st.column_config.NumberColumn("CI+", format="%.2f"),
                    "ic50_nm": st.column_config.NumberColumn("IC50 (nM)", format="%.0f"),
                    "dose_needed_mg": st.column_config.NumberColumn("الجرعة (mg)", format="%.0f"),
                    "pkpd_icon": st.column_config.TextColumn(""),
                    "pkpd_verdict": st.column_config.TextColumn("القرار PK/PD"),
                    "smiles": st.column_config.TextColumn("SMILES", width="medium"),
                },
            )
            st.caption(
                "الجرعة اللازمة تقارن C90 (Hill، احتلال 90%) مع Cmax الفموي المنمذج "
                f"(F=0.45، Vd=104.7L، t½=6.05h) عند {dose:.0f} mg/12h — ✅ ≤ 300mg، 🟡 ≤ 750mg، 🔴 بعيد."
            )

            # ── تنبؤ مقابل CI ──
            fig_ci = go.Figure()
            for i, r in enumerate(valid.head(10).itertuples(), 1):
                fig_ci.add_scatter(
                    x=[r.pic50, r.pic50], y=[i - 0.15, i + 0.15],
                    mode="lines", line={"color": "#667eea", "width": 3},
                    showlegend=False, hoverinfo="skip",
                )
                fig_ci.add_scatter(
                    x=[r.ci_lo, r.ci_hi], y=[i, i], mode="lines",
                    line={"color": "#2dd4a7", "width": 6}, showlegend=False,
                    name=f"#{i}",
                )
            fig_ci.update_layout(
                height=320, margin={"l": 0, "r": 0, "t": 10, "b": 0},
                xaxis_title="pIC50 (خط أخضر = فترة ثقة 95%)",
                yaxis={"tickvals": list(range(1, min(10, len(valid)) + 1)),
                       "ticktext": [f"#{i}" for i in range(1, min(10, len(valid)) + 1)]},
            )
            st.plotly_chart(fig_ci, width="stretch")

            # ── التقارير ──
            st.markdown("#### 📄 التقارير")
            d1, d2 = st.columns(2)
            md = build_markdown_report(res)
            d1.download_button(
                "⬇️ تقرير Markdown", md, file_name="capstone_report.md",
                mime="text/markdown", key="cap_md", width="stretch",
            )
            pdf = build_pdf_report(res)
            if pdf:
                d2.download_button(
                    "⬇️ تقرير PDF (عربي)", pdf, file_name="capstone_report.pdf",
                    mime="application/pdf", key="cap_pdf", width="stretch",
                )
            else:
                d2.info("PDF غير متاح في هذه البيئة — استخدم Markdown.")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في Capstone: {e}")
