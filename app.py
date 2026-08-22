import streamlit as st
import pandas as pd
import os
import hashlib
import base64
import shutil
import urllib.parse
import qrcode
from io import BytesIO
from datetime import datetime
from PIL import Image
import matplotlib.pyplot as plt

from streamlit_drawable_canvas import st_canvas

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage
)

from reportlab.lib.styles import getSampleStyleSheet


st.set_page_config(
    page_title="Electronic Tech Service",
    page_icon="logo.png",
    layout="wide"
)

# ===========================
# ESTILO
# ===========================

st.markdown("""
<style>

.stApp{
background:#05051b;
color:white;
}

.stButton>button{
background:#00E5FF;
color:black;
font-weight:bold;
border-radius:12px;
padding:12px;
width:100%;
}

.card{
background:#111133;
padding:16px;
border-radius:15px;
margin-bottom:15px;
}

@media (max-width:768px){

h1{
font-size:28px;
}

}

</style>
""",unsafe_allow_html=True)

# ===========================
# RUTAS
# ===========================

DATA_FILE="reparaciones.xlsx"
INV_FILE="inventario.xlsx"
GASTOS_FILE="gastos.xlsx"
USERS_FILE="usuarios.xlsx"

ASSETS="assets"
BACKUP="backup"
ARCHIVE="cortes_mensuales"

for carpeta in [ASSETS,BACKUP,ARCHIVE]:
    os.makedirs(carpeta,exist_ok=True)

# ===========================
# FUNCIONES
# ===========================

def hash_password(texto):
    return hashlib.sha256(texto.encode()).hexdigest()

@st.cache_data
def cargar_excel(ruta,columnas):

    if os.path.exists(ruta):
        return pd.read_excel(ruta)

    return pd.DataFrame(columns=columnas)

def guardar_excel(df,ruta):

    df.to_excel(ruta,index=False)

    respaldo()

    st.cache_data.clear()

def respaldo():

    fecha=datetime.now().strftime("%Y%m%d_%H%M%S")

    for archivo in [DATA_FILE,INV_FILE,GASTOS_FILE,USERS_FILE]:

        if os.path.exists(archivo):

            shutil.copy(
                archivo,
                os.path.join(
                    BACKUP,
                    f"{fecha}_{archivo}"
                )
            )

def asegurar_columnas(df,columnas):

    for c,v in columnas.items():

        if c not in df.columns:
            df[c]=v

    return df

# ===========================
# IMÁGENES BASE64
# ===========================

def imagen_base64(upload):

    return base64.b64encode(upload.read()).decode()

def mostrar_base64(texto):

    return base64.b64decode(texto)

# ===========================
# QR
# ===========================

def crear_qr(texto):

    qr=qrcode.QRCode(box_size=8,border=2)

    qr.add_data(texto)

    qr.make(fit=True)

    img=qr.make_image(fill_color="black",back_color="white")

    ruta=os.path.join(ASSETS,f"{texto}.png")

    img.save(ruta)

    return ruta

# ===========================
# PDF
# ===========================

def crear_pdf(orden):

    ruta=os.path.join(
        ASSETS,
        f"Recibo_{orden['ID']}.pdf"
    )

    doc=SimpleDocTemplate(ruta)

    estilos=getSampleStyleSheet()

    e=[]

    if os.path.exists("logo.png"):
        e.append(RLImage("logo.png",120,120))

    e.append(
        Paragraph(
            "<b>Electronic Tech Service</b>",
            estilos["Title"]
        )
    )

    e.append(
        Paragraph("Montería - Córdoba",estilos["Normal"])
    )

    e.append(Spacer(1,12))

    campos=[
        ("Orden",orden["ID"]),
        ("Fecha",orden["Fecha"]),
        ("Cliente",orden["Cliente"]),
        ("Teléfono",orden["Telefono"]),
        ("Equipo",orden["Equipo"]),
        ("Problema",orden["Problema"]),
        ("Estado",orden["Estado"])
    ]

    for k,v in campos:

        e.append(
            Paragraph(
                f"<b>{k}:</b> {v}",
                estilos["Normal"]
            )
        )

    e.append(
        Paragraph(
            f"<b>Total:</b> ${orden['Precio_Estimado']:,.0f}",
            estilos["Normal"]
        )
    )

    qr=crear_qr(f"ETS_{orden['ID']}")

    e.append(Spacer(1,10))

    e.append(RLImage(qr,120,120))

    e.append(Spacer(1,10))

    e.append(
        Paragraph(
            "Gracias por confiar en Electronic Tech Service.",
            estilos["Italic"]
        )
    )

    doc.build(e)

    return ruta

# ===========================
# CARGAR DATOS
# ===========================

df=cargar_excel(
DATA_FILE,
["ID","Fecha","Cliente","Telefono","Equipo",
"Problema","Precio_Estimado","Estado",
"Tecnico","Notas","Pagado","Fotos","Firma"]
)

df=asegurar_columnas(df,{
"Fotos":"",
"Firma":"",
"Pagado":"Pendiente"
})

inv=cargar_excel(
INV_FILE,
["Producto","Cantidad","Precio_Unitario"]
)

gastos=cargar_excel(
GASTOS_FILE,
["Fecha","Descripcion","Monto","Categoria"]
)

usuarios=cargar_excel(
USERS_FILE,
["usuario","password","rol"]
)

usuarios.columns=[
str(c).lower().strip()
for c in usuarios.columns
]

if "contraseña" in usuarios.columns:
    usuarios["password"]=usuarios["contraseña"]

if "clave" in usuarios.columns:
    usuarios["password"]=usuarios["clave"]

usuarios=asegurar_columnas(usuarios,{
"usuario":"",
"password":"",
"rol":"trabajador"
})

# Migrar contraseñas antiguas

for i,r in usuarios.iterrows():

    pwd=str(r["password"])

    if len(pwd)!=64:

        usuarios.loc[i,"password"]=hash_password(pwd)

# Crear admin si no existe

if usuarios[usuarios["usuario"].str.lower()=="admin"].empty:

    usuarios=pd.concat([
        usuarios,
        pd.DataFrame([{
        "usuario":"admin",
        "password":hash_password("123456"),
        "rol":"admin"
        }])
    ],ignore_index=True)

guardar_excel(usuarios,USERS_FILE)

# ===========================
# LOGIN
# ===========================

if "logged_in" not in st.session_state:

    st.session_state.logged_in=False
    st.session_state.usuario=""
    st.session_state.rol=""

if not st.session_state.logged_in:

    c1,c2,c3=st.columns([1,2,1])

    with c2:

        if os.path.exists("logo.png"):
            st.image("logo.png",width=260)

        st.title("Electronic Tech Service")

        st.caption("Sistema Profesional")

        usuario=st.text_input("Usuario")

        clave=st.text_input("Contraseña",type="password")

        if st.button("Entrar"):

            b=usuarios[
                usuarios["usuario"].str.lower()==usuario.lower()
            ]

            if not b.empty:

                d=b.iloc[0]

                if d["password"]==hash_password(clave):

                    st.session_state.logged_in=True
                    st.session_state.usuario=d["usuario"]
                    st.session_state.rol=d["rol"]

                    st.rerun()

            st.error("Usuario o contraseña incorrectos")

    st.stop()

# ===========================
# CABECERA
# ===========================

a,b=st.columns([1,5])

with a:

    if os.path.exists("logo.png"):
        st.image("logo.png",width=110)

with b:

    st.title("Electronic Tech Service")

    st.caption(
        f"{st.session_state.usuario} | {st.session_state.rol}"
    )

if st.sidebar.button("Cerrar Sesión"):

    st.session_state.logged_in=False

    st.rerun()

# ===========================
# MENÚ
# ===========================

menu=[
"🏠 Inicio",
"📋 Nueva Reparación",
"📋 Ver Órdenes",
"🔍 Buscar",
"📄 Cotizaciones",
"🖨️ Recibos",
"📍 Taller",
"📤 Exportar"
]

if st.session_state.rol=="admin":

    menu.extend([
    "📦 Inventario",
    "📊 Contabilidad",
    "💸 Gastos",
    "📅 Corte Mensual",
    "👥 Usuarios"
    ])

opcion=st.sidebar.selectbox("Menú",menu)
