import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Electronic Tech Service", page_icon="logo.png", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0a0a23; color: #ffffff; }
    .stButton>button { background-color: #00f5ff; color: #000000; font-weight: bold; padding: 12px; border-radius: 10px; }
    h1, h2, h3 { color: #00f5ff; }
</style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario = ""
    st.session_state.rol = ""

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=280)
        st.title("Electronic Tech Service")
        st.markdown("**Iniciar Sesión**")
    
    usuario = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar", type="primary", use_container_width=True):
        if usuario.strip().lower() == "admin" and password.strip() == "123456":
            st.session_state.logged_in = True
            st.session_state.usuario = "admin"
            st.session_state.rol = "admin"
            st.success("Bienvenido Administrador")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
    st.stop()

col1, col2 = st.columns([1, 4])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=180)
with col2:
    st.title("Electronic Tech Service")

st.markdown(f"**Usuario:** {st.session_state.usuario} ({st.session_state.rol})")
st.markdown("---")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logged_in = False
    st.rerun()

st.success("El sistema está funcionando correctamente")
st.write("Ya puedes empezar a usar la aplicación.")
