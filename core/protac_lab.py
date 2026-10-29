"""
مختبر PROTAC — Vepdegestrant
"""
import numpy as np

from core import palette

try:
    import plotly.graph_objects as go
except ImportError:
    go = None
try:
    import streamlit as st
except ImportError:
    st = None


def degradation_fraction(conc, dc50, dmax, kd_tern=1.0, kd_bin=100.0):
    c = np.asarray(conc, dtype=float)
    ternary = c / (kd_tern + c + (c ** 2) / kd_bin)
    t_max = ternary.max() if len(ternary) > 1 else 1
    normalized = ternary / t_max if t_max > 0 else ternary
    return dmax * normalized * (c / (dc50 + c))


def ternary_fraction(conc, kd_tern=1.0, kd_bin=100.0):
    c = np.asarray(conc, dtype=float)
    t = c / (kd_tern + c + (c ** 2) / kd_bin)
    t_max = t.max() if len(t) > 1 else 1
    return 100 * t / t_max if t_max > 0 else t


def traditional_inhibition(conc, dc50, dmax):
    c = np.asarray(conc, dtype=float)
    return dmax * c / (dc50 + c)


def render():  # pragma: no cover
    st.header("🧬 المختبر 04 — PROTAC: تدمير البروتين")
    st.markdown(
        "**Vepdegestrant** — أول PROTAC معتمد من FDA (مايو 2026). "
        "يعمل بتكوين معقد ثلاثي (ERα-PROTAC-CRBN) → يوبيكويتين → تحلل."
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ معاملات PROTAC")
    dc50 = st.sidebar.number_input("DC50 (nM)", 0.01, 1000.0, 0.94, 0.1)
    dmax = st.sidebar.slider("Dmax (%)", 20, 100, 95, 5)
    kd_bin = st.sidebar.number_input("Kd,binary (nM)", 10.0, 10000.0, 100.0, 10.0)

    conc = np.logspace(-2, 5, 300)
    deg_vep = degradation_fraction(conc, dc50, dmax, kd_tern=1.0, kd_bin=kd_bin)
    deg_fulv = traditional_inhibition(conc, dc50=10.0, dmax=60.0)
    tern = ternary_fraction(conc, kd_tern=1.0, kd_bin=kd_bin)

    peak_idx = np.argmax(tern)
    peak_conc = float(conc[peak_idx])

    st.subheader("📈 منحنى الجرعة-الاستجابة")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=conc, y=deg_vep, mode='lines',
                             name='Vepdegestrant (PROTAC)',
                             line={"color": palette.BLUE, "width": 3}))
    fig.add_trace(go.Scatter(x=conc, y=deg_fulv, mode='lines',
                             name='Fulvestrant (مثبط)',
                             line={"color": palette.RED, "width": 2, "dash": 'dash'}))
    fig.add_trace(go.Scatter(x=conc, y=tern, mode='lines',
                             name='المعقد الثلاثي (%)',
                             line={"color": palette.PURPLE, "width": 2},
                             yaxis='y2'))
    fig.add_vline(x=dc50, line_dash="dot", line_color=palette.BLUE, opacity=0.5)
    fig.add_vline(x=peak_conc, line_dash="dot", line_color=palette.PURPLE, opacity=0.5)
    fig.update_layout(
        xaxis={"title": "التركيز (nM)", "type": "log"},
        yaxis={"title": "نسبة التحلل (%)", "range": [-5, 105]},
        yaxis2={"title": "المعقد الثلاثي (%)", "overlaying": 'y', "side": 'right', "range": [-5, 105]},
        template="plotly_white", height=500,
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("📊 المؤشرات")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("DC50", f"{dc50} nM")
    col2.metric("Dmax", f"{dmax}%")
    col3.metric("قمة Hook", f"{peak_conc:.0f} nM")
    col4.metric("أقصى تحلل", f"{deg_vep.max():.1f}%")

    st.subheader("📋 PROTAC vs مثبط تقليدي")
    st.dataframe({
        'الخاصية': ['الآلية', 'DC50', 'Dmax', 'Hook Effect'],
        'Fulvestrant': ['سد الموقع', '10 nM', '60%', 'لا'],
        'Vepdegestrant': ['تدمير البروتين', f'{dc50} nM', f'{dmax}%',
                          f'نعم ({peak_conc:.0f} nM)'],
    }, width="stretch", hide_index=True)

    with st.expander("💡 ما هو Hook Effect؟"):
        st.markdown(f"""
        **Hook Effect** ظاهرة فريدة في PROTACs: عند التركيز العالي جدًا،
        يكوّن PROTAC **ثنائيات** بدلًا من **ثلاثيات**، فتنخفض الفعالية.

        - قمة Hook عند **{peak_conc:.0f} nM** (≈ {peak_conc / dc50:.0f}× DC50)
        - فوق ذلك: جرعات أعلى قد تكون أقل فعالية
        """)

    with st.expander("🏥 التطبيق السريري — Veritac-2"):
        st.markdown("""
        - **المؤشر:** سرطان الثدي ER+/HER2− مع طفرة ESR1
        - **الجرعة:** 200 mg فمويًا مرة يوميًا
        - **المصدر:** FDA NDA 2026-05-01
        """)

    st.caption("📚 FDA NDA 2026-05-01؛ *J Med Chem* 2026 (PMID: 42489504)")
