"""Pharma SDL — Streamlit Web Application."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.agent import MultiObjectiveAgent
from core.maker import MoleculeMaker
from core.oracle import MultiObjectiveOracle
from core.protac import VEPDEGESTRANT

st.set_page_config(page_title="Pharma SDL", page_icon="🧬", layout="wide")

st.title("🧬 Pharma SDL — مختبر الفارما الذاتي")
st.markdown("> من الكتاب إلى الكود — من النظرية إلى الاكتشاف")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🏭 Make", "🔬 Test", "🧠 Analyze", "🧬 PROTAC", "🔌 PubChem"]
)

# --- Make Tab ---
with tab1:
    st.header("توليد جزيئات")
    n = st.slider("عدد الجزيئات", 5, 50, 20)
    seed = st.number_input("بذرة عشوائية", value=42)
    maker = MoleculeMaker(n=n, seed=seed)
    feats = maker.to_features()
    st.write(f"تم توليد {len(maker.smiles_list)} جزيء")
    st.dataframe(feats, columns=["MW", "LogP", "HBD", "HBA", "TPSA", "RotBonds"])

# --- Test Tab ---
with tab2:
    st.header("محاكاة hERG + LDL-C")
    oracle = MultiObjectiveOracle(seed=42)
    maker = MoleculeMaker(n=20, seed=42)
    feats = maker.to_features()
    scores = oracle.batch_score(feats)
    df = {"Molecule": range(len(feats)), "Score": scores}
    fig = px.bar(df, x="Molecule", y="Score", title="Multi-Objective Score")
    st.plotly_chart(fig, use_container_width=True)

# --- Analyze Tab ---
with tab3:
    st.header("التعلم النشط (UCB + Pareto)")
    maker = MoleculeMaker(n=20, seed=42)
    library = maker.to_features()
    oracle = MultiObjectiveOracle(seed=42)
    agent = MultiObjectiveAgent(library, oracle)
    agent.initialize(n_init=5)
    for _ in range(5):
        agent.run_cycle(batch_size=2)
    mask = agent.pareto_mask()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=agent.herg_train, y=agent.ldl_train,
        mode="markers", name="All", marker={"size": 8, "color": "gray"}
    ))
    fig.add_trace(go.Scatter(
        x=agent.herg_train[mask], y=agent.ldl_train[mask],
        mode="markers", name="Pareto", marker={"size": 12, "color": "red"}
    ))
    fig.update_layout(xaxis_title="hERG (lower=better)",
                      yaxis_title="LDL-C reduction (higher=better)")
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"Pool size: {len(agent.pool_idx)}, Pareto points: {mask.sum()}")

# --- PROTAC Tab ---
with tab4:
    st.header("PROTAC — Vepdegestrant")
    conc = np.logspace(-3, 4, 100)
    deg = VEPDEGESTRANT.degradation_fraction(conc)
    fig = px.line(x=conc, y=deg, log_x=True,
                  labels={"x": "Concentration (nM)", "y": "Degradation (%)"},
                  title="Degradation Curve")
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"DC50: {VEPDEGESTRANT.dc50} nM, Dmax: {VEPDEGESTRANT.dmax}%")

    sol = VEPDEGESTRANT.simulate(t_days=7)
    fig2 = px.line(x=sol.t, y=sol.y[2],
                   labels={"x": "Time (h)", "y": "Target Protein (%)"},
                   title="PK/PD Simulation (7 days)")
    st.plotly_chart(fig2, use_container_width=True)

# --- PubChem Tab ---
with tab5:
    st.header("PubChem — جلب بيانات حقيقية")
    from core.pubchem_client import PubChemClient
    client = PubChemClient()
    cid = st.number_input("CID", value=2244, min_value=1)
    if st.button("جلب"):
        data = client.get_compound(cid)
        if data:
            st.json(data)
        else:
            st.error("فشل في جلب البيانات")
