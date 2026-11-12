"""Pharma SDL — Streamlit Web Application."""
import importlib.util
import json
import logging
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from core import palette
from core.i18n import t

# Check RDKit availability (not available on Stlite/WASM)
HAS_RDKIT = importlib.util.find_spec("rdkit") is not None


def _sync_preset_to_input(select_key: str, input_key: str, presets: dict[str, str]):
    """ربط صادق بين قائمة الأمثلة وحقل الإدخال (تدقيق UX 2026-11).

    Streamlit يتجاهل `value=` لحقل نصي إذا وُجدت قيمة سابقة في
    `session_state` — فتتغير القائمة المحددة بلا تغيّر النص المُحلَّل
    فعلياً (نتيجة خاطئة صامتة على المستخدم). الربط عبر `on_change`
    يعيد السلوك المتوقع: اختيار مثال ⇒ النص يتبعه حرفياً.
    """

    def _on_change() -> None:
        st.session_state[input_key] = presets[st.session_state[select_key]]

    return _on_change

st.set_page_config(page_title="Pharma SDL — مختبر الفارما الذاتي", page_icon="🧬", layout="wide")

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

# ── RTL للوضع العربي (تدقيق UX — P-1): مواءمة الويب مع manifest.json وتقارير PDF ──
if LANG == "ar":
    st.markdown(
        """
<style>
  html, body, [data-testid='stApp'] { direction: rtl; text-align: right; }
  [data-testid='stCode'], [data-testid='stMarkdownContainer'] code,
  [data-testid='stMarkdownContainer'] pre { direction: ltr; text-align: left; }
  [data-testid='stMetric'] { text-align: right; }
  [data-testid='stMetricLabel'] p { text-align: right; }
</style>
""",
        unsafe_allow_html=True,
    )

st.title(t(LANG, "app_title"))
st.markdown(t(LANG, "app_tagline"))

# ═══════════════════════════════════════════════════════════
# التحذير العلمي/الطبي — عقد صدق (تدقيق P0): ظاهر في الواجهة دائماً،
# وليس في التوثيق فقط. المصدر الواحد: pharma_sdl.scores
# ═══════════════════════════════════════════════════════════
from pharma_sdl.scores import disclaimer_md, lanes_legend_md  # عقد صدق خالص stdlib

st.error(disclaimer_md(LANG), icon="⚠️")

# ═══════════════════════════════════════════════════════════
# توجيه بيئة stlite (متصفح/WASM) — رسالة صريحة بدل أخطاء استيراد غامضة
# ═══════════════════════════════════════════════════════════
from core.runtime import is_stlite  # استيراد موضعي بعد إعداد الصفحة

if is_stlite():
    st.warning(t(LANG, "stlite_title"))
    st.markdown(t(LANG, "stlite_body"))


# ═══════════════════════════════════════════════════════════
# التبويبات — 4 مجموعات بدل شريط مسطح واحد من 13 تبويباً
# (تدقيق UX §4.6/P-3: يخفف كلفة المسح البصري ويمنح كل سياق بابه)
# ═══════════════════════════════════════════════════════════

st.header(t(LANG, "lab_header"))

st.caption(t(LANG, "group_pipeline"))
g_pipeline = st.tabs([
    "🏭 Make",
    "🔬 Test",
    "🧠 Analyze",
    "🧬 PROTAC",
])

st.caption(t(LANG, "group_labs"))
g_labs = st.tabs([
    "💊 MIC Lab",
    "🎯 PROTAC Lab",
    "🧫 CYP2C19",
    t(LANG, "tab_pgx"),
    t(LANG, "tab_global"),
])

st.caption(t(LANG, "group_tools"))
g_tools = st.tabs([
    "🔌 PubChem",
    "🤖 Predict",
    t(LANG, "tab_docking"),
])

st.caption(t(LANG, "group_reports"))
g_reports = st.tabs([
    "🎓 Capstone",
    t(LANG, "tab_admet"),
    t(LANG, "tab_classes"),
    t(LANG, "tab_validation"),
])

# خريطة مواضع محتوى التبويبات القديمة (tabs[0..13]) إلى المجموعات الجديدة:
#   0 Make→pipeline[0] · 1 Test→pipeline[1] · 2 Analyze→pipeline[2] · 3 PROTAC→pipeline[3]
#   4 MIC→labs[0] · 5 PROTAC Lab→labs[1] · 6 PubChem→tools[0] · 7 CYP→labs[2]
#   8 Predict→tools[1] · 9 Capstone→reports[0] · 10 Docking→tools[2]
#  11 PGx→labs[3] · 12 ADMET→reports[1] · 13 Classes (ATC/S10)→reports[2]
#  + P15: Global Health→labs[4] · v0.18: External Validation→reports[3]

# ═══ Tab 0: Make ═══
with g_pipeline[0]:
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
        from core.viz import render_png

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
                        png = render_png(cand.smiles, size=240)
                        if png is not None:
                            st.image(png, caption=cand.smiles)
                        else:  # بيئة بلا Cairo → النص بديلاً صادقاً
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
with g_pipeline[1]:
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
with g_pipeline[2]:
    st.subheader("تحليل Pareto")
    st.info("استخدم مختبر MIC/PROTAC للحصول على نتائج محاكاة كاملة.")
    try:
        from core.agent import MultiObjectiveAgent

        _agent = MultiObjectiveAgent
        st.write("✅ وكيل التعلم النشط متاح")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 3: PROTAC (overview) ═══
with g_pipeline[3]:
    st.subheader("PROTAC — نظرة عامة")
    st.write("Vepdegestrant (Veppanu) — أول PROTAC معتمد (FDA 2026-05-01)")
    try:
        from core.protac import VEPDEGESTRANT

        st.write(f"DC50 = {VEPDEGESTRANT.dc50} nM")
        st.write(f"Dmax = {VEPDEGESTRANT.dmax}%")
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")

# ═══ Tab 4: MIC Lab ═══
with g_labs[0]:
    try:
        from core.mic_lab import render as render_mic

        render_mic()
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في MIC Lab: {e}")

# ═══ Tab 5: PROTAC Lab ═══
with g_labs[1]:
    try:
        from core.protac_lab import render as render_protac

        render_protac()
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في PROTAC Lab: {e}")

# ═══ Tab 6: PubChem ═══
with g_tools[0]:
    st.subheader("🔌 PubChem")
    try:
        query = st.text_input("اسم الدواء", value="aspirin", key="pubchem_q")
        if st.button("بحث", key="pubchem_btn"):
            with st.spinner("جاري البحث..."):
                # تدقيق UX (P-2): تُخزَّن النتيجة فتبقى بعد إعادة الرسم وتبديل اللغة/التبويب
                st.session_state["pubchem_res"] = fetch_drug_cached(query)
                st.session_state["pubchem_q_done"] = query

        data = st.session_state.get("pubchem_res", "__unset__")
        if data == "__unset__":
            st.info("ابحث عن دواء لعرض خصائصه — النتائج تبقى ظاهرة أثناء تنقلك بين التبويبات.")
        elif data:
            st.caption(f"نتائج البحث عن: `{st.session_state.get('pubchem_q_done', '')}`")
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
with g_labs[2]:
    try:
        from core.cyp2c19_lab import render as render_cyp

        render_cyp()
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في CYP2C19: {e}")

# ═══ Tab 8: Predict — من الاستعلام إلى التنبؤ ═══
with g_tools[1]:
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
        sel = st.selectbox(
            "أمثلة جاهزة",
            list(PRESETS),
            key="pred_sel",
            on_change=_sync_preset_to_input("pred_sel", "pred_smi", PRESETS),
        )
        smi = st.text_input("أو الصق SMILES الخاص بك", value=PRESETS[sel], key="pred_smi")

        if st.button("تنبؤ", key="pred_btn", type="primary"):
            try:
                # تدقيق UX (P-2): النتيجة تُخزَّن فلا تُمسح عند أي إعادة رسم
                st.session_state["pred_res"] = model.predict(smi)
                st.session_state["pred_smi_done"] = smi
            except ValueError as ve:
                st.session_state.pop("pred_res", None)
                st.error(f"⚠️ {ve}")

        res = st.session_state.get("pred_res")
        if res is not None:
            st.caption(f"نتيجة التنبؤ لـ: `{st.session_state.get('pred_smi_done', '')}`")
            try:
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
                    marker_color=palette.PRIMARY, orientation="h", name="تنبؤ",
                )
                for i, row in enumerate(top3.itertuples(), 1):
                    fig.add_bar(
                        y=[f"أقوى مثبط حقيقي #{i}"], x=[row.pchembl_value],
                        marker_color=palette.TEAL, orientation="h", name="قياس",
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
                **palette.MODEL_COLORS,
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
with g_reports[0]:
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

                live = st.empty()
                live.write("**2/5–4/5** ⏳ فلترة ADME + تنبؤ الفعالية + تحليل PK/PD — قيد التنفيذ…")
                res = run_pipeline(lib, dose_mg=dose, source=source, model=_capstone_model())
                live.write("**2/5–4/5** ✅ اكتملت الفلترة والتنبؤ وتحليل PK/PD")
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
                color_continuous_scale=[palette.PRIMARY_SOFT, palette.PRIMARY],
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
            st.caption(
                "🧭 عمود pIC50 هنا = مسار «الفعالية المتنبأ بها (ML)» — ليس قياساً تجريبياً؛ "
                "القياس التجريبي مسار مستقل من ChEMBL، ودرجة الالتحام مسار ثالث منفصل."
            )
            with st.expander("🧭 مسارات الدرجات الثلاثة — كيف تُقرأ الأرقام؟"):
                st.markdown(lanes_legend_md(LANG))
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
                    "pkpd_icon": st.column_config.TextColumn("الرمز"),
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
                    mode="lines", line={"color": palette.PRIMARY, "width": 3},
                    showlegend=False, hoverinfo="skip",
                )
                fig_ci.add_scatter(
                    x=[r.ci_lo, r.ci_hi], y=[i, i], mode="lines",
                    line={"color": palette.TEAL, "width": 6}, showlegend=False,
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
with g_tools[2]:
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
                t(LANG, "dock_preset"),
                list(preset_labels),
                key="dock_preset_sel",
                on_change=_sync_preset_to_input(
                    "dock_preset_sel", "dock_smi", preset_labels
                ),
            )
            smi = st.text_input(
                t(LANG, "dock_custom"), value=preset_labels[preset], key="dock_smi"
            )
            d1, d2 = st.columns(2)
            n_poses = d1.slider(t(LANG, "dock_nposes"), 3, 10, 5, key="dock_nposes")
            exh = d2.select_slider(
                t(LANG, "dock_exh"), options=[4, 8, 16, 32], value=8, key="dock_exh"
            )

            dock_run = st.button(t(LANG, "dock_btn"), type="primary", key="dock_btn")
            if dock_run and not (HAS_VINA and HAS_MEEKO):
                st.warning(t(LANG, "dock_no_engine"))
            if dock_run and (HAS_VINA and HAS_MEEKO):
                with st.status(t(LANG, "dock_status_title"), expanded=True) as status:
                    st.write(t(LANG, "dock_phase1"))
                    # prepare_ligand يُستدعى داخل dock_ligand ذاته — استدعاء
                    # مكرر هنا كان يضاعف Embed 3D+MMFF (أغلى خطوة في المسار).
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
                st.caption(
                    "🧭 درجات هذا الجدول من مسار «الالتحام» حصراً (kcal/mol) — "
                    "لا تُقارن بدرجات بروتين آخر ولا تُقرأ كفعالية."
                )
                with st.expander("🧭 مسارات الدرجات الثلاثة — كيف تُقرأ الأرقام؟"):
                    st.markdown(lanes_legend_md(LANG))
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
with g_labs[3]:
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


# ═══ Tab: Global Health (P15) ═══
with g_labs[4]:
    st.subheader(t(LANG, "gh_title"))
    st.caption(t(LANG, "gh_caption"))
    try:
        from core import global_health as gh
        from core.clients import ersilia_client as ers

        card_opts = {
            (c.name_ar if LANG == "ar" else c.name_en): pid
            for pid, c in gh.PATHOGENS.items()
        }
        card_label = st.selectbox(
            t(LANG, "gh_pathogen"), list(card_opts), key="gh_pathogen"
        )
        card = gh.PATHOGENS[card_opts[card_label]]
        model = ers.MODELS[card.model_id]

        st.info(
            t(LANG, "gh_burden").format(
                year=card.who_year,
                cases=card.who_cases,
                deaths=card.who_deaths,
                source=(card.who_source_ar if LANG == "ar" else card.who_source_en),
            ),
            icon="🌍",
        )

        with st.expander(t(LANG, "gh_lesson_title"), expanded=False):
            st.markdown(gh.trust_lesson(LANG))
        with st.expander(
            f"🧬 {t(LANG, 'gh_model_card')} — {card.model_id}", expanded=False
        ):
            st.markdown(
                f"- **{t(LANG, 'gh_pathogen')}:** "
                f"{card.agent_ar if LANG == 'ar' else card.agent_en}\n"
                f"- **{model.endpoint}:** `{card.endpoint}` — "
                f"{model.unit_ar if LANG == 'ar' else model.unit_en}\n"
                f"- **License:** GPL-3.0 (package) · MIT (model)"
            )

        if "gh_input" not in st.session_state:
            st.session_state["gh_input"] = "\n".join(gh.GLOBAL_PRESETS.values())
        if st.button(t(LANG, "gh_preset"), key="gh_fill"):
            st.session_state["gh_input"] = "\n".join(gh.GLOBAL_PRESETS.values())
        gh_smi_text = st.text_area(t(LANG, "gh_input"), key="gh_input", height=140)

        if st.button(t(LANG, "gh_btn"), type="primary", key="gh_btn"):
            gh_raw = [s.strip() for s in gh_smi_text.splitlines() if s.strip()]
            gh_valid: list[str] = []
            gh_invalid: list[str] = []
            if HAS_RDKIT:
                from rdkit import Chem

                for s in gh_raw:
                    if Chem.MolFromSmiles(s) is not None:
                        gh_valid.append(s)
                    else:
                        gh_invalid.append(s)
            else:
                gh_valid = gh_raw
            if gh_invalid:
                st.warning(
                    t(LANG, "gh_invalid").format(bad=", ".join(gh_invalid[:3]))
                )
            if not gh_valid:
                st.info(t(LANG, "gh_empty"))
            else:
                # تدقيق UX (P-2): النتائج تبقى بعد أي إعادة رسم
                st.session_state["gh_rows"] = [
                    gh.assess_candidate(s, card.pathogen_id) for s in gh_valid
                ]

        if "gh_rows" in st.session_state:
            gh_rows = st.session_state["gh_rows"]
            gh_live = [r for r in gh_rows if r.status == "live"]
            if not gh_live:
                st.info(t(LANG, "gh_no_server"))
                with st.expander(t(LANG, "gh_server_hint"), expanded=False):
                    st.text(
                        ers.SERVER_HINT_AR if LANG == "ar" else ers.SERVER_HINT_EN
                    )
                st.markdown(f"#### {t(LANG, 'gh_ref_title')}")
                st.dataframe(
                    pd.DataFrame(ers.fallback_reference_df(card.model_id, LANG)),
                    hide_index=True,
                    width="stretch",
                )
            st.markdown(f"#### {t(LANG, 'gh_table_title')}")
            st.dataframe(
                pd.DataFrame(gh.panel_df(gh_rows, LANG)),
                hide_index=True,
                width="stretch",
            )

            # ── القمع: نشاط الممرض + بوابة ADMET الحية من نفس الخادم ──
            gh_verdicts = []
            for r in gh_rows:
                herg_v = logs_v = None
                if r.status == "live":
                    h = ers.predict_admet(r.smiles, "eos2ta5")
                    herg_v = h.value if h else None
                    l = ers.predict_admet(r.smiles, "eos6oli")
                    logs_v = l.value if l else None
                gh_verdicts.append(
                    gh.funnel_decision(card.pathogen_id, r.value, herg_v, logs_v)
                )
            st.markdown(f"#### {t(LANG, 'gh_funnel_title')}")
            st.caption(t(LANG, "gh_funnel_caption"))
            st.dataframe(
                pd.DataFrame(gh.funnel_df(gh_verdicts, LANG)),
                hide_index=True,
                width="stretch",
            )
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في الصحة العالمية: {e}")


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


ADMET_PRESETS: dict[str, str] = {
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


def _render_ersilia_engine(lang: str, presets: dict[str, str]) -> None:
    """مسار Ersilia — نموذجان حيان عبر خادم محلي."""
    try:
        from core.clients import ersilia_client as ers

        with st.expander(t(lang, "admet_lesson_title"), expanded=False):
            st.markdown(
                ers.ADMET_LESSON.get(lang, ers.ADMET_LESSON["ar"]).format(
                    hlow="0.1", hhigh="0.3", sgood="-2", sbad="-4"
                )
            )

        model_opts = {
            (m.name_ar if lang == "ar" else m.name_en): mid
            for mid, m in ers.MODELS.items()
        }
        model_label = st.selectbox(t(lang, "admet_model"), list(model_opts), key="admet_model")
        model_id = model_opts[model_label]

        if "admet_input" not in st.session_state:
            st.session_state["admet_input"] = "\n".join(presets.values())
        if st.button(t(lang, "admet_preset"), key="admet_fill"):
            st.session_state["admet_input"] = "\n".join(presets.values())
        smi_text = st.text_area(
            t(lang, "admet_input"), key="admet_input", height=140
        )

        if st.button(t(lang, "admet_btn"), type="primary", key="admet_btn"):
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
                    t(lang, "admet_invalid").format(bad=", ".join(invalid[:3]))
                )
            if not valid:
                st.info(t(lang, "admet_empty"))
            else:
                # تدقيق UX (P-2): النتائج تبقى بعد أي إعادة رسم
                st.session_state["admet_rows"] = _ersilia_cached(tuple(valid), model_id)

        if "admet_rows" in st.session_state:
            rows = st.session_state["admet_rows"]
            if rows:
                st.markdown(f"#### {t(lang, 'admet_table_title')}")
                df = pd.DataFrame(
                    [
                        {
                            "SMILES": r.smiles,
                            t(lang, "admet_col_value"): round(r.value, 3),
                            t(lang, "admet_col_verdict"): (
                                r.verdict_ar if lang == "ar" else r.verdict_en
                            ),
                        }
                        for r in rows
                    ]
                )
                st.dataframe(df, hide_index=True, width="stretch")
            else:
                st.info(t(lang, "admet_no_server"))
                with st.expander(t(lang, "admet_server_hint"), expanded=False):
                    st.markdown(
                        ers.SERVER_HINT_AR if lang == "ar" else ers.SERVER_HINT_EN
                    )
                st.markdown(f"#### {t(lang, 'admet_ref_title')}")
                st.dataframe(
                    pd.DataFrame(ers.fallback_reference_df(model_id, lang)),
                    hide_index=True,
                    width="stretch",
                )

        st.warning(
            ers.DISCLAIMER_AR if lang == "ar" else ers.DISCLAIMER_EN
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في ADMET: {e}")


def _render_admetai_engine(lang: str, presets: dict[str, str]) -> None:
    """محرك ADMET-AI المحلي (P13) — 41 نقطة نهاية + مئينات DrugBank بلا شبكة."""
    try:
        from core.clients import admet_ai_client as aic

        st.caption(t(lang, "admetai_caption"))
        with st.expander(t(lang, "admetai_lesson_title"), expanded=False):
            st.markdown(
                aic.ADMET_AI_LESSON.get(lang, aic.ADMET_AI_LESSON["ar"]).format(
                    n=aic.N_ML_TASKS
                )
            )

        if not aic.is_available():
            st.info(t(lang, "admetai_not_available"))
            with st.expander(t(lang, "admetai_install_hint"), expanded=False):
                st.markdown(
                    aic.INSTALL_HINT_AR if lang == "ar" else aic.INSTALL_HINT_EN
                )
            return

        presets3 = list(presets.values())[:3]
        if "admetai_input" not in st.session_state:
            st.session_state["admetai_input"] = "\n".join(presets3)
        if st.button(t(lang, "admet_preset"), key="admetai_fill"):
            st.session_state["admetai_input"] = "\n".join(presets3)
        smi_text = st.text_area(
            t(lang, "admet_input"), key="admetai_input", height=140
        )

        if st.button(t(lang, "admetai_btn"), type="primary", key="admetai_btn"):
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
                    t(lang, "admet_invalid").format(bad=", ".join(invalid[:3]))
                )
            if not valid:
                st.info(t(lang, "admet_empty"))
            else:
                with st.spinner(t(lang, "admet_status")):
                    st.session_state["admetai_results"] = aic.predict_admet_ai_batch(valid)

        if "admetai_results" not in st.session_state:
            return
        results = st.session_state["admetai_results"]
        if not results:
            st.info(t(lang, "admetai_no_rows"))
            return

        st.markdown(f"#### {t(lang, 'admetai_results_title')}")
        families = sorted(
            {(t_.family_ar if lang == "ar" else t_.family_en) for t_ in aic.TASKS.values()}
        )
        fam_all = t(lang, "admetai_family_all")
        fam_choice = st.selectbox(
            t(lang, "admetai_family_filter"),
            [fam_all] + families,
            key="admetai_family",
        )

        for idx, res in enumerate(results, 1):
            label = (
                f"🧬 جزيء {idx}/{len(results)} — {res.smiles[:42]}"
                if lang == "ar"
                else f"🧬 Molecule {idx}/{len(results)} — {res.smiles[:42]}"
            )
            with st.expander(label, expanded=(idx == 1)):
                ml_rows: list[dict] = []
                ph_rows: list[dict] = []
                for tid, val in res.values.items():
                    task = aic.TASKS.get(tid)
                    if task is None:
                        continue  # عمود مجهول — لا تزييف تفسير
                    if task.kind == aic.KIND_PHYSCHEM:
                        ph_rows.append(
                            {
                                t(lang, "admetai_col_task"): (
                                    task.name_ar if lang == "ar" else task.name_en
                                ),
                                t(lang, "admetai_col_value"): round(val, 3),
                                t(lang, "admetai_col_unit"): (
                                    task.unit_ar if lang == "ar" else task.unit_en
                                ),
                            }
                        )
                        continue
                    fam = task.family_ar if lang == "ar" else task.family_en
                    if fam_choice != fam_all and fam != fam_choice:
                        continue
                    pct = res.get_percentile(tid)
                    ml_rows.append(
                        {
                            t(lang, "admetai_col_task"): (
                                task.name_ar if lang == "ar" else task.name_en
                            ),
                            t(lang, "admetai_col_family"): fam,
                            t(lang, "admetai_col_value"): round(val, 3),
                            t(lang, "admetai_col_unit"): (
                                task.unit_ar if lang == "ar" else task.unit_en
                            ),
                            t(lang, "admetai_col_pct"): (
                                round(pct, 1) if pct is not None else "—"
                            ),
                            t(lang, "admetai_col_verdict"): aic.verdict(tid, val, lang),
                        }
                    )
                st.dataframe(pd.DataFrame(ml_rows), hide_index=True, width="stretch")
                st.markdown(f"**{t(lang, 'admetai_physchem_title')}**")
                st.dataframe(pd.DataFrame(ph_rows), hide_index=True, width="stretch")

        st.warning(
            aic.DISCLAIMER_AR if lang == "ar" else aic.DISCLAIMER_EN
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في ADMET-AI: {e}")


# ═══ Tab 12: ADMET Hub — Ersilia / ADMET-AI ═══
with g_reports[1]:
    st.subheader(t(LANG, "admet_title"))
    st.caption(t(LANG, "admet_caption"))

    engine_label_admetai = t(LANG, "admet_engine_admetai")
    engine = st.radio(
        t(LANG, "admet_engine"),
        [t(LANG, "admet_engine_ersilia"), engine_label_admetai],
        horizontal=True,
        key="admet_engine",
    )
    if engine == engine_label_admetai:
        _render_admetai_engine(LANG, ADMET_PRESETS)
    else:
        _render_ersilia_engine(LANG, ADMET_PRESETS)

# ═══ Tab 13: التصنيف الدوائي — المعيار العالمي ATC (S10) ═══
with g_reports[2]:
    st.subheader(t(LANG, "cls_title"))
    try:
        from core.drug_classes import CATALOG, atc_live, classify

        st.caption(t(LANG, "cls_caption").format(n=len(CATALOG)))

        cls_mode = st.radio(
            t(LANG, "cls_title"),
            options=["classify", "browse"],
            format_func=lambda m: (
                t(LANG, "cls_btn") if m == "classify" else t(LANG, "cls_browse").format(n=len(CATALOG))
            ),
            label_visibility="collapsed",
            horizontal=True,
            key="cls_mode",
        )

        if cls_mode == "classify":
            cls_query = st.text_input(
                t(LANG, "cls_input"), value="amoxicillin", key="cls_input"
            )
            if st.button(t(LANG, "cls_btn"), type="secondary", key="cls_btn"):
                if not cls_query.strip():
                    st.info(t(LANG, "cls_empty"))
                else:
                    hits = classify(cls_query.strip())
                    if not hits:
                        st.info(t(LANG, "cls_none"))
                    else:
                        hit = hits[0]
                        basis_label = t(LANG, f"cls_basis_{hit.basis}")
                        st.success(t(LANG, "cls_found").format(basis=basis_label))
                        card = hit.card
                        st.markdown(
                            f"**{card.name_ar}** / {card.name_en} — "
                            f"{t(LANG, 'cls_atc')} `{card.atc}`"
                        )
                        st.markdown(f"{t(LANG, 'cls_mech')} {card.mech_ar}")
                        members_txt = " · ".join(f"{en} ({ar})" for en, ar in card.members)
                        st.caption(f"{t(LANG, 'cls_members')} {members_txt}")
                    # خيار ATC الحي — يعمل بلا مفتاح، والفشل لا يعطّل شيئاً
                    if st.button(t(LANG, "cls_live_btn"), key="cls_live_btn"):
                        with st.spinner("⏳ RxNorm…"):
                            codes = atc_live(cls_query.strip())
                        if codes:
                            st.markdown(
                                t(LANG, "cls_live_done").format(drug=cls_query.strip())
                            )
                            st.dataframe(
                                pd.DataFrame(codes, columns=["ATC", "Class"]),
                                hide_index=True,
                                width="stretch",
                            )
                        else:
                            st.info(t(LANG, "cls_live_none"))
        else:
            st.markdown(t(LANG, "cls_browse").format(n=len(CATALOG)))
            for card in CATALOG:
                with st.expander(f"{card.atc} — {card.name_ar} / {card.name_en}"):
                    st.markdown(f"{t(LANG, 'cls_mech')} {card.mech_ar}")
                    members_txt = " · ".join(f"{en} ({ar})" for en, ar in card.members)
                    st.caption(f"{t(LANG, 'cls_members')} {members_txt}")

        with st.expander(t(LANG, "cls_lesson"), expanded=False):
            st.write(t(LANG, "cls_lesson_text"))
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في التصنيف الدوائي: {e}")


# ═══ Tab 14 (v0.18): التحقق الخارجي — بطاقات النماذج + القياس المتبادل ═══
# المبدأ: رقم بلا فترته لا يُقتبس — والنموذج الذي ينشر حدوده يُؤتمن أكثر
# من نموذج يخفيها. القسم الأول يقرأ البطاقة الرسمية من docs/audit (البروتوكول
# المجمَّد)، والقسم الثاني قياس متبادل حي مع ADMETlab 3.0 بفشل لطيف موثّق.


def _admetlab3_cached(smiles_tuple: tuple[str, ...]) -> "object":
    """كاش جلسة صريح — النجاحات فقط تُخزَّن، والفشل يُعاد نداؤه لاحقاً
    (حتى لا يبقى المستخدم عالقاً في رسالة الانقطاع بعد تعافي الخدمة)."""
    from core.clients import admetlab3_client as al3

    cache: dict = st.session_state.setdefault("admetlab3_cache", {})
    if smiles_tuple in cache:
        return cache[smiles_tuple]
    batch = al3.predict_admet_batch(list(smiles_tuple))
    if batch.ok:
        cache[smiles_tuple] = batch
    return batch


with g_reports[3]:
    st.subheader(t(LANG, "val_title"))
    st.caption(t(LANG, "val_caption"))
    try:
        # ── ① بطاقة النموذج المعتمد — من docs/audit (البروتوكول المجمَّد) ──
        st.markdown(f"### {t(LANG, 'val_card_title')}")
        st.caption(t(LANG, "val_card_caption"))
        card_path = Path(__file__).parent / "docs" / "audit" / "model-cards-p18-results.json"
        if card_path.exists():
            card = json.loads(card_path.read_text(encoding="utf-8"))
            rnd = card["model_card_random"]
            scaf = card["model_card_scaffold"]["aggregate"]
            summ = card["honest_summary_ar"]

            cm1, cm2, cm3, cm4 = st.columns(4)
            cm1.metric(
                "R² (عشوائي، seed=42)",
                f'{rnd["metrics"]["r2"]["point"]:.3f}',
                f'CI95 {rnd["metrics"]["r2"]["ci95"]}',
            )
            cm2.metric(
                "R² (هيكلي، 5 بذور)",
                f'{scaf["r2"]["mean"]:.3f}',
                f'± {scaf["r2"]["std"]}',
            )
            cm3.metric(
                "MAE (عشوائي)",
                f'{rnd["metrics"]["mae"]["point"]:.3f}',
                f'CI95 {rnd["metrics"]["mae"]["ci95"]}',
            )
            cm4.metric(t(LANG, "val_gap_label"), f'{summ["generalization_gap"]:+.3f}')

            ad = rnd["applicability_domain"]
            with st.expander(f"🧭 {t(LANG, 'val_ad_title')}", expanded=True):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "المنطقة": "داخل النطاق (قريب من التدريب)",
                                "العدد": ad["inside"]["n"],
                                "النسبة": f'{ad["inside"]["frac"]:.1%}',
                                "R²": ad["inside"]["r2"],
                                "MAE": ad["inside"]["mae"],
                            },
                            {
                                "المنطقة": "خارج النطاق (استقراء)",
                                "العدد": ad["outside"]["n"],
                                "النسبة": f'{ad["outside"]["frac"]:.1%}',
                                "R²": ad["outside"]["r2"],
                                "MAE": ad["outside"]["mae"],
                            },
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
                st.caption(
                    f'العتبة: أعلى تشابه تانيروتو ≥ {ad["threshold"]} مقابل '
                    f'التدريب (المئين {ad["percentile"]} من التشابه الذاتي) — {ad["note_ar"]}'
                )

            with st.expander(f"📉 {t(LANG, 'val_calib_title')}"):
                st.dataframe(pd.DataFrame(rnd["calibration_bins"]), hide_index=True, width="stretch")
                st.caption(t(LANG, "val_calib_note"))
        else:
            st.warning(t(LANG, "val_card_missing"))

        st.divider()

        # ── ② القياس المتبادل الحي — ADMETlab 3.0 (فشل لطيف موثّق) ──
        st.markdown(f"### {t(LANG, 'val_admetlab_title')}")
        from core.clients import admetlab3_client as al3

        val_text = st.text_area(
            t(LANG, "val_smiles_label"),
            value="CC(=O)Oc1ccccc1C(=O)O\nCN1C=NC2=C1C(=O)N(C)C(=O)N2C",
            key="val_smiles",
        )
        smiles_in = [s.strip() for s in val_text.splitlines() if s.strip()][:10]

        vb1, vb2 = st.columns(2)
        if vb1.button(t(LANG, "val_run_btn"), type="primary", key="val_run"):
            if not smiles_in:
                st.info(t(LANG, "val_no_smiles"))
            else:
                with st.spinner("⏳ ADMETlab 3.0…"):
                    batch = _admetlab3_cached(tuple(smiles_in))
                if not batch.ok:
                    st.info(al3.reason_message(batch.reason, LANG))
                else:
                    st.success(
                        t(LANG, "val_ok_status").format(
                            n_valid=batch.n_valid, n_all=batch.n_all
                        )
                    )
                    rows = []
                    for res in batch.results:
                        for key, ep in al3.ENDPOINTS.items():
                            v = res.get(key)
                            if v is not None:
                                rows.append(
                                    {
                                        "SMILES": res.smiles,
                                        "نقطة النهاية": f"{ep.name_ar} ({key})",
                                        "القيمة": v,
                                        "الوحدة": ep.unit_ar,
                                    }
                                )
                    if rows:
                        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

                    # المقارنة الجانبية مع ADMET-AI المحلي إن توفّر — القياس المتبادل
                    ai_rows = []
                    ai_available = False
                    try:
                        from core.clients import admet_ai_client as aic

                        ai_available = bool(aic.is_available())
                        if ai_available:
                            ai_results = aic.predict_admet_ai_batch(smiles_in)
                            ai_by_smiles = {r.smiles: r for r in ai_results}
                            for res in batch.results:
                                ai = ai_by_smiles.get(res.smiles)
                                if ai is None:
                                    continue
                                for key3, task_id in al3.CROSSWALK_TO_ADMET_AI.items():
                                    v3 = res.get(key3)
                                    va = ai.get(task_id)
                                    if v3 is None or va is None:
                                        continue
                                    label = (
                                        aic.TASKS[task_id].name_ar
                                        if task_id in aic.TASKS
                                        else key3
                                    )
                                    ai_rows.append(
                                        {
                                            "SMILES": res.smiles,
                                            "نقطة النهاية": label,
                                            "ADMET-AI (محلي)": round(va, 3),
                                            "ADMETlab 3.0": round(v3, 3),
                                            "الفارق": round(v3 - va, 3),
                                        }
                                    )
                    except Exception:  # المقارنة رفاهية لا أساس — تسجل صمتاً
                        logging.getLogger(__name__).debug(
                            "ADMET-AI crosswalk unavailable", exc_info=True
                        )
                    if ai_rows:
                        st.markdown(
                            f"**{t(LANG, 'val_crosswalk_n').format(n=len(al3.CROSSWALK_TO_ADMET_AI))}**"
                        )
                        st.dataframe(pd.DataFrame(ai_rows), hide_index=True, width="stretch")
                    elif not ai_available:
                        st.caption(t(LANG, "val_admetai_absent"))

        if vb2.button(t(LANG, "val_wash_btn"), key="val_wash"):
            if not smiles_in:
                st.info(t(LANG, "val_no_smiles"))
            else:
                with st.spinner("⏳ washmol…"):
                    cleaned = al3.washmol(smiles_in[0])
                if cleaned:
                    st.success(
                        t(LANG, "val_wash_done").format(orig=smiles_in[0], cleaned=cleaned)
                    )
                else:
                    st.info(t(LANG, "val_wash_none"))

        with st.expander(t(LANG, "val_lesson_title"), expanded=False):
            st.write(
                al3.ADMETLAB3_LESSON[LANG].format(n=len(al3.CROSSWALK_TO_ADMET_AI))
            )
            st.write(al3.DISCLAIMER_AR if LANG == "ar" else al3.DISCLAIMER_EN)
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ في التحقق الخارجي: {e}")
