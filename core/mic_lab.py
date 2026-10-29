"""
مختبر PK/PD للمضادات الحيوية — Streamlit
3 مضادات حيوية، 3 مؤشرات فعالية، 3 حالات سريرية
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


# ═══════════════════════════════════════════════════════════
# البيانات
# ═══════════════════════════════════════════════════════════

DRUGS = {
    'gentamicin': {
        'name': 'الجنتامايسين', 'icon': '🔷',
        'index': 'cmax_mic', 'index_label': 'Cmax/MIC', 'index_target': 10,
        'color': palette.BLUE,
        'dose': 350, 'vd': 17.5, 'cl': 5.25, 'mic': 2.0,
    },
    'ceftriaxone': {
        'name': 'السيفترياكسون', 'icon': '🔶',
        'index': 'ft_mic', 'index_label': 'fT>MIC', 'index_target': 50,
        'color': palette.ORANGE,
        'dose': 2000, 'vd': 10, 'cl': 1.0, 'mic': 1.0,
    },
    'vancomycin': {
        'name': 'الفانكومايسين', 'icon': '🟣',
        'index': 'auc_mic', 'index_label': 'AUC/MIC', 'index_target': 400,
        'color': palette.PURPLE,
        'dose': 1500, 'vd': 50, 'cl': 4.5, 'mic': 1.0,
    },
}


# ═══════════════════════════════════════════════════════════
# المحرك الرياضي
# ═══════════════════════════════════════════════════════════

def compute_pk(dose, vd, cl, t_inf=0.5, t_max=24, n=500):
    """نموذج حجرة واحدة مع تسريب وريدي."""
    k = cl / vd
    t = np.linspace(0, t_max, n)
    c = np.zeros_like(t)

    mask_inf = t <= t_inf
    c[mask_inf] = (dose / (vd * k * t_inf)) * (1 - np.exp(-k * t[mask_inf]))

    c_end = (dose / (vd * k * t_inf)) * (1 - np.exp(-k * t_inf))
    mask_post = t > t_inf
    c[mask_post] = c_end * np.exp(-k * (t[mask_post] - t_inf))

    return t, c


def compute_metrics(t, c, mic, interval=24, index='cmax_mic', target=10):
    """حساب المؤشرات الثلاثة + الحكم."""
    cmax = float(c.max())
    tmax = float(t[c.argmax()])
    auc = float(np.trapezoid(c, t))

    above = c > mic
    if above.any():
        transitions = np.diff(above.astype(int))
        starts = np.where(transitions == 1)[0] + 1
        ends = np.where(transitions == -1)[0] + 1
        if above[0]:
            starts = np.concatenate([[0], starts])
        if above[-1]:
            ends = np.concatenate([ends, [len(above)]])
        ft_h = float(sum(t[e-1] - t[s] for s, e in zip(starts, ends)))
    else:
        ft_h = 0.0
    ft_pct = (ft_h / interval) * 100

    cmax_mic = cmax / mic if mic > 0 else 0
    auc_mic = auc / mic if mic > 0 else 0

    if index == 'cmax_mic':
        value = cmax_mic
    elif index == 'ft_mic':
        value = ft_pct
    else:
        value = auc_mic

    if value >= target:
        verdict = 'active'
    elif value >= target * 0.7:
        verdict = 'warning'
    else:
        verdict = 'failed'

    return {
        'cmax': cmax, 'tmax': tmax, 'auc': auc,
        'ft_h': ft_h, 'ft_pct': ft_pct,
        'cmax_mic': cmax_mic, 'auc_mic': auc_mic,
        'governing_value': value, 'verdict': verdict,
    }


# ═══════════════════════════════════════════════════════════
# واجهة Streamlit
# ═══════════════════════════════════════════════════════════

def render():  # pragma: no cover
    """نقطة الدخول — تُستدعى من app.py."""
    st.header("🧪 المختبر 03 — PK/PD للمضادات الحيوية")
    st.markdown(
        "**السؤال الجوهري:** لماذا نعطي الجنتامايسين مرة يوميًا رغم أن عمر نصفه 2-3 ساعات؟ "
        "**الجواب:** مؤشر الفعالية يختلف."
    )

    drug_keys = list(DRUGS.keys())
    selected = st.selectbox(
        "اختر المضاد الحيوي",
        options=drug_keys,
        format_func=lambda k: f"{DRUGS[k]['icon']} {DRUGS[k]['name']} — {DRUGS[k]['index_label']}",
    )
    drug = DRUGS[selected]

    st.subheader("⚙️ المعاملات")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        dose = st.number_input("الجرعة (mg)", 10, 5000, drug['dose'], 10)
    with col2:
        vd = st.number_input("Vd (L)", 1.0, 200.0, float(drug['vd']), 0.5)
    with col3:
        cl = st.number_input("CL (L/h)", 0.1, 50.0, float(drug['cl']), 0.1)
    with col4:
        mic = st.number_input("MIC (mg/L)", 0.1, 32.0, float(drug['mic']), 0.5)

    t, c = compute_pk(dose, vd, cl)
    m = compute_metrics(t, c, mic, index=drug['index'], target=drug['index_target'])

    st.subheader("📈 منحنى التركيز-الزمن")
    fig = go.Figure()
    above_mask = c > mic
    fig.add_trace(go.Scatter(
        x=t[above_mask], y=c[above_mask],
        fill='tozeroy', fillcolor='rgba(34, 197, 94, 0.25)',
        line={'width': 0}, name='fT>MIC',
    ))
    fig.add_trace(go.Scatter(
        x=t, y=c, mode='lines', name='التركيز',
        line={'color': drug['color'], 'width': 3},
    ))
    fig.add_hline(y=mic, line_dash="dash", line_color="red",
                  annotation_text=f"MIC = {mic} mg/L")
    fig.update_layout(
        xaxis_title="الزمن (ساعة)", yaxis_title="التركيز (mg/L)",
        template="plotly_white", height=450,
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("📊 المؤشرات")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cmax", f"{m['cmax']:.1f} mg/L")
    col2.metric("Tmax", f"{m['tmax']:.1f} h")
    col3.metric("AUC", f"{m['auc']:.0f} mg·h/L")
    col4.metric("fT>MIC", f"{m['ft_pct']:.1f}%")

    st.subheader("🎯 الحكم النهائي")
    msg = f"{drug['index_label']} = {m['governing_value']:.1f} (الهدف ≥ {drug['index_target']})"
    if m['verdict'] == 'active':
        st.success(f"✅ فعال — {msg}")
    elif m['verdict'] == 'warning':
        st.warning(f"⚠️ حدّي — {msg}")
    else:
        st.error(f"❌ غير فعال — {msg}")

    st.subheader("📋 مقارنة المؤشرات الثلاثة")
    st.dataframe({
        'المؤشر': ['Cmax/MIC', 'fT>MIC (%)', 'AUC/MIC'],
        'القيمة': [f"{m['cmax_mic']:.1f}", f"{m['ft_pct']:.1f}", f"{m['auc_mic']:.0f}"],
        'الهدف': ['≥ 10', '≥ 50%', '≥ 400'],
        'الحاكم': ['✅' if drug['index'] == 'cmax_mic' else '',
                    '✅' if drug['index'] == 'ft_mic' else '',
                    '✅' if drug['index'] == 'auc_mic' else ''],
    }, width="stretch", hide_index=True)

    with st.expander("💡 لماذا هذا المؤشر الحاكم؟"):
        explanations = {
            'gentamicin': "الأمينوغليكوزيدات تعتمد على تركيز الذروة (Cmax/MIC ≥ 10).",
            'ceftriaxone': "β-لاكتام تعتمد على الوقت (fT>MIC ≥ 50%).",
            'vancomycin': "الفانكومايسين يعتمد على التعرض الكلي (AUC/MIC ≥ 400).",
        }
        st.info(explanations[selected])

    with st.expander("⚠️ حدود النموذج"):
        st.markdown("""
        - **حجرة واحدة فقط** — الجنتامايسين يتوزع على 2-3 حجرات في الواقع
        - **لا PAE** — الجنتامايسين له PAE طويل 2-4 ساعات
        - **لا مقاومة تكيفية** — البكتيريا قد تقلل نفاذية الدواء
        """)

    st.caption("📚 Bauer (2026)؛ IDSA TDM Guidelines (2026)")
