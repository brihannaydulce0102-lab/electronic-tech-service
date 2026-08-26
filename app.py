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

df = pd.read_excel(
    DATA_FILE,
    dtype={
        "Cliente": str,
        "Telefono": str,
        "Equipo": str,
        "Problema": str,
        "Tecnico": str,
        "Notas": str,
        "Pagado": str
    }
)

columnas_texto = [
    "Cliente", "Telefono", "Equipo",
    "Problema", "Tecnico", "Notas", "Pagado"
]

for col in columnas_texto:
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str)

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
# ==========================================================
# INICIO
# ==========================================================

if opcion=="🏠 Inicio":

    ingresos=df["Precio_Estimado"].sum() if not df.empty else 0

    pendientes=len(df[df["Estado"]!="Entregado"]) if not df.empty else 0

    listos=len(df[df["Estado"]=="Listo"]) if not df.empty else 0

    c1,c2,c3,c4=st.columns(4)

    c1.metric("Órdenes",len(df))
    c2.metric("Ingresos",f"${ingresos:,.0f}")
    c3.metric("Pendientes",pendientes)
    c4.metric("Listos",listos)

    st.markdown("---")

    if not df.empty:
        st.subheader("Últimas órdenes")
        st.dataframe(df.tail(5),use_container_width=True,hide_index=True)

# ==========================================================
# NUEVA REPARACIÓN
# ==========================================================

elif opcion=="📋 Nueva Reparación":

    st.subheader("Nueva Orden de Reparación")

    c1,c2=st.columns(2)

    with c1:

        cliente=st.text_input("Cliente")
        telefono=st.text_input("Teléfono / WhatsApp")
        equipo=st.text_input("Equipo")

    with c2:

        problema=st.text_area("Problema")
        precio=st.number_input("Precio estimado",min_value=0,step=1000)

        estado=st.selectbox(
            "Estado",
            ["Recibido","En reparación","Listo","Entregado"]
        )

    st.markdown("### 📷 Fotos")

    antes=st.file_uploader("Antes",type=["jpg","jpeg","png"],key="antes")
    durante=st.file_uploader("Durante",type=["jpg","jpeg","png"],key="durante")
    despues=st.file_uploader("Después",type=["jpg","jpeg","png"],key="despues")

    st.markdown("### ✍️ Firma del cliente")

    canvas=st_canvas(
        stroke_width=3,
        stroke_color="#000",
        background_color="#FFF",
        height=180,
        width=500,
        drawing_mode="freedraw",
        key="firma_canvas"
    )

    if st.button("Guardar Orden"):

        if cliente and equipo:

            nuevo_id=1 if df.empty else int(df["ID"].max())+1

            fotos={}

            if antes:
                fotos["antes"]=imagen_base64(antes)

            if durante:
                fotos["durante"]=imagen_base64(durante)

            if despues:
                fotos["despues"]=imagen_base64(despues)

            firma=""

            if canvas.image_data is not None:

                img=Image.fromarray(canvas.image_data.astype("uint8"))

                buffer=BytesIO()

                img.save(buffer,format="PNG")

                firma=base64.b64encode(buffer.getvalue()).decode()

            nueva=pd.DataFrame([{
                "ID":nuevo_id,
                "Fecha":datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Cliente":cliente,
                "Telefono":telefono,
                "Equipo":equipo,
                "Problema":problema,
                "Precio_Estimado":precio,
                "Estado":estado,
                "Tecnico":st.session_state.usuario,
                "Notas":"",
                "Pagado":"Pendiente",
                "Fotos":str(fotos),
                "Firma":firma
            }])

            df=pd.concat([df,nueva],ignore_index=True)

            guardar_excel(df,DATA_FILE)

            st.success(f"Orden #{nuevo_id} creada correctamente")

            st.balloons()

        else:
            st.error("Cliente y equipo son obligatorios.")

# ==========================================================
# VER ÓRDENES
# ==========================================================

elif opcion=="📋 Ver Órdenes":

    st.subheader("Órdenes")

    if df.empty:

        st.info("No hay órdenes registradas.")

    else:

        import ast

        for i,orden in df.iterrows():

            with st.container(border=True):

                c1,c2=st.columns([1,2])

                with c1:

                    try:
                        fotos=ast.literal_eval(str(orden["Fotos"]))
                    except:
                        fotos={}

                    for nombre in ["antes","durante","despues"]:

                        if nombre in fotos:

                            st.image(
                                mostrar_base64(fotos[nombre]),
                                caption=nombre.capitalize(),
                                width=170
                            )

                with c2:

                    st.markdown(f"### Orden #{orden['ID']}")

                    st.write("**Cliente:**",orden["Cliente"])
                    st.write("**Equipo:**",orden["Equipo"])
                    st.write("**Problema:**",orden["Problema"])
                    st.write("**Estado:**",orden["Estado"])
                    st.write("**Precio:**",f"${orden['Precio_Estimado']:,.0f}")

                    if orden["Firma"]:

                        st.image(
                            mostrar_base64(orden["Firma"]),
                            caption="Firma del cliente",
                            width=200
                        )

                    nuevo_estado=st.selectbox(
                        "Estado",
                        ["Recibido","En reparación","Listo","Entregado"],
                        index=["Recibido","En reparación","Listo","Entregado"].index(orden["Estado"]),
                        key=f"estado{orden['ID']}"
                    )

                    if st.button("Actualizar Estado",key=f"actualizar{orden['ID']}"):

                        anterior=df.loc[i,"Estado"]

                        df.loc[i,"Estado"]=nuevo_estado

                        guardar_excel(df,DATA_FILE)

                        if anterior!="Listo" and nuevo_estado=="Listo":

                            st.success("Equipo listo para entregar.")
                            st.balloons()

                        st.rerun()

                    telefono=str(orden["Telefono"]).replace(" ","")

                    mensaje=urllib.parse.quote(
                        f"Hola {orden['Cliente']}, tu equipo ({orden['Equipo']}) está en estado: {nuevo_estado}."
                    )

                    st.link_button(
                        "📲 WhatsApp",
                        f"https://wa.me/57{telefono}?text={mensaje}"
                    )

                    if st.session_state.rol=="admin":

                        with st.expander("Editar Orden"):

                            cliente2=st.text_input(
                                "Cliente",
                                value=orden["Cliente"],
                                key=f"cli{orden['ID']}"
                            )

                            telefono2=st.text_input(
                                "Teléfono",
                                value=orden["Telefono"],
                                key=f"tel{orden['ID']}"
                            )

                            equipo2=st.text_input(
                                "Equipo",
                                value=orden["Equipo"],
                                key=f"eq{orden['ID']}"
                            )

                            problema2=st.text_area(
                                "Problema",
                                value=orden["Problema"],
                                key=f"prob{orden['ID']}"
                            )

                            precio2=st.number_input(
                                "Precio",
                                value=int(orden["Precio_Estimado"]),
                                step=1000,
                                key=f"precio{orden['ID']}"
                            )

                            if st.button("Guardar Cambios",key=f"save{orden['ID']}"):

                                df.loc[i,"Cliente"]=cliente2
                                df.loc[i,"Telefono"]=telefono2
                                df.loc[i,"Equipo"]=equipo2
                                df.loc[i,"Problema"]=problema2
                                df.loc[i,"Precio_Estimado"]=precio2

                                guardar_excel(df,DATA_FILE)

                                st.success("Orden actualizada.")

                                st.rerun()

                            if st.button("Eliminar Orden",key=f"del{orden['ID']}"):

                                df=df[df["ID"]!=orden["ID"]]

                                guardar_excel(df,DATA_FILE)

                                st.success("Orden eliminada.")

                                st.rerun()

# ==========================================================
# BUSCAR
# ==========================================================

elif opcion=="🔍 Buscar":

    st.subheader("Buscar")

    texto=st.text_input("Buscar por cliente, teléfono, equipo o ID")

    if texto:

        r=df[
            df["Cliente"].astype(str).str.contains(texto,case=False,na=False)
            | df["Telefono"].astype(str).str.contains(texto,na=False)
            | df["Equipo"].astype(str).str.contains(texto,case=False,na=False)
            | df["ID"].astype(str).str.contains(texto)
        ]

        st.write(f"{len(r)} resultado(s)")

        st.dataframe(r,use_container_width=True)

        if not r.empty:

            cliente=r.iloc[0]["Cliente"]

            st.markdown("---")

            st.subheader(f"Historial de {cliente}")

            historial=df[df["Cliente"]==cliente]

            st.dataframe(historial,use_container_width=True)

# ==========================================================
# RECIBOS
# ==========================================================

elif opcion=="🖨️ Recibos":

    st.subheader("Recibos")

    if df.empty:

        st.info("No hay órdenes.")

    else:

        id_recibo=st.selectbox("Selecciona la orden",df["ID"].tolist())

        orden=df[df["ID"]==id_recibo].iloc[0]

        st.write("**Cliente:**",orden["Cliente"])
        st.write("**Equipo:**",orden["Equipo"])
        st.write("**Estado:**",orden["Estado"])

        qr=crear_qr(f"ETS_{orden['ID']}")

        st.image(qr,width=140)

        if st.button("Generar PDF"):

            pdf=crear_pdf(orden)

            with open(pdf,"rb") as f:

                st.download_button(
                    "📄 Descargar Recibo",
                    f,
                    file_name=f"Recibo_{orden['ID']}.pdf",
                    mime="application/pdf"
                )

        if st.button("Generar Ticket"):

            ticket=f"""
Electronic Tech Service

Orden #{orden['ID']}

Cliente:
{orden['Cliente']}

Equipo:
{orden['Equipo']}

Estado:
{orden['Estado']}

Total:
${orden['Precio_Estimado']:,.0f}

WhatsApp:
3014874740

Gracias por preferirnos.
"""

            st.download_button(
                "🧾 Descargar Ticket",
                ticket,
                file_name=f"Ticket_{orden['ID']}.txt"
            )

# ==========================================================
# COTIZACIONES
# ==========================================================

elif opcion=="📄 Cotizaciones":

    st.subheader("Nueva Cotización")

    c1,c2=st.columns(2)

    with c1:
        cliente=st.text_input("Cliente",key="cot_cliente")
        telefono=st.text_input("Teléfono",key="cot_tel")
        equipo=st.text_input("Equipo",key="cot_equipo")

    with c2:
        descripcion=st.text_area("Descripción",key="cot_desc")
        precio=st.number_input("Precio",min_value=0,step=1000,key="cot_precio")

    if st.button("Generar Cotización"):

        st.markdown(f"""
        <div style="background:white;color:black;padding:25px;border-radius:12px">
        <h2 style="text-align:center;">Electronic Tech Service</h2>
        <hr>
        <b>Cliente:</b> {cliente}<br>
        <b>Teléfono:</b> {telefono}<br>
        <b>Equipo:</b> {equipo}<br>
        <b>Descripción:</b> {descripcion}<br><br>
        <h3 style="text-align:right;">Total: ${precio:,.0f}</h3>
        <hr>
        Montería - Córdoba
        </div>
        """,unsafe_allow_html=True)

# ==========================================================
# INVENTARIO
# ==========================================================

elif opcion=="📦 Inventario":

    st.subheader("Inventario")

    tab1,tab2=st.tabs(["Inventario","Agregar"])

    with tab1:

        if inv.empty:

            st.info("No hay productos.")

        else:

            for i,p in inv.iterrows():

                color="🟢"

                if p["Cantidad"]<=5:
                    color="🔴"

                elif p["Cantidad"]<=10:
                    color="🟡"

                with st.container(border=True):

                    st.write(f"{color} **{p['Producto']}**")

                    c1,c2=st.columns(2)

                    c1.write(f"Cantidad: {p['Cantidad']}")
                    c2.write(f"${p['Precio_Unitario']:,.0f}")

                    nueva=st.number_input(
                        "Nueva cantidad",
                        value=int(p["Cantidad"]),
                        key=f"cant{i}"
                    )

                    c3,c4=st.columns(2)

                    if c3.button("Actualizar",key=f"up{i}"):

                        inv.loc[i,"Cantidad"]=nueva

                        guardar_excel(inv,INV_FILE)

                        st.rerun()

                    if c4.button("Eliminar",key=f"del{i}"):

                        inv=inv.drop(i)

                        guardar_excel(inv,INV_FILE)

                        st.rerun()

    with tab2:

        prod=st.text_input("Producto")
        cant=st.number_input("Cantidad",min_value=1,value=1)
        precio=st.number_input("Precio Unitario",min_value=0,step=1000,key="inv_precio")

        if st.button("Guardar Producto"):

            nuevo=pd.DataFrame([{
                "Producto":prod,
                "Cantidad":cant,
                "Precio_Unitario":precio
            }])

            inv=pd.concat([inv,nuevo],ignore_index=True)

            guardar_excel(inv,INV_FILE)

            st.success("Producto agregado.")

            st.rerun()

# ==========================================================
# CONTABILIDAD
# ==========================================================

elif opcion=="📊 Contabilidad":

    st.subheader("Contabilidad")

    ingresos=df["Precio_Estimado"].sum() if not df.empty else 0

    egresos=gastos["Monto"].sum() if not gastos.empty else 0

    utilidad=ingresos-egresos

    c1,c2,c3=st.columns(3)

    c1.metric("Ingresos",f"${ingresos:,.0f}")
    c2.metric("Gastos",f"${egresos:,.0f}")
    c3.metric("Utilidad",f"${utilidad:,.0f}")

    st.markdown("---")

    if not df.empty:

        estados=df.groupby("Estado")["Precio_Estimado"].sum()

        fig,ax=plt.subplots()

        ax.bar(estados.index,estados.values)

        st.pyplot(fig)

        st.subheader("Equipos más reparados")

        top=df["Equipo"].value_counts().head(5)

        fig2,ax2=plt.subplots()

        ax2.bar(top.index,top.values)

        plt.xticks(rotation=25)

        st.pyplot(fig2)

# ==========================================================
# GASTOS
# ==========================================================

elif opcion=="💸 Gastos":

    st.subheader("Registrar Gasto")

    desc=st.text_input("Descripción")

    categoria=st.selectbox(
        "Categoría",
        ["Repuestos","Herramientas","Servicios","Transporte","Otros"]
    )

    monto=st.number_input("Monto",min_value=0,step=1000,key="gasto_monto")

    if st.button("Guardar Gasto"):

        nuevo=pd.DataFrame([{
            "Fecha":datetime.now().strftime("%Y-%m-%d"),
            "Descripcion":desc,
            "Monto":monto,
            "Categoria":categoria
        }])

        gastos=pd.concat([gastos,nuevo],ignore_index=True)

        guardar_excel(gastos,GASTOS_FILE)

        st.success("Gasto registrado.")

        st.rerun()

    if not gastos.empty:

        st.dataframe(gastos,use_container_width=True)

# ==========================================================
# CORTE MENSUAL
# ==========================================================

elif opcion=="📅 Corte Mensual":

    st.subheader("Corte del Mes")

    if st.button("Cerrar Mes"):

        mes=datetime.now().strftime("%Y-%m")

        ruta=os.path.join(
            ARCHIVE,
            f"corte_{mes}.xlsx"
        )

        guardar_excel(df,ruta)

        df=df.iloc[0:0]

        guardar_excel(df,DATA_FILE)

        st.success("Corte realizado correctamente.")

# ==========================================================
# USUARIOS
# ==========================================================

elif opcion=="👥 Usuarios":

    st.subheader("Administrar Usuarios")

    tab1,tab2=st.tabs(["Editar","Nuevo"])

    with tab1:

        for i,u in usuarios.iterrows():

            with st.container(border=True):

                nombre=st.text_input(
                    "Usuario",
                    value=u["usuario"],
                    key=f"user{i}"
                )

                clave=st.text_input(
                    "Nueva contraseña",
                    type="password",
                    key=f"pass{i}"
                )

                rol=st.selectbox(
                    "Rol",
                    ["trabajador","admin"],
                    index=1 if u["rol"]=="admin" else 0,
                    key=f"rol{i}"
                )

                c1,c2=st.columns(2)

                if c1.button("Guardar",key=f"save{i}"):

                    usuarios.loc[i,"usuario"]=nombre
                    usuarios.loc[i,"rol"]=rol

                    if clave:
                        usuarios.loc[i,"password"]=hash_password(clave)

                    guardar_excel(usuarios,USERS_FILE)

                    if st.session_state.usuario==u["usuario"]:
                        st.session_state.usuario=nombre
                        st.session_state.rol=rol

                    st.success("Usuario actualizado.")

                    st.rerun()

                if u["usuario"].lower()!="admin":

                    if c2.button("Eliminar",key=f"deluser{i}"):

                        usuarios=usuarios.drop(i)

                        guardar_excel(usuarios,USERS_FILE)

                        st.success("Usuario eliminado.")

                        st.rerun()

    with tab2:

        usuario=st.text_input("Nuevo Usuario")
        password=st.text_input("Contraseña",type="password",key="new_pass")
        rol=st.selectbox("Rol",["trabajador","admin"],key="new_role")

        if st.button("Crear Usuario"):

            if usuario:

                nuevo=pd.DataFrame([{
                    "usuario":usuario,
                    "password":hash_password(password),
                    "rol":rol
                }])

                usuarios=pd.concat([usuarios,nuevo],ignore_index=True)

                guardar_excel(usuarios,USERS_FILE)

                st.success("Usuario creado.")

                st.rerun()

# ==========================================================
# EXPORTAR
# ==========================================================

elif opcion=="📤 Exportar":

    st.subheader("Exportar Datos")

    st.download_button(
        "Descargar Órdenes",
        df.to_csv(index=False).encode("utf8"),
        "reparaciones.csv",
        "text/csv"
    )

    st.download_button(
        "Descargar Inventario",
        inv.to_csv(index=False).encode("utf8"),
        "inventario.csv",
        "text/csv"
    )

    st.download_button(
        "Descargar Gastos",
        gastos.to_csv(index=False).encode("utf8"),
        "gastos.csv",
        "text/csv"
    )

# ==========================================================
# TALLER
# ==========================================================

elif opcion=="📍 Taller":

    st.subheader("Electronic Tech Service")

    st.write("📍 Barrio El Mundo López")
    st.write("Montería - Córdoba")
    st.write("📞 WhatsApp: 301 487 4740")

    st.link_button(
        "Abrir Google Maps",
        "https://maps.google.com"
    )

# ==========================================================
# BOTÓN FLOTANTE WHATSAPP
# ==========================================================

st.markdown("""
<a href="https://wa.me/573014874740"
target="_blank"
style="
position:fixed;
bottom:20px;
right:20px;
background:#25D366;
color:white;
padding:16px;
border-radius:50%;
font-size:24px;
text-decoration:none;
z-index:999;">
💬
</a>
""",unsafe_allow_html=True)