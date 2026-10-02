import os
import re
import ast
import csv
import json
import base64
import qrcode
import urllib.parse
import matplotlib.pyplot as plt

from io import BytesIO, StringIO
from datetime import datetime
from collections import defaultdict

import streamlit as st
import streamlit.components.v1 as components

from PIL import Image

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage
)

from reportlab.lib.styles import (
    getSampleStyleSheet
)

from streamlit_drawable_canvas import (
    st_canvas
)

from database import (
    hash_password,
    crear_tablas,

    obtener_ordenes,
    obtener_orden,
    crear_orden,
    actualizar_orden,
    actualizar_estado,
    eliminar_orden,
    contar_ordenes,
    sumar_ingresos,
    contar_por_estado,
    contar_pendientes,

    obtener_usuarios,
    obtener_usuario_por_nombre,
    crear_usuario,
    actualizar_usuario,
    eliminar_usuario,

    obtener_inventario,
    obtener_producto,
    crear_producto,
    actualizar_producto,
    eliminar_producto,

    obtener_gastos,
    crear_gasto,
    sumar_gastos,
    eliminar_gasto,

    crear_venta,
    obtener_ventas,
    eliminar_venta,
    sumar_ventas,
    contar_ventas,

    crear_corte_mensual,
    obtener_cortes_mensuales,

    obtener_diagnostico_db
)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

ICONO = (
    "logo.png"
    if os.path.exists("logo.png")
    else "🔧"
)

st.set_page_config(
    page_title="Electronic Tech Service",
    page_icon=ICONO,
    layout="wide",
    initial_sidebar_state="auto"
)


# ==========================================================
# ESTILO
# ==========================================================

st.markdown("""
<style>

/* Fondo general */
.stApp {
    background:
        radial-gradient(
            circle at top,
            #101047 0%,
            #07071f 40%,
            #040412 100%
        );

    color: white;
}

/* Limitar ancho en pantallas grandes */
.block-container {
    max-width: 1200px;
    padding-top: 1.4rem;
    padding-bottom: 5rem;
}

/* Títulos */
h1, h2, h3 {
    color: #ffffff;
}

/* Botones */
.stButton > button,
.stDownloadButton > button,
[data-testid="stLinkButton"] > a {

    background:
        linear-gradient(
            135deg,
            #00e5ff,
            #00b8d4
        );

    color: #001014;

    font-weight: 800;

    border: none;

    border-radius: 16px;

    min-height: 46px;

    width: 100%;

    box-shadow:
        0 6px 18px
        rgba(0,229,255,.15);
}

.stButton > button:hover,
.stDownloadButton > button:hover {

    transform: translateY(-1px);

    border: none;

    color: #001014;
}

/* Entradas */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {

    border-radius: 14px !important;
}

/* Select */
div[data-baseweb="select"] > div {

    border-radius: 14px !important;
}

/* Tarjetas de métricas */
div[data-testid="stMetric"] {

    background:
        linear-gradient(
            145deg,
            #12123b,
            #0c0c2c
        );

    border: 1px solid
        rgba(0,229,255,.18);

    padding: 16px;

    border-radius: 18px;

    box-shadow:
        0 8px 30px
        rgba(0,0,0,.15);
}

/* Contenedores con borde */
div[data-testid="stVerticalBlockBorderWrapper"] {

    background:
        rgba(15,15,50,.7);

    border-radius: 18px;
}

/* Tabs */
button[data-baseweb="tab"] {

    font-weight: 700;
}

/* Sidebar */
section[data-testid="stSidebar"] {

    background:
        linear-gradient(
            180deg,
            #0a0a28,
            #05051b
        );
}

/* Ocultar footer */
footer {
    visibility: hidden;
}

/* Móvil */
@media (max-width: 768px) {

    .block-container {
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        padding-top: 0.8rem;
    }

    h1 {
        font-size: 1.65rem !important;
    }

    h2 {
        font-size: 1.35rem !important;
    }

    h3 {
        font-size: 1.15rem !important;
    }

    .stButton > button,
    .stDownloadButton > button {

        min-height: 50px;

        border-radius: 15px;
    }

}

/* Botón flotante */
.whatsapp-float {

    position: fixed;

    bottom: 20px;

    right: 20px;

    width: 58px;

    height: 58px;

    background: #25D366;

    color: white;

    border-radius: 50%;

    display: flex;

    align-items: center;

    justify-content: center;

    font-size: 27px;

    text-decoration: none;

    box-shadow:
        0 6px 24px
        rgba(0,0,0,.28);

    z-index: 9999;
}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# INICIALIZAR BASE DE DATOS
# ==========================================================

try:

    crear_tablas()

except Exception as e:

    st.error(
        f"Error conectando con la base de datos: {e}"
    )

    st.info(
        "Verifica DATABASE_URL en "
        "Secrets de Streamlit."
    )

    st.stop()


# ==========================================================
# CARPETA TEMPORAL
# ==========================================================

ASSETS = "assets"

os.makedirs(
    ASSETS,
    exist_ok=True
)


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================

def imagen_base64(upload):

    """
    Reduce tamaño de imágenes antes de
    guardarlas en PostgreSQL.
    """

    imagen = Image.open(upload)

    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")

    imagen.thumbnail(
        (1600, 1600)
    )

    buffer = BytesIO()

    imagen.save(
        buffer,
        format="JPEG",
        quality=82,
        optimize=True
    )

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")


def mostrar_base64(texto):

    if not texto:
        return None

    return base64.b64decode(
        texto
    )


def normalizar_whatsapp(telefono):

    numeros = re.sub(
        r"\D",
        "",
        str(telefono or "")
    )

    if not numeros:
        return ""

    # Si ya tiene Colombia
    if numeros.startswith("57"):
        return numeros

    return f"57{numeros}"


def crear_qr(texto):

    qr = qrcode.QRCode(
        box_size=8,
        border=2
    )

    qr.add_data(texto)

    qr.make(
        fit=True
    )

    img = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    nombre = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        str(texto)
    )

    ruta = os.path.join(
        ASSETS,
        f"{nombre}.png"
    )

    img.save(ruta)

    return ruta


def crear_pdf(orden):

    ruta = os.path.join(
        ASSETS,
        f"Recibo_{orden['id']}.pdf"
    )

    doc = SimpleDocTemplate(
        ruta
    )

    estilos = getSampleStyleSheet()

    elementos = []

    if os.path.exists("logo.png"):

        elementos.append(
            RLImage(
                "logo.png",
                100,
                100
            )
        )

    elementos.append(
        Paragraph(
            "<b>Electronic Tech Service</b>",
            estilos["Title"]
        )
    )

    elementos.append(
        Paragraph(
            "Montería - Córdoba",
            estilos["Normal"]
        )
    )

    elementos.append(
        Spacer(1, 12)
    )

    campos = [

        (
            "Orden",
            orden["id"]
        ),

        (
            "Fecha",
            orden["fecha"]
        ),

        (
            "Cliente",
            orden["cliente"]
        ),

        (
            "Teléfono",
            orden["telefono"] or ""
        ),

        (
            "Equipo",
            orden["equipo"]
        ),

        (
            "Problema",
            orden["problema"] or ""
        ),

        (
            "Estado",
            orden["estado"]
        )
    ]

    for clave, valor in campos:

        elementos.append(
            Paragraph(
                f"<b>{clave}:</b> {valor}",
                estilos["Normal"]
            )
        )

    elementos.append(
        Paragraph(
            f"<b>Total:</b> "
            f"${float(orden['precio_estimado'] or 0):,.0f}",
            estilos["Normal"]
        )
    )

    qr = crear_qr(
        f"ETS_{orden['id']}"
    )

    elementos.append(
        Spacer(1, 10)
    )

    elementos.append(
        RLImage(
            qr,
            100,
            100
        )
    )

    elementos.append(
        Spacer(1, 10)
    )

    elementos.append(
        Paragraph(
            "Gracias por confiar en "
            "Electronic Tech Service.",
            estilos["Italic"]
        )
    )

    doc.build(
        elementos
    )

    return ruta


# ==========================================================
# LOGIN
# ==========================================================

if "logged_in" not in st.session_state:

    st.session_state.logged_in = False

    st.session_state.usuario = ""

    st.session_state.rol = ""


if not st.session_state.logged_in:

    _, centro, _ = st.columns(
        [1, 1.5, 1]
    )

    with centro:

        if os.path.exists("logo.png"):

            st.image(
                "logo.png",
                width=220
            )

        st.title(
            "Electronic Tech Service"
        )

        st.caption(
            "Sistema de gestión técnica"
        )

        usuario = st.text_input(
            "Usuario"
        )

        clave = st.text_input(
            "Contraseña",
            type="password"
        )

        if st.button(
            "🔐 Entrar",
            use_container_width=True
        ):

            user = obtener_usuario_por_nombre(
                usuario
            )

            if (
                user
                and user["password"]
                == hash_password(clave)
            ):

                st.session_state.logged_in = True

                st.session_state.usuario = (
                    user["usuario"]
                )

                st.session_state.rol = (
                    user["rol"]
                )

                st.rerun()

            else:

                st.error(
                    "Usuario o contraseña incorrectos."
                )

    st.stop()


# ==========================================================
# CABECERA
# ==========================================================

cab_logo, cab_texto = st.columns(
    [1, 5]
)

with cab_logo:

    if os.path.exists("logo.png"):

        st.image(
            "logo.png",
            width=90
        )

with cab_texto:

    st.title(
        "Electronic Tech Service"
    )

    st.caption(
        f"👤 {st.session_state.usuario} "
        f"• {st.session_state.rol}"
    )


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.markdown(
    "## 🔧 Electronic Tech"
)

st.sidebar.caption(
    f"Sesión: {st.session_state.usuario}"
)

st.sidebar.markdown("---")


if "opcion" not in st.session_state:

    st.session_state.opcion = "🏠 Inicio"


def seleccionar_opcion(
    texto
):

    if st.sidebar.button(
        texto,
        use_container_width=True
    ):

        st.session_state.opcion = texto

        st.rerun()


seleccionar_opcion(
    "🏠 Inicio"
)

seleccionar_opcion(
    "➕ Nueva Reparación"
)

seleccionar_opcion(
    "📋 Ver Órdenes"
)

seleccionar_opcion(
    "🔍 Buscar"
)

seleccionar_opcion(
    "📄 Cotizaciones"
)

seleccionar_opcion(
    "🖨️ Recibos"
)

seleccionar_opcion(
    "🛒 Ventas"
)

seleccionar_opcion(
    "📤 Exportar"
)

seleccionar_opcion(
    "📍 Taller"
)


if st.session_state.rol == "admin":

    st.sidebar.markdown("---")

    st.sidebar.markdown(
        "### Administración"
    )

    seleccionar_opcion(
        "📦 Inventario"
    )

    seleccionar_opcion(
        "📊 Contabilidad"
    )

    seleccionar_opcion(
        "💸 Gastos"
    )

    seleccionar_opcion(
        "📅 Corte Mensual"
    )

    seleccionar_opcion(
        "👥 Usuarios"
    )

    seleccionar_opcion(
        "🛡️ Sistema"
    )


st.sidebar.markdown("---")


if st.sidebar.button(
    "🚪 Cerrar sesión",
    use_container_width=True
):

    st.session_state.logged_in = False

    st.session_state.usuario = ""

    st.session_state.rol = ""

    st.session_state.opcion = "🏠 Inicio"

    st.rerun()


opcion = st.session_state.opcion


# ==========================================================
# INICIO
# ==========================================================

if opcion == "🏠 Inicio":

    st.subheader(
        "🏠 Panel principal"
    )

    ingresos_reparaciones = (
        sumar_ingresos()
    )

    ingresos_ventas = (
        sumar_ventas()
    )

    ingresos = (
        ingresos_reparaciones
        + ingresos_ventas
    )

    pendientes = (
        contar_pendientes()
    )

    listos = (
        contar_por_estado("Listo")
    )

    total = (
        contar_ordenes()
    )

    total_ventas = (
        contar_ventas()
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "🔧 Órdenes",
        total
    )

    c2.metric(
        "🛒 Ventas",
        total_ventas
    )

    c3, c4 = st.columns(2)

    c3.metric(
        "⏳ Pendientes",
        pendientes
    )

    c4.metric(
        "✅ Listos",
        listos
    )

    st.metric(
        "💰 Ingresos registrados",
        f"${ingresos:,.0f}"
    )

    st.caption(
        f"Reparaciones: "
        f"${ingresos_reparaciones:,.0f} "
        f"• Ventas: "
        f"${ingresos_ventas:,.0f}"
    )

    st.markdown("---")

    ordenes = obtener_ordenes()

    st.subheader(
        "Últimas órdenes"
    )

    if ordenes:

        data = []

        for o in ordenes[:7]:

            data.append({

                "ID":
                    o["id"],

                "Fecha":
                    o["fecha"],

                "Cliente":
                    o["cliente"],

                "Equipo":
                    o["equipo"],

                "Estado":
                    o["estado"],

                "Precio":
                    o["precio_estimado"]
            })

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "Todavía no hay órdenes."
        )


# ==========================================================
# NUEVA REPARACIÓN
# ==========================================================

elif opcion == "➕ Nueva Reparación":

    st.subheader(
        "➕ Nueva orden de reparación"
    )

    c1, c2 = st.columns(2)

    with c1:

        cliente = st.text_input(
            "Cliente"
        )

        telefono = st.text_input(
            "Teléfono / WhatsApp"
        )

        equipo = st.text_input(
            "Equipo"
        )

    with c2:

        problema = st.text_area(
            "Problema reportado"
        )

        precio = st.number_input(
            "Precio estimado",
            min_value=0,
            step=1000
        )

        estado = st.selectbox(
            "Estado",
            [
                "Recibido",
                "En reparación",
                "Listo",
                "Entregado"
            ]
        )

    st.markdown(
        "### 📷 Evidencia fotográfica"
    )

    antes = st.file_uploader(
        "Foto antes",
        type=[
            "jpg",
            "jpeg",
            "png"
        ],
        key="foto_antes"
    )

    durante = st.file_uploader(
        "Foto durante",
        type=[
            "jpg",
            "jpeg",
            "png"
        ],
        key="foto_durante"
    )

    despues = st.file_uploader(
        "Foto después",
        type=[
            "jpg",
            "jpeg",
            "png"
        ],
        key="foto_despues"
    )

    st.markdown(
        "### ✍️ Firma del cliente"
    )

    canvas = st_canvas(
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=180,
        width=320,
        drawing_mode="freedraw",
        key="firma_canvas"
    )

    if st.button(
        "💾 Guardar orden",
        type="primary",
        use_container_width=True
    ):

        if not cliente.strip():

            st.error(
                "El nombre del cliente es obligatorio."
            )

        elif not equipo.strip():

            st.error(
                "El equipo es obligatorio."
            )

        else:

            try:

                fotos = {}

                if antes:

                    fotos["antes"] = (
                        imagen_base64(
                            antes
                        )
                    )

                if durante:

                    fotos["durante"] = (
                        imagen_base64(
                            durante
                        )
                    )

                if despues:

                    fotos["despues"] = (
                        imagen_base64(
                            despues
                        )
                    )

                firma = ""

                if canvas.image_data is not None:

                    img = Image.fromarray(
                        canvas.image_data.astype(
                            "uint8"
                        )
                    )

                    buffer = BytesIO()

                    img.save(
                        buffer,
                        format="PNG"
                    )

                    firma = (
                        base64.b64encode(
                            buffer.getvalue()
                        ).decode("utf-8")
                    )

                nuevo_id = crear_orden(

                    cliente=cliente,

                    telefono=telefono,

                    equipo=equipo,

                    problema=problema,

                    precio=precio,

                    estado=estado,

                    tecnico=(
                        st.session_state.usuario
                    ),

                    fotos=str(fotos),

                    firma=firma
                )

                st.success(
                    f"✅ Orden #{nuevo_id} "
                    f"creada correctamente."
                )

                st.balloons()

            except Exception as e:

                st.error(
                    f"No fue posible guardar "
                    f"la orden: {e}"
                )


# ==========================================================
# VER ÓRDENES
# ==========================================================

elif opcion == "📋 Ver Órdenes":

    st.subheader(
        "📋 Órdenes"
    )

    ordenes = obtener_ordenes()

    if not ordenes:

        st.info(
            "No hay órdenes registradas."
        )

    else:

        ids = [
            o["id"]
            for o in ordenes
        ]

        if (
            "orden_seleccionada"
            not in st.session_state
        ):

            st.session_state.orden_seleccionada = (
                ids[0]
            )

        if (
            st.session_state.orden_seleccionada
            not in ids
        ):

            st.session_state.orden_seleccionada = (
                ids[0]
            )

        id_seleccionado = st.selectbox(

            "Selecciona una orden",

            options=ids,

            index=ids.index(
                st.session_state.orden_seleccionada
            ),

            format_func=lambda x:
                f"#{x} - "
                f"{next((o['cliente'] for o in ordenes if o['id'] == x), '')}",

            key="select_orden"
        )

        st.session_state.orden_seleccionada = (
            id_seleccionado
        )

        orden = obtener_orden(
            id_seleccionado
        )

        if orden:

            col1, col2 = st.columns(
                [1, 2]
            )

            with col1:

                try:

                    fotos = ast.literal_eval(
                        orden["fotos"] or "{}"
                    )

                except Exception:

                    fotos = {}

                for nombre in [
                    "antes",
                    "durante",
                    "despues"
                ]:

                    if (
                        nombre in fotos
                        and fotos[nombre]
                    ):

                        st.image(
                            mostrar_base64(
                                fotos[nombre]
                            ),
                            caption=nombre.capitalize(),
                            use_container_width=True
                        )

            with col2:

                st.markdown(
                    f"### Orden #{orden['id']}"
                )

                st.write(
                    "**Fecha:**",
                    orden["fecha"]
                )

                st.write(
                    "**Cliente:**",
                    orden["cliente"]
                )

                st.write(
                    "**Teléfono:**",
                    orden["telefono"] or ""
                )

                st.write(
                    "**Equipo:**",
                    orden["equipo"]
                )

                st.write(
                    "**Problema:**",
                    orden["problema"] or ""
                )

                st.write(
                    "**Estado:**",
                    orden["estado"]
                )

                st.write(
                    "**Pago:**",
                    orden["pagado"]
                )

                st.write(
                    "**Precio:**",
                    f"${float(orden['precio_estimado'] or 0):,.0f}"
                )

                if orden["firma"]:

                    st.image(
                        mostrar_base64(
                            orden["firma"]
                        ),
                        caption="Firma del cliente",
                        width=250
                    )

                estados = [
                    "Recibido",
                    "En reparación",
                    "Listo",
                    "Entregado"
                ]

                idx = (
                    estados.index(
                        orden["estado"]
                    )
                    if orden["estado"] in estados
                    else 0
                )

                nuevo_estado = st.selectbox(
                    "Cambiar estado",
                    estados,
                    index=idx,
                    key=f"est_{orden['id']}"
                )

                if st.button(
                    "Actualizar estado",
                    key=f"btn_est_{orden['id']}",
                    use_container_width=True
                ):

                    actualizar_estado(
                        orden["id"],
                        nuevo_estado
                    )

                    st.success(
                        "Estado actualizado."
                    )

                    st.rerun()

                numero = normalizar_whatsapp(
                    orden["telefono"]
                )

                if numero:

                    mensaje = urllib.parse.quote(
                        f"Hola {orden['cliente']}, "
                        f"tu equipo "
                        f"({orden['equipo']}) "
                        f"está en estado: "
                        f"{nuevo_estado}."
                    )

                    st.link_button(
                        "📲 Enviar WhatsApp",
                        f"https://wa.me/{numero}"
                        f"?text={mensaje}",
                        use_container_width=True
                    )

            if st.session_state.rol == "admin":

                st.markdown("---")

                with st.expander(
                    "✏️ Editar orden completa"
                ):

                    with st.form(
                        key=f"form_edit_{orden['id']}"
                    ):

                        cliente2 = st.text_input(
                            "Cliente",
                            value=orden["cliente"]
                        )

                        telefono2 = st.text_input(
                            "Teléfono",
                            value=(
                                orden["telefono"]
                                or ""
                            )
                        )

                        equipo2 = st.text_input(
                            "Equipo",
                            value=orden["equipo"]
                        )

                        problema2 = st.text_area(
                            "Problema",
                            value=(
                                orden["problema"]
                                or ""
                            )
                        )

                        precio2 = st.number_input(
                            "Precio estimado",
                            value=float(
                                orden["precio_estimado"]
                                or 0
                            ),
                            step=1000.0
                        )

                        estado2 = st.selectbox(
                            "Estado",
                            estados,
                            index=idx,
                            key=f"estado_edit_{orden['id']}"
                        )

                        notas2 = st.text_area(
                            "Notas",
                            value=(
                                orden["notas"]
                                or ""
                            )
                        )

                        opciones_pagado = [
                            "Pendiente",
                            "Parcial",
                            "Pagado"
                        ]

                        idx_pag = (
                            opciones_pagado.index(
                                orden["pagado"]
                            )
                            if orden["pagado"]
                            in opciones_pagado
                            else 0
                        )

                        pagado2 = st.selectbox(
                            "Pago",
                            opciones_pagado,
                            index=idx_pag,
                            key=f"pago_edit_{orden['id']}"
                        )

                        confirmar_eliminar = (
                            st.checkbox(
                                "Confirmo que deseo "
                                "eliminar esta orden"
                            )
                        )

                        col_g, col_e = st.columns(2)

                        guardar = (
                            col_g.form_submit_button(
                                "💾 Guardar cambios"
                            )
                        )

                        eliminar = (
                            col_e.form_submit_button(
                                "🗑️ Eliminar"
                            )
                        )

                        if guardar:

                            actualizar_orden(

                                orden["id"],

                                cliente=cliente2,

                                telefono=telefono2,

                                equipo=equipo2,

                                problema=problema2,

                                precio_estimado=precio2,

                                estado=estado2,

                                notas=notas2,

                                pagado=pagado2
                            )

                            st.success(
                                "Orden actualizada."
                            )

                            st.rerun()

                        if eliminar:

                            if not confirmar_eliminar:

                                st.error(
                                    "Marca la casilla de "
                                    "confirmación."
                                )

                            else:

                                eliminar_orden(
                                    orden["id"]
                                )

                                st.success(
                                    "Orden eliminada."
                                )

                                st.rerun()


# ==========================================================
# BUSCAR
# ==========================================================

elif opcion == "🔍 Buscar":

    st.subheader(
        "🔍 Buscar"
    )

    texto = st.text_input(
        "Cliente, teléfono, equipo o ID"
    )

    if texto:

        ordenes = obtener_ordenes()

        resultados = []

        texto_lower = (
            texto
            .strip()
            .lower()
        )

        for o in ordenes:

            if (
                texto_lower
                in str(
                    o["cliente"]
                ).lower()

                or texto_lower
                in str(
                    o["telefono"] or ""
                ).lower()

                or texto_lower
                in str(
                    o["equipo"]
                ).lower()

                or texto_lower
                in str(
                    o["id"]
                ).lower()
            ):

                resultados.append(
                    o
                )

        st.write(
            f"{len(resultados)} "
            f"resultado(s)"
        )

        if resultados:

            data = [

                {
                    "ID":
                        o["id"],

                    "Fecha":
                        o["fecha"],

                    "Cliente":
                        o["cliente"],

                    "Teléfono":
                        o["telefono"],

                    "Equipo":
                        o["equipo"],

                    "Estado":
                        o["estado"],

                    "Precio":
                        o["precio_estimado"]
                }

                for o in resultados
            ]

            st.dataframe(
                data,
                use_container_width=True,
                hide_index=True
            )

            cliente_historial = (
                resultados[0]["cliente"]
            )

            st.markdown("---")

            st.subheader(
                f"Historial de "
                f"{cliente_historial}"
            )

            historial = [

                o
                for o in ordenes

                if o["cliente"]
                == cliente_historial
            ]

            data_h = [

                {
                    "ID":
                        o["id"],

                    "Fecha":
                        o["fecha"],

                    "Equipo":
                        o["equipo"],

                    "Estado":
                        o["estado"],

                    "Precio":
                        o["precio_estimado"]
                }

                for o in historial
            ]

            st.dataframe(
                data_h,
                use_container_width=True,
                hide_index=True
            )


# ==========================================================
# RECIBOS
# ==========================================================

elif opcion == "🖨️ Recibos":

    st.subheader(
        "🖨️ Recibos"
    )

    ordenes = obtener_ordenes()

    if not ordenes:

        st.info(
            "No hay órdenes."
        )

    else:

        ids = [
            o["id"]
            for o in ordenes
        ]

        id_recibo = st.selectbox(
            "Selecciona una orden",
            ids
        )

        orden = obtener_orden(
            id_recibo
        )

        st.write(
            "**Cliente:**",
            orden["cliente"]
        )

        st.write(
            "**Equipo:**",
            orden["equipo"]
        )

        st.write(
            "**Estado:**",
            orden["estado"]
        )

        st.write(
            "**Total:**",
            f"${float(orden['precio_estimado'] or 0):,.0f}"
        )

        qr = crear_qr(
            f"ETS_{orden['id']}"
        )

        st.image(
            qr,
            width=140
        )

        pdf = crear_pdf(
            orden
        )

        with open(
            pdf,
            "rb"
        ) as archivo_pdf:

            st.download_button(

                "📄 Descargar recibo PDF",

                data=archivo_pdf.read(),

                file_name=(
                    f"Recibo_{orden['id']}.pdf"
                ),

                mime="application/pdf",

                use_container_width=True
            )

        ticket = f"""
Electronic Tech Service

Orden #{orden['id']}

Fecha:
{orden['fecha']}

Cliente:
{orden['cliente']}

Equipo:
{orden['equipo']}

Estado:
{orden['estado']}

Total:
${float(orden['precio_estimado'] or 0):,.0f}

WhatsApp:
3014874740

Gracias por preferirnos.
"""

        st.download_button(

            "🧾 Descargar ticket",

            ticket,

            file_name=(
                f"Ticket_{orden['id']}.txt"
            ),

            mime="text/plain",

            use_container_width=True
        )


# ==========================================================
# COTIZACIONES
# ==========================================================

elif opcion == "📄 Cotizaciones":

    st.subheader(
        "📄 Cotización de cámaras"
    )

    st.markdown(
        "### Datos del cliente"
    )

    c1, c2 = st.columns(2)

    with c1:

        cliente = st.text_input(
            "Cliente / Empresa",
            key="cot_cliente"
        )

        telefono = st.text_input(
            "Teléfono",
            key="cot_tel"
        )

        direccion_cliente = (
            st.text_input(
                "Dirección",
                key="cot_dir"
            )
        )

    with c2:

        fecha_cot = st.date_input(
            "Fecha",
            value=datetime.now().date()
        )

        validez = st.number_input(
            "Validez (días)",
            min_value=1,
            value=15,
            key="cot_validez"
        )

        forma_pago = st.selectbox(
            "Forma de pago",
            [
                "Efectivo",
                "Transferencia",
                "50% anticipo - 50% entrega",
                "Otro"
            ],
            key="cot_pago"
        )

    st.markdown(
        "### Detalle del sistema"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        tipo_camara = st.selectbox(
            "Tipo de cámara",
            [
                "IP (Red)",
                "Analógica HD",
                "WiFi",
                "PTZ",
                "Otra"
            ],
            key="cot_tipo"
        )

        cantidad_camaras = (
            st.number_input(
                "Cantidad",
                min_value=1,
                value=4,
                key="cot_cant"
            )
        )

    with col2:

        resolucion = st.selectbox(
            "Resolución",
            [
                "2MP",
                "4MP",
                "5MP",
                "8MP (4K)",
                "Otra"
            ],
            key="cot_res"
        )

        incluye_audio = st.checkbox(
            "Incluye audio",
            key="cot_audio"
        )

    with col3:

        dvr_nvr = st.selectbox(
            "Grabador",
            [
                "NVR",
                "DVR",
                "No incluye",
                "Otro"
            ],
            key="cot_grabador"
        )

        discos = st.number_input(
            "Almacenamiento (TB)",
            min_value=0,
            value=1,
            step=1,
            key="cot_discos"
        )

    descripcion = st.text_area(

        "Descripción del servicio",

        value=(
            "Instalación de sistema de videovigilancia, "
            "configuración de grabación, acceso remoto "
            "por celular y capacitación básica al cliente."
        ),

        key="cot_desc",

        height=120
    )

    st.markdown(
        "### Costos"
    )

    c1, c2 = st.columns(2)

    with c1:

        precio_camaras = (
            st.number_input(
                "Cámaras ($)",
                min_value=0,
                step=10000,
                key="cot_p_cam"
            )
        )

        precio_grabador = (
            st.number_input(
                "Grabador + Disco ($)",
                min_value=0,
                step=10000,
                key="cot_p_grab"
            )
        )

        precio_cableado = (
            st.number_input(
                "Cableado y accesorios ($)",
                min_value=0,
                step=10000,
                key="cot_p_cab"
            )
        )

    with c2:

        precio_mano_obra = (
            st.number_input(
                "Mano de obra ($)",
                min_value=0,
                step=10000,
                key="cot_p_mo"
            )
        )

        otros = st.number_input(
            "Otros costos ($)",
            min_value=0,
            step=5000,
            key="cot_otros"
        )

        descuento = st.number_input(
            "Descuento ($)",
            min_value=0,
            step=5000,
            key="cot_desc_monto"
        )

    subtotal = (
        precio_camaras
        + precio_grabador
        + precio_cableado
        + precio_mano_obra
        + otros
    )

    total = max(
        subtotal - descuento,
        0
    )

    st.metric(
        "Total cotización",
        f"${total:,.0f}"
    )

    if st.button(
        "Generar cotización",
        type="primary",
        use_container_width=True
    ):

        logo_html = ""

        if os.path.exists("logo.png"):

            with open(
                "logo.png",
                "rb"
            ) as f:

                logo_b64 = (
                    base64.b64encode(
                        f.read()
                    ).decode()
                )

            logo_html = (
                f'<img '
                f'src="data:image/png;base64,{logo_b64}" '
                f'width="110">'
            )

        audio_texto = (
            "Sí"
            if incluye_audio
            else "No"
        )

        fecha_str = (
            fecha_cot.strftime(
                "%d/%m/%Y"
            )
        )

        cotizacion_html = f"""
<div style="
background:white;
color:#111;
padding:28px;
border-radius:14px;
font-family:Arial,sans-serif;
max-width:820px;
margin:auto;
">

<div style="
text-align:center;
border-bottom:3px solid #00E5FF;
padding-bottom:15px;
margin-bottom:20px;
">
{logo_html}

<h1 style="
color:#05051b;
font-size:26px;
margin:8px 0;
">
Electronic Tech Service
</h1>

<p style="color:#555;">
Montería, Córdoba<br>
WhatsApp: 301 487 4740
</p>
</div>

<h2 style="
text-align:center;
color:#05051b;
">
COTIZACIÓN DE SISTEMA DE
CÁMARAS DE SEGURIDAD
</h2>

<p style="
text-align:center;
color:#666;
">
Fecha: {fecha_str}
•
Validez: {validez} días
</p>

<hr>

<p>
<b>Cliente:</b>
{cliente or "________________"}
</p>

<p>
<b>Teléfono:</b>
{telefono or "________________"}
</p>

<p>
<b>Dirección:</b>
{direccion_cliente or "________________"}
</p>

<h3>Detalle del sistema</h3>

<table style="
width:100%;
border-collapse:collapse;
">

<tr>
<td style="padding:8px;border:1px solid #ddd;">
<b>Tipo</b>
</td>

<td style="padding:8px;border:1px solid #ddd;">
{tipo_camara}
</td>

<td style="padding:8px;border:1px solid #ddd;">
<b>Cantidad</b>
</td>

<td style="padding:8px;border:1px solid #ddd;">
{cantidad_camaras}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
<b>Resolución</b>
</td>

<td style="padding:8px;border:1px solid #ddd;">
{resolucion}
</td>

<td style="padding:8px;border:1px solid #ddd;">
<b>Audio</b>
</td>

<td style="padding:8px;border:1px solid #ddd;">
{audio_texto}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
<b>Grabador</b>
</td>

<td style="padding:8px;border:1px solid #ddd;">
{dvr_nvr}
</td>

<td style="padding:8px;border:1px solid #ddd;">
<b>Almacenamiento</b>
</td>

<td style="padding:8px;border:1px solid #ddd;">
{discos} TB
</td>
</tr>

</table>

<h3>Descripción</h3>

<p>
{descripcion}
</p>

<h3>Costos</h3>

<table style="
width:100%;
border-collapse:collapse;
">

<tr>
<td style="padding:8px;border:1px solid #ddd;">
Cámaras
</td>
<td style="padding:8px;border:1px solid #ddd;text-align:right;">
${precio_camaras:,.0f}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
Grabador + Disco
</td>
<td style="padding:8px;border:1px solid #ddd;text-align:right;">
${precio_grabador:,.0f}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
Cableado y accesorios
</td>
<td style="padding:8px;border:1px solid #ddd;text-align:right;">
${precio_cableado:,.0f}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
Mano de obra
</td>
<td style="padding:8px;border:1px solid #ddd;text-align:right;">
${precio_mano_obra:,.0f}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
Otros
</td>
<td style="padding:8px;border:1px solid #ddd;text-align:right;">
${otros:,.0f}
</td>
</tr>

<tr>
<td style="padding:8px;border:1px solid #ddd;">
Descuento
</td>
<td style="padding:8px;border:1px solid #ddd;text-align:right;">
-${descuento:,.0f}
</td>
</tr>

<tr style="
background:#05051b;
color:white;
font-weight:bold;
font-size:17px;
">
<td style="padding:12px;">
TOTAL
</td>
<td style="padding:12px;text-align:right;">
${total:,.0f}
</td>
</tr>

</table>

<p>
<b>Forma de pago:</b>
{forma_pago}
</p>

<hr>

<p style="
text-align:center;
font-size:12px;
color:#666;
">
Electronic Tech Service<br>
Montería, Córdoba<br>
WhatsApp: 301 487 4740
</p>

</div>
"""

        components.html(
            cotizacion_html,
            height=1200,
            scrolling=True
        )

        st.success(
            "Cotización generada."
        )


# ==========================================================
# INVENTARIO
# ==========================================================

elif opcion == "📦 Inventario":

    st.subheader(
        "📦 Inventario"
    )

    tab1, tab2 = st.tabs(
        [
            "Productos",
            "Agregar producto"
        ]
    )

    with tab1:

        productos = obtener_inventario()

        if not productos:

            st.info(
                "No hay productos."
            )

        else:

            for p in productos:

                if p["cantidad"] <= 5:

                    color = "🔴"

                elif p["cantidad"] <= 10:

                    color = "🟡"

                else:

                    color = "🟢"

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"### {color} "
                        f"{p['producto']}"
                    )

                    c1, c2 = st.columns(2)

                    c1.metric(
                        "Stock",
                        p["cantidad"]
                    )

                    c2.metric(
                        "Precio",
                        f"${float(p['precio_unitario'] or 0):,.0f}"
                    )

                    nueva = st.number_input(

                        "Nueva cantidad",

                        min_value=0,

                        value=int(
                            p["cantidad"]
                        ),

                        key=f"cant_{p['id']}"
                    )

                    c3, c4 = st.columns(2)

                    if c3.button(
                        "Actualizar",
                        key=f"up_{p['id']}"
                    ):

                        actualizar_producto(
                            p["id"],
                            cantidad=nueva
                        )

                        st.rerun()

                    if c4.button(
                        "Eliminar",
                        key=f"del_{p['id']}"
                    ):

                        eliminar_producto(
                            p["id"]
                        )

                        st.rerun()

    with tab2:

        prod = st.text_input(
            "Producto"
        )

        cant = st.number_input(
            "Cantidad",
            min_value=1,
            value=1
        )

        precio = st.number_input(
            "Precio unitario",
            min_value=0,
            step=1000,
            key="inv_precio"
        )

        if st.button(
            "Guardar producto",
            use_container_width=True
        ):

            if prod.strip():

                crear_producto(
                    prod,
                    cant,
                    precio
                )

                st.success(
                    "Producto agregado."
                )

                st.rerun()

            else:

                st.error(
                    "El nombre es obligatorio."
                )


# ==========================================================
# CONTABILIDAD
# ==========================================================

elif opcion == "📊 Contabilidad":

    st.subheader(
        "📊 Contabilidad"
    )

    ingresos_reparaciones = (
        sumar_ingresos()
    )

    ingresos_ventas = (
        sumar_ventas()
    )

    ingresos = (
        ingresos_reparaciones
        + ingresos_ventas
    )

    egresos = (
        sumar_gastos()
    )

    utilidad = (
        ingresos
        - egresos
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Reparaciones",
        f"${ingresos_reparaciones:,.0f}"
    )

    c2.metric(
        "Ventas",
        f"${ingresos_ventas:,.0f}"
    )

    c3, c4 = st.columns(2)

    c3.metric(
        "Gastos",
        f"${egresos:,.0f}"
    )

    c4.metric(
        "Utilidad",
        f"${utilidad:,.0f}"
    )

    st.metric(
        "Ingresos totales",
        f"${ingresos:,.0f}"
    )

    st.markdown("---")

    st.subheader(
        "Ingresos por fuente"
    )

    fig, ax = plt.subplots()

    ax.bar(
        [
            "Reparaciones",
            "Ventas"
        ],
        [
            ingresos_reparaciones,
            ingresos_ventas
        ]
    )

    ax.set_ylabel(
        "Pesos"
    )

    st.pyplot(fig)

    plt.close(fig)

    ordenes = obtener_ordenes()

    if ordenes:

        st.subheader(
            "Reparaciones por estado"
        )

        por_estado = defaultdict(
            float
        )

        for o in ordenes:

            por_estado[
                o["estado"]
            ] += float(
                o["precio_estimado"]
                or 0
            )

        fig2, ax2 = plt.subplots()

        ax2.bar(
            list(
                por_estado.keys()
            ),
            list(
                por_estado.values()
            )
        )

        plt.xticks(
            rotation=20
        )

        st.pyplot(fig2)

        plt.close(fig2)

        st.subheader(
            "Equipos más reparados"
        )

        contador = defaultdict(
            int
        )

        for o in ordenes:

            contador[
                o["equipo"]
            ] += 1

        top = sorted(
            contador.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        if top:

            fig3, ax3 = plt.subplots()

            ax3.bar(
                [
                    t[0]
                    for t in top
                ],
                [
                    t[1]
                    for t in top
                ]
            )

            plt.xticks(
                rotation=25
            )

            st.pyplot(fig3)

            plt.close(fig3)

    ventas = obtener_ventas()

    if ventas:

        st.subheader(
            "Productos más vendidos"
        )

        contador_v = defaultdict(
            int
        )

        for v in ventas:

            contador_v[
                v["producto_nombre"]
            ] += int(
                v["cantidad"]
            )

        top_v = sorted(
            contador_v.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        if top_v:

            fig4, ax4 = plt.subplots()

            ax4.bar(
                [
                    t[0]
                    for t in top_v
                ],
                [
                    t[1]
                    for t in top_v
                ]
            )

            plt.xticks(
                rotation=25
            )

            st.pyplot(fig4)

            plt.close(fig4)


# ==========================================================
# GASTOS
# ==========================================================

elif opcion == "💸 Gastos":

    st.subheader(
        "💸 Gastos"
    )

    desc = st.text_input(
        "Descripción"
    )

    categoria = st.selectbox(
        "Categoría",
        [
            "Repuestos",
            "Herramientas",
            "Servicios",
            "Transporte",
            "Otros"
        ]
    )

    monto = st.number_input(
        "Monto",
        min_value=0,
        step=1000,
        key="gasto_monto"
    )

    if st.button(
        "Guardar gasto",
        use_container_width=True
    ):

        if desc.strip():

            crear_gasto(
                desc,
                monto,
                categoria
            )

            st.success(
                "Gasto registrado."
            )

            st.rerun()

        else:

            st.error(
                "La descripción es obligatoria."
            )

    st.markdown("---")

    gastos = obtener_gastos()

    if gastos:

        data = [

            {
                "ID":
                    g["id"],

                "Fecha":
                    g["fecha"],

                "Descripción":
                    g["descripcion"],

                "Monto":
                    g["monto"],

                "Categoría":
                    g["categoria"]
            }

            for g in gastos
        ]

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        ids_gastos = [
            g["id"]
            for g in gastos
        ]

        gasto_eliminar = st.selectbox(
            "Eliminar gasto por ID",
            ids_gastos
        )

        confirmar = st.checkbox(
            "Confirmo eliminar el gasto"
        )

        if st.button(
            "🗑️ Eliminar gasto",
            use_container_width=True
        ):

            if confirmar:

                eliminar_gasto(
                    gasto_eliminar
                )

                st.success(
                    "Gasto eliminado."
                )

                st.rerun()

            else:

                st.warning(
                    "Debes confirmar primero."
                )


# ==========================================================
# CORTE MENSUAL SEGURO
# ==========================================================

elif opcion == "📅 Corte Mensual":

    st.subheader(
        "📅 Corte mensual"
    )

    st.success(
        "El corte mensual ya NO borra "
        "órdenes ni información."
    )

    periodo_actual = (
        datetime.now().strftime(
            "%Y-%m"
        )
    )

    periodo = st.text_input(
        "Periodo",
        value=periodo_actual,
        help="Formato: AAAA-MM"
    )

    if not re.match(
        r"^\d{4}-\d{2}$",
        periodo
    ):

        st.warning(
            "Usa el formato AAAA-MM. "
            "Ejemplo: 2026-10"
        )

    else:

        if st.button(
            "📊 Realizar corte",
            type="primary",
            use_container_width=True
        ):

            try:

                resultado = (
                    crear_corte_mensual(
                        periodo,
                        st.session_state.usuario
                    )
                )

                st.success(
                    "✅ Corte guardado "
                    "sin eliminar información."
                )

                c1, c2 = st.columns(2)

                c1.metric(
                    "Órdenes",
                    resultado["ordenes"]
                )

                c2.metric(
                    "Reparaciones",
                    f"${resultado['reparaciones']:,.0f}"
                )

                c3, c4 = st.columns(2)

                c3.metric(
                    "Ventas",
                    f"${resultado['ventas']:,.0f}"
                )

                c4.metric(
                    "Gastos",
                    f"${resultado['gastos']:,.0f}"
                )

                st.metric(
                    "Utilidad",
                    f"${resultado['utilidad']:,.0f}"
                )

            except Exception as e:

                st.error(
                    f"Error realizando corte: {e}"
                )

    st.markdown("---")

    st.subheader(
        "Historial de cortes"
    )

    cortes = obtener_cortes_mensuales()

    if cortes:

        datos = [

            {
                "Periodo":
                    c["periodo"],

                "Fecha corte":
                    c["fecha_cierre"],

                "Órdenes":
                    c["total_ordenes"],

                "Reparaciones":
                    c["ingresos_reparaciones"],

                "Ventas":
                    c["ingresos_ventas"],

                "Gastos":
                    c["gastos"],

                "Utilidad":
                    c["utilidad"],

                "Usuario":
                    c["usuario"]
            }

            for c in cortes
        ]

        st.dataframe(
            datos,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No hay cortes registrados."
        )


# ==========================================================
# USUARIOS
# ==========================================================

elif opcion == "👥 Usuarios":

    st.subheader(
        "👥 Usuarios"
    )

    tab1, tab2 = st.tabs(
        [
            "Usuarios",
            "Nuevo"
        ]
    )

    with tab1:

        usuarios = obtener_usuarios()

        for u in usuarios:

            with st.container(
                border=True
            ):

                nombre = st.text_input(

                    "Usuario",

                    value=u["usuario"],

                    key=f"user_{u['id']}"
                )

                clave = st.text_input(

                    "Nueva contraseña",

                    type="password",

                    help=(
                        "Déjala vacía "
                        "para conservarla."
                    ),

                    key=f"pass_{u['id']}"
                )

                rol = st.selectbox(

                    "Rol",

                    [
                        "trabajador",
                        "admin"
                    ],

                    index=(
                        1
                        if u["rol"] == "admin"
                        else 0
                    ),

                    key=f"rol_{u['id']}"
                )

                c1, c2 = st.columns(2)

                if c1.button(
                    "Guardar",
                    key=f"save_{u['id']}"
                ):

                    datos = {

                        "usuario":
                            nombre,

                        "rol":
                            rol
                    }

                    if clave:

                        datos["password"] = (
                            clave
                        )

                    actualizar_usuario(
                        u["id"],
                        **datos
                    )

                    if (
                        st.session_state.usuario
                        == u["usuario"]
                    ):

                        st.session_state.usuario = (
                            nombre
                        )

                        st.session_state.rol = (
                            rol
                        )

                    st.success(
                        "Usuario actualizado."
                    )

                    st.rerun()

                if (
                    u["usuario"].lower()
                    != "admin"
                ):

                    if c2.button(
                        "Eliminar",
                        key=f"deluser_{u['id']}"
                    ):

                        eliminar_usuario(
                            u["id"]
                        )

                        st.success(
                            "Usuario eliminado."
                        )

                        st.rerun()

    with tab2:

        usuario_nuevo = st.text_input(
            "Nuevo usuario"
        )

        password_nuevo = st.text_input(
            "Contraseña",
            type="password",
            key="new_pass"
        )

        rol_nuevo = st.selectbox(
            "Rol",
            [
                "trabajador",
                "admin"
            ],
            key="new_role"
        )

        if st.button(
            "Crear usuario",
            use_container_width=True
        ):

            if (
                usuario_nuevo.strip()
                and password_nuevo
            ):

                try:

                    crear_usuario(
                        usuario_nuevo,
                        password_nuevo,
                        rol_nuevo
                    )

                    st.success(
                        "Usuario creado."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Error: {e}"
                    )

            else:

                st.error(
                    "Usuario y contraseña "
                    "son obligatorios."
                )


# ==========================================================
# VENTAS
# ==========================================================

elif opcion == "🛒 Ventas":

    st.subheader(
        "🛒 Ventas"
    )

    tab_vender, tab_historial = st.tabs(
        [
            "Vender",
            "Historial"
        ]
    )

    with tab_vender:

        productos = obtener_inventario()

        disponibles = [

            p
            for p in productos

            if (
                p["cantidad"]
                or 0
            ) > 0
        ]

        if not disponibles:

            st.warning(
                "No hay productos con stock."
            )

        else:

            opciones = {

                (
                    f"{p['producto']} "
                    f"• Stock: {p['cantidad']} "
                    f"• ${float(p['precio_unitario'] or 0):,.0f}"
                ):
                    p

                for p in disponibles
            }

            elegido = st.selectbox(
                "Producto",
                list(
                    opciones.keys()
                )
            )

            prod = opciones[
                elegido
            ]

            cantidad = st.number_input(

                "Cantidad",

                min_value=1,

                max_value=int(
                    prod["cantidad"]
                ),

                value=1,

                key="venta_cant"
            )

            cliente_v = st.text_input(
                "Cliente (opcional)",
                key="venta_cliente"
            )

            notas_v = st.text_input(
                "Notas (opcional)",
                key="venta_notas"
            )

            total_venta = (
                float(
                    prod["precio_unitario"]
                    or 0
                )
                * cantidad
            )

            c1, c2 = st.columns(2)

            c1.metric(
                "Precio unitario",
                f"${float(prod['precio_unitario'] or 0):,.0f}"
            )

            c2.metric(
                "Total",
                f"${total_venta:,.0f}"
            )

            if st.button(
                "💰 Registrar venta",
                type="primary",
                use_container_width=True
            ):

                try:

                    vid = crear_venta(

                        producto_id=prod["id"],

                        cantidad=int(
                            cantidad
                        ),

                        cliente=cliente_v,

                        vendedor=(
                            st.session_state.usuario
                        ),

                        notas=notas_v
                    )

                    st.success(
                        f"Venta #{vid} registrada."
                    )

                    st.balloons()

                    st.rerun()

                except ValueError as e:

                    st.error(
                        str(e)
                    )

                except Exception as e:

                    st.error(
                        f"Error: {e}"
                    )

    with tab_historial:

        ventas = obtener_ventas()

        if not ventas:

            st.info(
                "No hay ventas."
            )

        else:

            data = [

                {
                    "ID":
                        v["id"],

                    "Fecha":
                        v["fecha"],

                    "Producto":
                        v["producto_nombre"],

                    "Cantidad":
                        v["cantidad"],

                    "P. Unitario":
                        v["precio_unitario"],

                    "Total":
                        v["total"],

                    "Cliente":
                        v["cliente"] or "",

                    "Vendedor":
                        v["vendedor"] or ""
                }

                for v in ventas
            ]

            st.dataframe(
                data,
                use_container_width=True,
                hide_index=True
            )

            st.metric(
                "Total vendido",
                f"${sumar_ventas():,.0f}"
            )

            if (
                st.session_state.rol
                == "admin"
            ):

                st.markdown("---")

                st.subheader(
                    "Eliminar venta"
                )

                ids_v = [
                    v["id"]
                    for v in ventas
                ]

                id_del = st.selectbox(
                    "ID de venta",
                    ids_v,
                    key="del_venta"
                )

                confirmar_venta = (
                    st.checkbox(
                        "Confirmo eliminar "
                        "esta venta"
                    )
                )

                if st.button(
                    "🗑️ Eliminar venta",
                    key="btn_del_venta",
                    use_container_width=True
                ):

                    if confirmar_venta:

                        eliminar_venta(
                            id_del
                        )

                        st.success(
                            "Venta eliminada y "
                            "stock devuelto."
                        )

                        st.rerun()

                    else:

                        st.warning(
                            "Debes confirmar primero."
                        )


# ==========================================================
# EXPORTAR
# ==========================================================

elif opcion == "📤 Exportar":

    st.subheader(
        "📤 Exportar información"
    )

    ordenes = obtener_ordenes()

    if ordenes:

        output = StringIO()

        writer = csv.writer(
            output
        )

        writer.writerow([
            "ID",
            "Fecha",
            "Cliente",
            "Teléfono",
            "Equipo",
            "Problema",
            "Precio",
            "Estado",
            "Técnico",
            "Notas",
            "Pagado"
        ])

        for o in ordenes:

            writer.writerow([

                o["id"],
                o["fecha"],
                o["cliente"],
                o["telefono"],
                o["equipo"],
                o["problema"],
                o["precio_estimado"],
                o["estado"],
                o["tecnico"],
                o["notas"],
                o["pagado"]
            ])

        st.download_button(

            "📥 Descargar órdenes",

            output.getvalue().encode(
                "utf-8-sig"
            ),

            "reparaciones.csv",

            "text/csv",

            use_container_width=True
        )

    productos = obtener_inventario()

    if productos:

        output = StringIO()

        writer = csv.writer(
            output
        )

        writer.writerow([
            "ID",
            "Producto",
            "Cantidad",
            "Precio Unitario"
        ])

        for p in productos:

            writer.writerow([
                p["id"],
                p["producto"],
                p["cantidad"],
                p["precio_unitario"]
            ])

        st.download_button(

            "📥 Descargar inventario",

            output.getvalue().encode(
                "utf-8-sig"
            ),

            "inventario.csv",

            "text/csv",

            use_container_width=True
        )

    gastos = obtener_gastos()

    if gastos:

        output = StringIO()

        writer = csv.writer(
            output
        )

        writer.writerow([
            "ID",
            "Fecha",
            "Descripción",
            "Monto",
            "Categoría"
        ])

        for g in gastos:

            writer.writerow([
                g["id"],
                g["fecha"],
                g["descripcion"],
                g["monto"],
                g["categoria"]
            ])

        st.download_button(

            "📥 Descargar gastos",

            output.getvalue().encode(
                "utf-8-sig"
            ),

            "gastos.csv",

            "text/csv",

            use_container_width=True
        )

    ventas = obtener_ventas()

    if ventas:

        output = StringIO()

        writer = csv.writer(
            output
        )

        writer.writerow([
            "ID",
            "Fecha",
            "Producto",
            "Cantidad",
            "Precio Unitario",
            "Total",
            "Cliente",
            "Vendedor",
            "Notas"
        ])

        for v in ventas:

            writer.writerow([
                v["id"],
                v["fecha"],
                v["producto_nombre"],
                v["cantidad"],
                v["precio_unitario"],
                v["total"],
                v["cliente"],
                v["vendedor"],
                v["notas"]
            ])

        st.download_button(

            "📥 Descargar ventas",

            output.getvalue().encode(
                "utf-8-sig"
            ),

            "ventas.csv",

            "text/csv",

            use_container_width=True
        )

    st.markdown("---")

    st.subheader(
        "🛡️ Respaldo general"
    )

    respaldo = {

        "fecha_respaldo":
            datetime.now().isoformat(),

        "ordenes":
            [
                dict(x)
                for x in obtener_ordenes()
            ],

        "inventario":
            [
                dict(x)
                for x in obtener_inventario()
            ],

        "ventas":
            [
                dict(x)
                for x in obtener_ventas()
            ],

        "gastos":
            [
                dict(x)
                for x in obtener_gastos()
            ],

        "cortes":
            [
                dict(x)
                for x in obtener_cortes_mensuales()
            ]
    }

    respaldo_json = json.dumps(
        respaldo,
        ensure_ascii=False,
        indent=2,
        default=str
    )

    st.download_button(

        "💾 Descargar respaldo completo",

        respaldo_json.encode(
            "utf-8"
        ),

        file_name=(
            "electronic_tech_backup_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}"
            ".json"
        ),

        mime="application/json",

        use_container_width=True
    )


# ==========================================================
# SISTEMA
# ==========================================================

elif opcion == "🛡️ Sistema":

    st.subheader(
        "🛡️ Estado del sistema"
    )

    try:

        diagnostico = (
            obtener_diagnostico_db()
        )

        st.success(
            "✅ Base de datos conectada."
        )

        st.caption(
            "Este identificador debe permanecer "
            "igual. Si algún día cambia, la "
            "aplicación está conectada a otra "
            "base de datos."
        )

        st.code(
            diagnostico[
                "instalacion_id"
            ]
        )

        c1, c2 = st.columns(2)

        c1.metric(
            "Órdenes",
            diagnostico["ordenes"]
        )

        c2.metric(
            "Productos",
            diagnostico["productos"]
        )

        c3, c4 = st.columns(2)

        c3.metric(
            "Ventas",
            diagnostico["ventas"]
        )

        c4.metric(
            "Gastos",
            diagnostico["gastos"]
        )

        c5, c6 = st.columns(2)

        c5.metric(
            "Usuarios",
            diagnostico["usuarios"]
        )

        c6.metric(
            "Cortes",
            diagnostico["cortes"]
        )

        st.warning(
            "Guarda una captura del ID de "
            "instalación. Si algún día aparece "
            "la aplicación vacía, compara ese ID."
        )

    except Exception as e:

        st.error(
            f"Error en diagnóstico: {e}"
        )


# ==========================================================
# TALLER
# ==========================================================

elif opcion == "📍 Taller":

    st.subheader(
        "📍 Electronic Tech Service"
    )

    st.write(
        "📍 Barrio El Mundo López"
    )

    st.write(
        "Montería - Córdoba"
    )

    st.write(
        "📞 WhatsApp: 301 487 4740"
    )

    st.link_button(
        "🗺️ Abrir Google Maps",
        "https://maps.google.com",
        use_container_width=True
    )

    st.link_button(
        "📲 Abrir WhatsApp",
        "https://wa.me/573014874740",
        use_container_width=True
    )


# ==========================================================
# WHATSAPP FLOTANTE
# ==========================================================

st.markdown("""
<a
href="https://wa.me/573014874740"
target="_blank"
class="whatsapp-float"
title="WhatsApp"
>
💬
</a>
""", unsafe_allow_html=True)