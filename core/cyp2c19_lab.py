"""
مختبر CYP2C19 — الطب الشخصي في clopidogrel
بناءً على QPGx-CARES (قطر، 2026): 376 مريضًا، 22% حاملو LoF
"""
import numpy as np

try:
    import plotly.graph_objects as go
except ImportError:
    go = None
try:
    import streamlit as st
except ImportError:
    st = None


# ═══════════════════════════════════════════════════════════
# الأنماط الجينية
# ═══════════════════════════════════════════════════════════

PHENOTYPES = {
    'UM': {
        'name': 'Ultra-rapid Metabolizer',
        'name_ar': 'استقلاب فائق السرعة',
        'genotypes': ['*17/*17', '*1/*17'],
        'activity_score': 3.0,
        'prevalence_me': '1-2%',
        'prevalence_ar': '3%',
        'color': '#3b82f6',
    },
    'NM': {
        'name': 'Normal Metabolizer',
        'name_ar': 'استقلاب طبيعي',
        'genotypes': ['*1/*1'],
        'activity_score': 2.0,
        'prevalence_me': '35-40%',
        'prevalence_ar': '55%',
        'color': '#22c55e',
    },
    'IM': {
        'name': 'Intermediate Metabolizer',
        'name_ar': 'استقلاب متوسط',
        'genotypes': ['*1/*2', '*1/*3', '*2/*17'],
        'activity_score': 1.0,
        'prevalence_me': '18-25%',
        'prevalence_ar': '37%',
        'color': '#f59e0b',
    },
    'PM': {
        'name': 'Poor Metabolizer',
        'name_ar': 'استقلاب ضعيف',
        'genotypes': ['*2/*2', '*2/*3', '*3/*3'],
        'activity_score': 0.0,
        'prevalence_me': '2-15%',
        'prevalence_ar': '5%',
        'color': '#ef4444',
    },
}


# ═══════════════════════════════════════════════════════════
# التوصيات السريرية (CPIC Guidelines)
# ═══════════════════════════════════════════════════════════

RECOMMENDATIONS = {
    'UM': {
        'clopidogrel': '✅ الجرعة القياسية (75 mg)',
        'alternative': 'لا حاجة',
        'detail': 'استقلاب طبيعي — clopidogrel فعّال',
        'strength': 'قوي',
        'color': 'success',
    },
    'NM': {
        'clopidogrel': '✅ الجرعة القياسية (75 mg)',
        'alternative': 'لا حاجة',
        'detail': 'استقلاب طبيعي — clopidogrel فعّال',
        'strength': 'قوي',
        'color': 'success',
    },
    'IM': {
        'clopidogrel': '⚠️ جرعة عالية (150 mg) أو بديل',
        'alternative': 'Ticagrelor 90 mg × 2، أو Prasugrel 10 mg',
        'detail': 'استقلاب متوسط — clopidogrel أقل فعالية',
        'strength': 'متوسط',
        'color': 'warning',
    },
    'PM': {
        'clopidogrel': '❌ غير موصى به',
        'alternative': 'Ticagrelor 90 mg × 2، أو Prasugrel 10 mg',
        'detail': 'استقلاب ضعيف — clopidogrel قد لا يعمل',
        'strength': 'قوي',
        'color': 'error',
    },
}


# ═══════════════════════════════════════════════════════════
# محرك التنبؤ بالاستجابة
# ═══════════════════════════════════════════════════════════

def predict_platelet_inhibition(activity_score, dose_mg):
    """
    تنبؤ بتثبيط الصفيحات بناءً على النشاط الإنزيمي والجرعة.
    مرجع: Mega et al., 2010؛ وبيانات CPIC
    """
    max_inhibition = {
        3.0: 95,   # UM
        2.0: 85,   # NM
        1.0: 45,   # IM
        0.0: 15,   # PM
    }.get(activity_score, 20)

    dose_factor = np.log10(dose_mg + 1) / np.log10(151)
    dose_factor = np.clip(dose_factor, 0, 1.2)

    return max_inhibition * dose_factor


def simulate_time_course(activity_score, dose_mg, duration_hours=72):
    """
    محاكاة تغيّر تثبيط الصفيحات عبر الزمن بعد جرعة واحدة.
    """
    t = np.linspace(0, duration_hours, 200)

    tmax = 3.0
    peak = predict_platelet_inhibition(activity_score, dose_mg)

    rise = 1 - np.exp(-t / tmax)
    decay = np.exp(-t / (24 * 3))

    return t, peak * rise * decay


# ═══════════════════════════════════════════════════════════
# واجهة Streamlit
# ═══════════════════════════════════════════════════════════

def render():  # pragma: no cover
    st.header("🧬 المختبر 05 — CYP2C19 والطب الشخصي")
    st.markdown(
        "**clopidogrel** هو دواء مضاد للصفيحات يستخدم بعد PCI. "
        "لكنه **طليعة دواء** (prodrug) يحتاج CYP2C19 لتحويله للشكل النشط. "
        "حاملو أليل **فقدان الوظيفة (LoF)** لا يستفيدون منه بالكامل."
    )

    st.subheader("1️⃣ اختر النمط الجيني")
    phenotype_keys = list(PHENOTYPES.keys())
    selected_pheno = st.radio(
        "النمط",
        options=phenotype_keys,
        format_func=lambda k: (
            f"{PHENOTYPES[k]['name_ar']} — {PHENOTYPES[k]['genotypes'][0]}"
        ),
        horizontal=True,
    )
    pheno = PHENOTYPES[selected_pheno]

    with st.expander("📊 توزيع الأنماط في الشرق الأوسط"):
        rows = []
        for key in phenotype_keys:
            p = PHENOTYPES[key]
            rows.append({
                'النمط': p['name_ar'],
                'الأنماط الجينية': '، '.join(p['genotypes'][:2]),
                'النشاط': p['activity_score'],
                'الانتشار': p['prevalence_ar'],
            })
        st.dataframe(rows, width="stretch", hide_index=True)

    st.subheader("2️⃣ معاملات المريض")
    col1, col2 = st.columns(2)
    with col1:
        dose = st.slider("جرعة clopidogrel (mg)", 75, 300, 75, 25)
    with col2:
        _indication = st.selectbox(
            "الاستطباب",
            ["PCI بعد ACS", "PCI مستقر", "السكتة الدماغية"],
        )

    t, response = simulate_time_course(pheno['activity_score'], dose)

    st.subheader("3️⃣ محاكاة الاستجابة")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t, y=response,
        mode='lines',
        name=pheno['name_ar'],
        line={'color': pheno['color'], 'width': 3},
        fill='tozeroy',
    ))

    fig.add_hline(
        y=50, line_dash="dash", line_color="gray",
        annotation_text="حد الفعالية (50%)",
    )

    fig.update_layout(
        xaxis_title="الزمن (ساعة)",
        yaxis_title="تثبيط الصفيحات (%)",
        template="plotly_white",
        height=400,
        yaxis={'range': [0, 100]},
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("4️⃣ المؤشرات")
    col1, col2, col3 = st.columns(3)
    col1.metric("أقصى تثبيط", f"{response.max():.1f}%")
    col2.metric("الهدف", "≥ 50%")
    col3.metric("الحالة", "✅ فعال" if response.max() >= 50 else "❌ غير فعال")

    st.subheader("5️⃣ التوصية السريرية")
    rec = RECOMMENDATIONS[selected_pheno]

    if rec['color'] == 'success':
        st.success(f"**{rec['clopidogrel']}**\n\n{rec['detail']}")
    elif rec['color'] == 'warning':
        st.warning(f"**{rec['clopidogrel']}**\n\n{rec['detail']}\n\n**البديل:** {rec['alternative']}")
    else:
        st.error(f"**{rec['clopidogrel']}**\n\n{rec['detail']}\n\n**البديل:** {rec['alternative']}")

    with st.expander("📚 الأسس العلمية"):
        st.markdown("""
        ### CPIC Guidelines for CYP2C19 and Clopidogrel (2022 update)

        **Poor Metabolizer (PM):**
        - لا يُوصى بـ clopidogrel للـ ACS/PCI
        - البديل: ticagrelor أو prasugrel

        **Intermediate Metabolizer (IM):**
        - قد يحتاج جرعة مضاعفة (150 mg)
        - أو التحول إلى ticagrelor/prasugrel
        - خاصة في ACS/PCI

        **Normal/Ultra-rapid Metabolizer:**
        - الجرعة القياسية 75 mg

        ### بيانات عربية (QPGx-CARES، قطر 2026)
        - 376 مريضًا خضعوا لـ PCI
        - 22% حاملو أليل LoF
        - تغيير العلاج في 22% من الحالات
        - 80% قبول من الأطباء
        - وفر: 300 ريال قطري (~82$) لكل مريض/سنة
        """)

    with st.expander("⚠️ حدود النموذج"):
        st.markdown("""
        - **النموذج تقديري** — لا يعكس الاستجابة الفردية الكاملة
        - **الأدوية الأخرى:** لا يشمل interactions مع omeprazole، إلخ
        - **الالتزام:** لا يعكس عدم الالتزام بالدواء
        - **العوامل الأخرى:** الوزن، العمر، السكري، التدخين
        """)

    st.caption(
        "📚 المصادر: CPIC 2022؛ QPGx-CARES (Clinical Therapeutics 2026)؛ "
        "Mega et al. (JAMA 2010)"
    )
