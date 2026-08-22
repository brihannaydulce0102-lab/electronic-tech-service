import streamlit as st
import pandas as pd
import os
from datetime import datetime
from PIL import Image
import hashlib

st.set_page_config(
    page_title="Electronic Tech Service",
    page_icon="logo.png",
    layout="wide"
)

# ------------------ DISEÑO ------------------

st.markdown("""
<style>

.stApp{
background:#05051b;
color:white;
}

.stButton>button{
background:#00e5ff;
color:black;
font-weight:bold;
border-radius:12px;
padding:10px;
}

.card{
background:#111133;
padding:15px;
border-radius:15px;
margin-bottom:15px;
}

</style>
""",unsafe_allow_html=True)

# ------------------ CARPETAS ------------------

ARCHIVE_FOLDER="cortes_mensuales"
ASSETS_FOLDER="assets"

os.makedirs(ARCHIVE_FOLDER,exist_ok=True)
os.makedirs(ASSETS_FOLDER,exist_ok=True)

DATA_FILE="reparaciones.xlsx"
INV_FILE="inventario.xlsx"
GASTOS_FILE="gastos.xlsx"
USERS_FILE="usuarios.xlsx"

# ------------------ HASH ------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ------------------ USUARIOS ------------------

if os.path.exists(USERS_FILE):

    usuarios=pd.read_excel(USERS_FILE)

else:

    usuarios=pd.DataFrame([{
        "usuario":"admin",
        "password":hash_password("123456"),
        "rol":"admin"
    }])

    usuarios.to_excel(USERS_FILE,index=False)

usuarios.columns=[str(c).lower().strip() for c in usuarios.columns]

if "contraseña" in usuarios.columns:
    usuarios["password"]=usuarios["contraseña"]

if "clave" in usuarios.columns:
    usuarios["password"]=usuarios["clave"]

for c in ["usuario","password","rol"]:
    if c not in usuarios.columns:
        usuarios[c]=""

# Migración automática

for i,row in usuarios.iterrows():

    pwd=str(row["password"])

    if len(pwd)!=64:
        usuarios.loc[i,"password"]=hash_password(pwd)

# Asegurar admin

if usuarios[usuarios["usuario"].str.lower()=="admin"].empty:

    usuarios=pd.concat([
        usuarios,
        pd.DataFrame([{
            "usuario":"admin",
            "password":hash_password("123456"),
            "rol":"admin"
        }])
    ],ignore_index=True)

usuarios.to_excel(USERS_FILE,index=False)

# ------------------ SESSION ------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in=False
    st.session_state.usuario=""
    st.session_state.rol=""

# ------------------ LOGIN ------------------

if not st.session_state.logged_in:

    c1,c2,c3=st.columns([1,2,1])

    with c2:

        if os.path.exists("logo.png"):
            st.image("logo.png",width=260)

        st.title("Electronic Tech Service")
        st.caption("Sistema Profesional de Gestión")

        user=st.text_input("Usuario")
        pwd=st.text_input("Contraseña",type="password")

        if st.button("Entrar",use_container_width=True):

            buscar=usuarios[
                usuarios["usuario"].str.lower()==user.lower().strip()
            ]

            if not buscar.empty:

                datos=buscar.iloc[0]

                if datos["password"]==hash_password(pwd):

                    st.session_state.logged_in=True
                    st.session_state.usuario=datos["usuario"]
                    st.session_state.rol=datos["rol"]

                    st.success("Bienvenido")
                    st.rerun()

            st.error("Usuario o contraseña incorrectos")

    st.stop()

# ------------------ CABECERA ------------------

col1,col2=st.columns([1,5])

with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png",width=120)

with col2:
    st.title("Electronic Tech Service")
    st.caption(
        f"{st.session_state.usuario} • {st.session_state.rol}"
    )

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logged_in=False
    st.rerun()

# ------------------ BASES ------------------

if os.path.exists(DATA_FILE):
    df=pd.read_excel(DATA_FILE)
else:
    df=pd.DataFrame(columns=[
        "ID","Fecha","Cliente","Telefono","Equipo",
        "Problema","Precio_Estimado","Estado",
        "Tecnico","Notas","Pagado","Fotos","Firma"
    ])

for c in ["Fotos","Firma"]:
    if c not in df.columns:
        df[c]=""

if os.path.exists(INV_FILE):
    inv=pd.read_excel(INV_FILE)
else:
    inv=pd.DataFrame(columns=[
        "Producto","Cantidad","Precio_Unitario"
    ])

if os.path.exists(GASTOS_FILE):
    gastos=pd.read_excel(GASTOS_FILE)
else:
    gastos=pd.DataFrame(columns=[
        "Fecha","Descripcion","Monto","Categoria"
    ])
    menu=[
"🏠 Inicio",
"📋 Nueva Reparación",
"📋 Ver Órdenes",
"🔍 Buscar",
"📄 Cotizaciones",
"🖨️ Recibos"
]

if st.session_state.rol=="admin":

    menu+=["📦 Inventario",
           "📊 Contabilidad",
           "💸 Gastos",
           "📅 Corte Mensual",
           "👥 Usuarios"]

opcion=st.sidebar.selectbox("Menú",menu)
if opcion=="🏠 Inicio":

    col1,col2,col3,col4=st.columns(4)

    col1.metric("Órdenes",len(df))

    pendientes=len(df[df["Estado"]!="Entregado"])

    col2.metric("Pendientes",pendientes)

    entregados=len(df[df["Estado"]=="Entregado"])

    col3.metric("Entregados",entregados)

    total=df["Precio_Estimado"].sum()

    col4.metric("Ingresos estimados",f"${total:,.0f}")

    st.markdown("---")

    st.subheader("Actividad reciente")

    if not df.empty:

        st.dataframe(
            df.tail(5),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Todavía no hay órdenes.")
        
