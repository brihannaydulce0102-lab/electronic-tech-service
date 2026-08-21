import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Electronic Tech Service", page_icon="logo.png", layout="wide")

# Estilo
st.markdown("""
<style>
    .stApp { background-color: #0a0a23; color: #ffffff; }
    .stButton>button { background-color: #00f5ff; color: #000000; font-weight: bold; padding: 12px; border-radius: 10px; }
    h1, h2, h3 { color: #00f5ff; }
</style>
""", unsafe_allow_html=True)

# ==================== ARCHIVOS ====================
USERS_FILE = "usuarios.xlsx"
DATA_FILE = "reparaciones.xlsx"

if not os.path.exists(USERS_FILE):
    pd.DataFrame([
        {"usuario": "admin", "contraseña": "123456", "rol": "admin"}
    ]).to_excel(USERS_FILE, index=False)

usuarios = pd.read_excel(USERS_FILE)

# ==================== LOGIN ====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario = ""
    st.session_state.rol = ""

if not st.session_state.logged_in:
    # Logo en el login
    col1, col2, col3 = st.columns([1, 2, 1])
    with col
