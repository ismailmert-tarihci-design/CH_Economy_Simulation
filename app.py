import streamlit as st

st.set_page_config(
    page_title="Bluestar Economy Simulator", page_icon="🌌", layout="wide"
)

st.title("🌌 Bluestar Economy Simulator")
st.markdown(
    "Welcome to the Bluestar Economy Simulator - a tool for modeling and analyzing economic systems."
)

st.info("This is the foundation build. More features coming soon!")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Status", "Ready")
with col2:
    st.metric("Version", "0.1.0")
with col3:
    st.metric("Modules", "Core")
