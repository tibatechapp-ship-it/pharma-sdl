"""Pharma SDL — Streamlit Web Application."""
import importlib.util
import uuid

import pandas as pd
import streamlit as st

from core.i18n import t

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


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_cpic_cached(gene: str) -> list[dict]:
    """نداء CPIC مخزَّن (24 ساعة) — توصيات PGx حية مع احتياطي مدمج."""
    from core.pgx import fetch_cpic

    return fetch_cpic(gene)


# ═════════════════════════════════════════════════════
# مبدّل اللغة + العنوان
# ═════════════════════════════════════════════════════

LANG_LABEL = st.sidebar.selectbox(
    t("ar", "lang_label"), ["العربية", "English"], index=0, key="lang"
)
LANG = "ar" if LANG_LABEL == "العربية" else "en"

st.title(t(LANG, "app_title"))
st.markdown(t(LANG, "app_tagline"))

# ═══════════════════════════════════════════════════════════
# توجيه بيئة stlite (متصفح/WASM) — رسالة صريحة بدل أخطاء استيراد غامضة
# ═══════════════════════════════════════════════════════════
from core.runtime import is_stlite  # استيراد موضعي بعد إعداد الصفحة

if is_stlite():
    st.warning(t(LANG, "stlite_title"))
    st.markdown(t(LANG, "stlite_body"))


# ═══════════════════════════════════════════════════════════
# التبويبات — ربط الوحدات (13 تبويباً)
# ═══════════════════════════════════════════════════════════

st.header(t(LANG, "lab_header"))

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
    t(LANG, "tab_docking"),
    t(LANG, "tab_pgx"),
    t(LANG, "tab_admet"),
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

        # ── توسيع المكتبة حول بذرة (S6): PubChem حي أو BRICS محلي ──
        st.divider()
        st.markdown(f"### {t(LANG, 'expand_title')}")
        st.caption(t(LANG, "expand_caption"))
        from core.expander import SRC_BRICS, SRC_PUBCHEM, expand_library

        seed = st.text_input(
            t(LANG, "expand_seed"), value="CC(=O)OC1=CC=CC=C1C(=O)O", key="expand_seed"
        )
        n_exp = st.slider(t(LANG, "expand_n"), 4, 20, 8, key="expand_n")
        if st.button(t(LANG, "expand_btn"), type="secondary", key="expand_btn"):
            if not seed.strip():
                st.info(t(LANG, "expand_empty"))
            else:
                with st.spinner(t(LANG, "expand_status")):
                    exp_smiles, src = expand_library(seed.strip(), n=n_exp)
                if src == SRC_PUBCHEM and exp_smiles:
                    st.success(t(LANG, "expand_src_live").format(n=len(exp_smiles)))
                elif src == SRC_BRICS and exp_smiles:
                    st.success(t(LANG, "expand_src_offline").format(n=len(exp_smiles)))
                else:
                    st.info(t(LANG, "expand_none"))
                for smi in exp_smiles:
                    st.code(smi)

        # ── التوليد الموجّه بالهدف (S9): مكافئ ChatChemTS محلي بلا مفتاح ──
        st.divider()
        st.markdown(f"### {t(LANG, 'goal_title')}")
        st.caption(t(LANG, "goal_caption"))
        from core.goalgen import GoalSpec, generate_toward_goal

        g_mw = st.slider(t(LANG, "goal_mw"), 150, 700, (250, 500), step=10, key="goal_mw")
        g_logp = st.slider(t(LANG, "goal_logp"), 0.0, 7.0, 5.0, 0.5, key="goal_logp")
        g_sim = st.slider(t(LANG, "goal_sim"), 0.0, 1.0, 0.30, 0.05, key="goal_sim")
        g_n = st.slider(t(LANG, "goal_n"), 3, 10, 5, key="goal_n")
        if st.button(t(LANG, "goal_btn"), type="secondary", key="goal_btn"):
            if not seed.strip():
                st.info(t(LANG, "goal_empty"))
            else:
                with st.spinner(t(LANG, "goal_running")):
                    report = generate_toward_goal(
                        seed.strip(),
                        goal=GoalSpec(
                            mw_min=float(g_mw[0]),
                            mw_max=float(g_mw[1]),
                            logp_max=float(g_logp),
                            sim_floor=float(g_sim),
                        ),
                        top_keep=int(g_n),
                    )
                if report.reason == "invalid_seed":
                    st.info(t(LANG, "goal_invalid"))
                elif not report.survivors:
                    st.info(t(LANG, "goal_none").format(r=report.rounds_run))
                else:
                    st.success(
                        t(LANG, "goal_done").format(
                            n=len(report.survivors), r=report.rounds_run,
                            p=report.pool_size,
                        )
                    )
                    for cand in report.survivors:
                        st.code(cand.smiles)
                        st.caption(
                            t(LANG, "goal_props").format(
                                mw=cand.mw, logp=cand.logp, tpsa=cand.tpsa,
                                qed=cand.qed, sim=cand.sim,
                            )
                        )
                st.caption(t(LANG, "goal_engine"))
                with st.expander(t(LANG, "goal_lesson")):
                    st.write(t(LANG, "goal_lesson_text"))
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

        # ═══ مقارنة النماذج — RandomForest مقابل Gradient Boosting ═══
        st.markdown("---")
        st.markdown("#### ⚖️ مقارنة النماذج — RandomForest مقابل Gradient Boosting")
        st.caption(
            "نفس البيانات ونفس بصمات Morgan لكل النماذج، تحقق متقاطع 5 طيّات — "
            "الأرقام محسوبة من تنبؤات خارج الطية (جزيئات لم يرها النموذج أثناء "
            "التدريب). **R² الأعلى أفضل، RMSE الأقل أفضل** — والدرس هنا: المقارنة "
            "العادلة تتطلب توحيد البيانات والطيّات لا تغيير عدة أشياء معاً."
        )

        @st.cache_resource(show_spinner=False)
        def _compare_models_cached():
            from core.ml_compare import compare_models

            return compare_models()

        if st.button("شغّل المقارنة", key="mlcmp_btn"):
            with st.spinner("تحقق متقاطع على 900 جزيء — قد يستغرق دقيقة…"):
                st.session_state["mlcmp"] = _compare_models_cached()

        cmp_reports = st.session_state.get("mlcmp")
        if cmp_reports:
            from plotly.subplots import make_subplots

            df_cmp = pd.DataFrame(
                [
                    {
                        "النموذج": r.name_ar,
                        "R² (أعلى أفضل)": r.r2,
                        "RMSE (أقل أفضل)": r.rmse,
                        "MAE": r.mae,
                        "زمن التدريب (ث)": r.fit_seconds,
                        "طيّات": r.n_folds,
                    }
                    for r in cmp_reports
                ]
            )
            st.dataframe(df_cmp, hide_index=True, width="stretch")

            fig_cmp = make_subplots(
                rows=1,
                cols=2,
                subplot_titles=("R² (أعلى أفضل)", "RMSE (أقل أفضل)"),
            )
            model_colors = {
                "RandomForest": "#667eea",
                "GradientBoosting": "#2dd4a7",
            }
            for r in cmp_reports:
                fig_cmp.add_bar(
                    x=[r.name], y=[r.r2], marker_color=model_colors[r.name],
                    showlegend=False, row=1, col=1,
                )
                fig_cmp.add_bar(
                    x=[r.name], y=[r.rmse], marker_color=model_colors[r.name],
                    showlegend=False, row=1, col=2,
                )
            fig_cmp.update_layout(
                height=340, margin={"l": 0, "r": 0, "t": 40, "b": 0}
            )
            st.plotly_chart(fig_cmp, width="stretch")

            best_r2 = max(cmp_reports, key=lambda r: r.r2)
            best_rmse = min(cmp_reports, key=lambda r: r.rmse)
            st.success(
                f"🏆 على هذه البيانات: **{best_r2.name_ar}** الأعلى في R² "
                f"({best_r2.r2:.3f}) — والأفضل في RMSE: **{best_rmse.name_ar}** "
                f"({best_rmse.rmse:.3f}). لا يوجد نموذج «أفضل دائماً»: bagging "
                "يقاوم التوزيع العشوائي، وboosting يلتقط الأنماط غير الخطية — "
                "والقرار من الأرقام لا من المشاعر."
            )
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

            # ── القراءة التلقائية (S8): مكتبة → ADME → Vina → محلل داخلي → ADMET → PDF ──
            st.divider()
            st.markdown(f"### {t(LANG, 'auto_title')}")
            st.caption(t(LANG, "auto_caption"))
            from core.docking import HAS_MEEKO, HAS_VINA, load_receptors

            auto_recs = load_receptors()
            auto_receptor = auto_recs[0] if auto_recs else None
            if auto_recs:
                auto_opts = {
                    (r.label_ar if LANG == "ar" else r.label_en): r for r in auto_recs
                }
                auto_rec_sel = st.selectbox(
                    t(LANG, "auto_target"), list(auto_opts), key="auto_rec"
                )
                auto_receptor = auto_opts[auto_rec_sel]
            auto_seed = st.text_input(
                t(LANG, "auto_seed"), value="CC(=O)OC1=CC=CC=C1C(=O)O", key="auto_seed"
            )
            a1, a2 = st.columns(2)
            auto_n = a1.slider(t(LANG, "auto_n"), 4, 12, 6, key="auto_n")
            auto_top = a2.slider(t(LANG, "auto_top"), 2, 6, 3, key="auto_top")
            if st.button(t(LANG, "auto_btn"), type="primary", key="auto_btn"):
                if not auto_seed.strip():
                    st.info(t(LANG, "auto_empty_seed"))
                elif not (HAS_VINA and HAS_MEEKO) or auto_receptor is None:
                    st.warning(t(LANG, "auto_no_engine"))
                else:
                    from core.auto_pipeline import run_auto_pipeline

                    with st.status(t(LANG, "auto_status"), expanded=True) as astat:
                        st.write("**1/6** بناء المكتبة حول البذرة (حياً ثم محلياً)…")
                        st.write("**2/6** فلتر ADME محلي (Lipinski+Veber+hERG المحاكى)…")
                        st.write("**3/6** ربط Vina — ثوانٍ لكل جزيء…")
                        st.write("**4/6** المحلل الداخلي للبوزات (S7)…")
                        st.write("**5/6** فلتر ADMET (Ersilia إن توفّر خادم وإلا محلي)…")
                        st.write("**6/6** الأعلام والتقرير…")
                        auto_report = run_auto_pipeline(
                            auto_seed,
                            auto_receptor,
                            n_library=auto_n,
                            dock_top=auto_top,
                            model=_capstone_model(),
                        )
                        astat.update(
                            label=t(LANG, "auto_done"), state="complete", expanded=False
                        )
                    st.session_state["auto_rep"] = auto_report

            rep = st.session_state.get("auto_rep")
            if rep is not None:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(t(LANG, "auto_m_lib"), len(rep.library))
                m2.metric(t(LANG, "auto_m_docked"), len(rep.results))
                m3.metric(t(LANG, "auto_m_admet"), rep.admet_passed)
                m4.metric(
                    t(LANG, "auto_m_best"),
                    f"{rep.best_vina:.2f}" if rep.best_vina is not None else "—",
                )
                st.caption(
                    f"{t(LANG, 'auto_engine')}: **{rep.admet_engine}** · "
                    f"المصدر: {rep.source}"
                )
                if rep.results:
                    st.markdown(f"#### {t(LANG, 'auto_table_title')}")
                    df_auto = pd.DataFrame(
                        [
                            {
                                "SMILES": r["smiles"],
                                t(LANG, "col_vina"): (
                                    round(r["vina"], 2)
                                    if r.get("vina") is not None else None
                                ),
                                t(LANG, "col_inhouse"): r.get("inhouse"),
                                t(LANG, "col_hbonds"): r.get("hbonds"),
                                t(LANG, "col_clashes"): r.get("clashes"),
                                "ADMET": "✅" if r.get("admet_ok") else "❌",
                            }
                            for r in rep.results
                        ]
                    )
                    st.dataframe(df_auto, hide_index=True, width="stretch")
                if rep.best_smiles:
                    st.markdown(f"**{t(LANG, 'auto_best_smiles')}:**")
                    st.code(rep.best_smiles)
                st.markdown(f"#### {t(LANG, 'auto_flags_title')}")
                for fl in rep.pgx_flags:
                    st.markdown(f"- {fl}")
                if rep.report_pdf:
                    st.download_button(
                        t(LANG, "auto_pdf"),
                        rep.report_pdf,
                        file_name="auto_report.pdf",
                        mime="application/pdf",
                        key="auto_pdf",
                        width="stretch",
                    )
                else:
                    st.info(t(LANG, "auto_no_pdf"))
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في Capstone: {e}")

# ═══ Tab 10: Docking — فيزياء ثلاثية الأبعاد ═══
with tabs[10]:
    st.subheader(t(LANG, "dock_title"))
    st.caption(t(LANG, "dock_caption"))
    try:
        from core.docking import (
            HAS_MEEKO,
            HAS_VINA,
            LESSON,
            build_3d_html,
            dock_ligand,
            load_receptors,
            pic50_to_dg_kcal,
            prepare_ligand,
        )

        receptors = load_receptors()
        if not receptors:
            st.error("لا توجد مستقبلات مُجهَّزة — شغّل scripts/prepare_receptors.py")
        else:
            with st.expander(t(LANG, "dock_lesson_title"), expanded=False):
                st.markdown(LESSON.get(LANG, LESSON["ar"]))

            rec_opts = {
                (r.label_ar if LANG == "ar" else r.label_en): r for r in receptors
            }
            rec_sel = st.selectbox(t(LANG, "dock_target"), list(rec_opts), key="dock_rec")
            receptor = rec_opts[rec_sel]
            st.info(receptor.note_ar if LANG == "ar" else receptor.note_en)

            preset_labels = {
                receptor.demo_name_ar if LANG == "ar" else receptor.demo_name_en: (
                    receptor.demo_smiles
                ),
                "نيرماتريلڤير — مثبط Mpro المعتمد" if LANG == "ar" else (
                    "Nirmatrelvir — approved Mpro inhibitor"
                ): (
                    "CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)"
                    "C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C"
                ),
                "أسبرين — مزخرف" if LANG == "ar" else "Aspirin — decoy": (
                    "CC(=O)OC1=CC=CC=C1C(=O)O"
                ),
            }
            preset = st.selectbox(
                t(LANG, "dock_preset"), list(preset_labels), key="dock_preset_sel"
            )
            smi = st.text_input(
                t(LANG, "dock_custom"), value=preset_labels[preset], key="dock_smi"
            )
            d1, d2 = st.columns(2)
            n_poses = d1.slider(t(LANG, "dock_nposes"), 3, 10, 5, key="dock_nposes")
            exh = d2.select_slider(
                t(LANG, "dock_exh"), options=[4, 8, 16, 32], value=8, key="dock_exh"
            )

            if st.button(t(LANG, "dock_btn"), type="primary", key="dock_btn"):
                if not (HAS_VINA and HAS_MEEKO):
                    st.warning(t(LANG, "dock_no_engine"))
                with st.status(t(LANG, "dock_status_title"), expanded=True) as status:
                    st.write(t(LANG, "dock_phase1"))
                    prepare_ligand(smi)
                    st.write(t(LANG, "dock_phase2"))
                    st.write(t(LANG, "dock_phase3"))
                    result = dock_ligand(
                        smi, receptor, n_poses=n_poses, exhaustiveness=exh
                    )
                    st.write(t(LANG, "dock_phase4"))
                    status.update(
                        label=t(LANG, "dock_done"), state="complete", expanded=False
                    )
                st.session_state["dock_res"] = result
                st.session_state["dock_meta"] = {"smiles": smi, "rec_id": receptor.id}

            res = st.session_state.get("dock_res")
            meta = st.session_state.get("dock_meta")
            if res is not None and meta is not None:
                ml_pic50 = None
                if meta["rec_id"].startswith("7VH8"):
                    try:
                        from core.ml_potency import train_default_model

                        @st.cache_resource(show_spinner=False)
                        def _dock_model():
                            return train_default_model()

                        ml_pic50 = _dock_model().predict(meta["smiles"])["pic50"]
                    except Exception:  # noqa: BLE001 — المقارنة إضافية لا تعطّل العرض
                        ml_pic50 = None

                m1, m2, m3, m4 = st.columns(4)
                m1.metric(
                    t(LANG, "dock_best"),
                    f"{res.best:.2f}" if res.best is not None else "—",
                )
                if ml_pic50 is not None:
                    m2.metric(t(LANG, "dock_ml_pic50"), f"{ml_pic50:.2f}")
                    m3.metric(t(LANG, "dock_dg_est"), f"{pic50_to_dg_kcal(ml_pic50):.2f}")
                    gap = res.best - pic50_to_dg_kcal(ml_pic50)
                    m4.metric(t(LANG, "dock_gap"), f"{gap:+.2f}")
                    st.caption(t(LANG, "dock_compare_caption"))

                st.markdown(f"#### {t(LANG, 'dock_table_title')}")
                en_df = pd.DataFrame(
                    res.energies,
                    columns=["total", "inter", "intra", "torsions", "intra_best"],
                )
                en_df.insert(0, "#", range(1, len(en_df) + 1))
                st.dataframe(
                    en_df,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        c: st.column_config.NumberColumn(c, format="%.2f")
                        for c in en_df.columns[1:]
                    },
                )

                # ── المحلل الداخلي للبوزات (S7-a) — محرك تسجيل ثانٍ صنعناه محلياً ──
                st.markdown(f"#### {t(LANG, 'dock_contacts_title')}")
                st.caption(t(LANG, "dock_contacts_caption"))
                try:
                    from core.contacts import LESSON as CONTACT_LESSON
                    from core.contacts import score_poses

                    c_rows = score_poses(receptor.receptor_file_path, res.poses_pdbqt)
                    df_c = pd.DataFrame(
                        [
                            r.to_row(
                                pose_index=i + 1,
                                vina_kcal=(
                                    res.scores[i] if i < len(res.scores) else None
                                ),
                            )
                            for i, r in enumerate(c_rows)
                        ]
                    ).rename(
                        columns={
                            "vina": t(LANG, "col_vina"),
                            "contacts": t(LANG, "col_contacts"),
                            "hbonds": t(LANG, "col_hbonds"),
                            "hydrophobic": t(LANG, "col_hydro"),
                            "clashes": t(LANG, "col_clashes"),
                            "inhouse": t(LANG, "col_inhouse"),
                        }
                    )
                    st.dataframe(df_c, hide_index=True, width="stretch")
                    with st.expander(t(LANG, "dock_contacts_lesson"), expanded=False):
                        st.markdown(
                            CONTACT_LESSON.get(LANG, CONTACT_LESSON["ar"])
                        )
                except Exception:  # noqa: BLE001 — التحليل إضافي لا يُعطّل العرض
                    st.info(t(LANG, "dock_contacts_fail"))

                st.markdown(f"#### {t(LANG, 'dock_3d_title')}")
                st.html(
                    build_3d_html(
                        receptor.receptor_file_path,
                        res.best_pose_pdb(),
                        div_id=f"dock3d-{uuid.uuid4().hex[:8]}",
                    )
                )

                dl1, dl2 = st.columns(2)
                dl1.download_button(
                    t(LANG, "dock_dl_pdb"),
                    res.best_pose_pdb(),
                    file_name="best_pose.pdb",
                    mime="chemical/x-pdb",
                    key="dock_dl_pdb",
                    width="stretch",
                )
                dl2.download_button(
                    t(LANG, "dock_dl_pdbqt"),
                    "\n".join(res.poses_pdbqt),
                    file_name="all_poses.pdbqt",
                    mime="chemical/x-pdbqt",
                    key="dock_dl_pdbqt",
                    width="stretch",
                )

                # ── تحقق خارجي اختياري عبر Boltz-2 (S7-b) — opt-in بمفتاح المستخدم فقط ──
                with st.expander(t(LANG, "boltz_title"), expanded=False):
                    st.caption(t(LANG, "boltz_caption"))
                    from core.clients import japanfold

                    seq = st.text_area(t(LANG, "boltz_seq"), key="boltz_seq", height=110)
                    if st.button(t(LANG, "boltz_btn"), key="boltz_btn"):
                        if not seq.strip():
                            st.info(t(LANG, "boltz_empty"))
                        elif japanfold.get_api_key() is None:
                            st.info(t(LANG, "boltz_no_key"))
                        else:
                            with st.spinner(t(LANG, "boltz_running")):
                                fields, reason, _job = japanfold.boltz2_affinity(seq, smi)
                            if fields:
                                st.success(t(LANG, "boltz_done"))
                                st.dataframe(
                                    pd.DataFrame(
                                        [
                                            {"field": k, "value": round(v, 4)}
                                            for k, v in fields.items()
                                        ]
                                    ),
                                    hide_index=True,
                                    width="stretch",
                                )
                            else:
                                st.warning(t(LANG, "boltz_fail").format(reason=reason))
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في Docking: {e}")

# ═══ Tab 11: PGx — الجينوم الدوائي ═══
with tabs[11]:
    st.subheader(t(LANG, "pgx_title"))
    st.caption(t(LANG, "pgx_caption"))
    try:
        from core.pgx import DISCLAIMER_AR, DISCLAIMER_EN, GENES, recommendations_df

        gene_id = st.selectbox(t(LANG, "pgx_gene"), list(GENES), key="pgx_gene")
        gene = GENES[gene_id]
        dip = st.selectbox(
            t(LANG, "pgx_diplotype"), list(gene.diplotypes), key="pgx_dip"
        )
        phen_en = gene.diplotypes[dip]

        src = st.radio(
            t(LANG, "pgx_source"),
            [t(LANG, "pgx_src_offline"), t(LANG, "pgx_src_live")],
            key="pgx_src",
            horizontal=True,
        )
        live_rows: list[dict] | None = None
        if src == t(LANG, "pgx_src_live"):
            live_rows = fetch_cpic_cached(gene_id)
            if not live_rows:
                st.info(t(LANG, "pgx_live_empty"))

        st.markdown(f"#### {t(LANG, 'pgx_function')}")
        st.write(gene.function_ar if LANG == "ar" else gene.function_en)
        st.markdown(
            f"**{t(LANG, 'pgx_substrates')}:** {gene.substrates_ar}"
        )
        st.markdown(
            f"**{t(LANG, 'pgx_phenotype_of')}:** `{dip}` → **{phen_en}**"
        )

        df_pgx = recommendations_df(
            gene_id, dip, lang=LANG, live_rows=live_rows
        )
        st.markdown(
            "#### "
            + t(LANG, "pgx_table_title").format(gene=gene_id, diplotype=dip)
        )
        st.dataframe(df_pgx, hide_index=True, width="stretch")

        st.warning(DISCLAIMER_AR if LANG == "ar" else DISCLAIMER_EN)
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في PGx: {e}")


def _ersilia_cached(smiles_tuple: tuple[str, ...], model_id: str) -> list:
    """كاش جلسة صريح — النجاحات فقط تُخزَّن، والفشل يُعاد نداؤه لاحقاً
    (حتى لا يبقى المستخدم عالقاً في الاحتياطي بعد تشغيل الخادم)."""
    from core.clients.ersilia_client import predict_admet_batch

    cache: dict = st.session_state.setdefault("admet_cache", {})
    key = (model_id, smiles_tuple)
    if key in cache:
        return cache[key]
    rows = predict_admet_batch(list(smiles_tuple), model_id)
    if rows:
        cache[key] = rows
    return rows


# ═══ Tab 12: ADMET Hub — Ersilia Model Hub ═══
with tabs[12]:
    st.subheader(t(LANG, "admet_title"))
    st.caption(t(LANG, "admet_caption"))
    try:
        from core.clients import ersilia_client as ers

        with st.expander(t(LANG, "admet_lesson_title"), expanded=False):
            st.markdown(
                ers.ADMET_LESSON.get(LANG, ers.ADMET_LESSON["ar"]).format(
                    hlow="0.1", hhigh="0.3", sgood="-2", sbad="-4"
                )
            )

        model_opts = {
            (m.name_ar if LANG == "ar" else m.name_en): mid
            for mid, m in ers.MODELS.items()
        }
        model_label = st.selectbox(t(LANG, "admet_model"), list(model_opts), key="admet_model")
        model_id = model_opts[model_label]

        presets = {
            "أسبرين — مرجعية تاريخية": "CC(=O)OC1=CC=CC=C1C(=O)O",
            "باراسيتامول — ذوبان جيد": "CC(=O)NC1=CC=C(C=C1)O",
            "تيرفينادين — سُحب بسبب hERG": (
                "CC(C)(C)C1=CC=C(C=C1)C(CCCN2CCC(CC2)C(C3=CC=CC=C3)"
                "(C4=CC=CC=C4)O)O"
            ),
            "إيتراكونازول — ضعيف الذوبان": (
                "CCC(C)N1C(=O)N(C=N1)C2=CC=C(C=C2)N3CCN(CC3)C4=CC=C(C=C4)"
                "OCC5COC(O5)(CN6C=NC=N6)C7=C(C=C(C=C7)Cl)Cl"
            ),
        }
        if "admet_input" not in st.session_state:
            st.session_state["admet_input"] = "\n".join(presets.values())
        if st.button(t(LANG, "admet_preset"), key="admet_fill"):
            st.session_state["admet_input"] = "\n".join(presets.values())
        smi_text = st.text_area(
            t(LANG, "admet_input"), key="admet_input", height=140
        )

        if st.button(t(LANG, "admet_btn"), type="primary", key="admet_btn"):
            raw = [s.strip() for s in smi_text.splitlines() if s.strip()]
            valid: list[str] = []
            invalid: list[str] = []
            if HAS_RDKIT:
                from rdkit import Chem

                for s in raw:
                    if Chem.MolFromSmiles(s) is not None:
                        valid.append(s)
                    else:
                        invalid.append(s)
            else:
                valid = raw
            if invalid:
                st.warning(
                    t(LANG, "admet_invalid").format(bad=", ".join(invalid[:3]))
                )
            if not valid:
                st.info(t(LANG, "admet_empty"))
            else:
                rows = _ersilia_cached(tuple(valid), model_id)
                if rows:
                    st.markdown(f"#### {t(LANG, 'admet_table_title')}")
                    df = pd.DataFrame(
                        [
                            {
                                "SMILES": r.smiles,
                                t(LANG, "admet_col_value"): round(r.value, 3),
                                t(LANG, "admet_col_verdict"): (
                                    r.verdict_ar if LANG == "ar" else r.verdict_en
                                ),
                            }
                            for r in rows
                        ]
                    )
                    st.dataframe(df, hide_index=True, width="stretch")
                else:
                    st.info(t(LANG, "admet_no_server"))
                    with st.expander(t(LANG, "admet_server_hint"), expanded=False):
                        st.markdown(
                            ers.SERVER_HINT_AR if LANG == "ar" else ers.SERVER_HINT_EN
                        )
                    st.markdown(f"#### {t(LANG, 'admet_ref_title')}")
                    st.dataframe(
                        pd.DataFrame(ers.fallback_reference_df(model_id, LANG)),
                        hide_index=True,
                        width="stretch",
                    )

        st.warning(
            ers.DISCLAIMER_AR if LANG == "ar" else ers.DISCLAIMER_EN
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في ADMET: {e}")
