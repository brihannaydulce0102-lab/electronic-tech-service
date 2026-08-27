import streamlit as st
import os
import base64
import urllib.parse
import qrcode
import ast
from io import BytesIO
from datetime import datetime
from PIL import Image
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet
from streamlit_drawable_canvas import st_canvas

from database import (
    hash_password,
    obtener_ordenes, obtener_orden, crear_orden, actualizar_orden,
    actualizar_estado, eliminar_orden, contar_ordenes, sumar_ingresos,
    contar_por_estado, contar_pendientes,
    obtener_usuarios, obtener_usuario_por_nombre, crear_usuario,
    actualizar_usuario, eliminar_usuario,
    obtener_inventario, crear_producto, actualizar_producto, eliminar_producto,
    obtener_gastos, crear_gasto, sumar_gastos, eliminar_gasto
)

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
.stApp {
    background: #05051b;
    color: white;
}
.stButton>button {
    background: #00E5FF;
    color: black;
    font-weight: bold;
    border-radius: 12px;
    padding: 12px;
    width: 100%;
}
.card {
    background: #111133;
    padding: 16px;
    border-radius: 15px;
    margin-bottom: 15px;
}
@media (max-width: 768px) {
    h1 { font-size: 28px; }
}
</style>
""", unsafe_allow_html=True)

# ===========================
# RUTAS Y CARPETAS
# ===========================
ASSETS = "assets"
BACKUP = "backup"
ARCHIVE = "cortes_mensuales"

for carpeta in [ASSETS, BACKUP, ARCHIVE]:
    os.makedirs(carpeta, exist_ok=True)

# ===========================
# FUNCIONES AUXILIARES
# ===========================
def imagen_base64(upload):
    return base64.b64encode(upload.read()).decode()

def mostrar_base64(texto):
    return base64.b64decode(texto)

def crear_qr(texto):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    ruta = os.path.join(ASSETS, f"{texto}.png")
    img.save(ruta)
    return ruta

def crear_pdf(orden):
    ruta = os.path.join(ASSETS, f"Recibo_{orden['id']}.pdf")
    doc = SimpleDocTemplate(ruta)
    estilos = getSampleStyleSheet()
    e = []

    if os.path.exists("logo.png"):
        e.append(RLImage("logo.png", 120, 120))

    e.append(Paragraph("<b>Electronic Tech Service</b>", estilos["Title"]))
    e.append(Paragraph("Montería - Córdoba", estilos["Normal"]))
    e.append(Spacer(1, 12))

    campos = [
        ("Orden", orden["id"]),
        ("Fecha", orden["fecha"]),
        ("Cliente", orden["cliente"]),
        ("Teléfono", orden["telefono"] or ""),
        ("Equipo", orden["equipo"]),
        ("Problema", orden["problema"] or ""),
        ("Estado", orden["estado"]),
    ]

    for k, v in campos:
        e.append(Paragraph(f"<b>{k}:</b> {v}", estilos["Normal"]))

    e.append(Paragraph(
        f"<b>Total:</b> ${orden['precio_estimado']:,.0f}",
        estilos["Normal"]
    ))

    qr = crear_qr(f"ETS_{orden['id']}")
    e.append(Spacer(1, 10))
    e.append(RLImage(qr, 120, 120))
    e.append(Spacer(1, 10))
    e.append(Paragraph(
        "Gracias por confiar en Electronic Tech Service.",
        estilos["Italic"]
    ))

    doc.build(e)
    return ruta

# ===========================
# LOGIN
# ===========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario = ""
    st.session_state.rol = ""

if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=260)
        st.title("Electronic Tech Service")
        st.caption("Sistema Profesional")

        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")

        if st.button("Entrar"):
            user = obtener_usuario_por_nombre(usuario)
            if user and user["password"] == hash_password(clave):
                st.session_state.logged_in = True
                st.session_state.usuario = user["usuario"]
                st.session_state.rol = user["rol"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# ===========================
# CABECERA
# ===========================
a, b = st.columns([1, 5])
with a:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=110)
with b:
    st.title("Electronic Tech Service")
    st.caption(f"{st.session_state.usuario} | {st.session_state.rol}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logged_in = False
    st.rerun()

# ===========================
# MENÚ (se mantiene aunque des F5)
# ===========================
menu = [
    "🏠 Inicio",
    "📋 Nueva Reparación",
    "📋 Ver Órdenes",
    "🔍 Buscar",
    "📄 Cotizaciones",
    "🖨️ Recibos",
    "📍 Taller",
    "📤 Exportar"
]

if st.session_state.rol == "admin":
    menu.extend([
        "📦 Inventario",
        "📊 Contabilidad",
        "💸 Gastos",
        "📅 Corte Mensual",
        "👥 Usuarios"
    ])

# Claves limpias para la URL
menu_keys = {
    "🏠 Inicio": "inicio",
    "📋 Nueva Reparación": "nueva",
    "📋 Ver Órdenes": "ordenes",
    "🔍 Buscar": "buscar",
    "📄 Cotizaciones": "cotizaciones",
    "🖨️ Recibos": "recibos",
    "📍 Taller": "taller",
    "📤 Exportar": "exportar",
    "📦 Inventario": "inventario",
    "📊 Contabilidad": "contabilidad",
    "💸 Gastos": "gastos",
    "📅 Corte Mensual": "corte",
    "👥 Usuarios": "usuarios"
}

keys_to_menu = {v: k for k, v in menu_keys.items()}

# Leer la sección desde la URL
try:
    params = st.query_params
    seccion_url = params.get("page", "inicio")
except Exception:
    params = st.experimental_get_query_params()
    seccion_url = params.get("page", ["inicio"])[0]

# Validar la sección
if seccion_url in keys_to_menu and keys_to_menu[seccion_url] in menu:
    seccion_actual = keys_to_menu[seccion_url]
else:
    seccion_actual = "🏠 Inicio"

# Selectbox del menú
opcion = st.sidebar.selectbox(
    "Menú",
    menu,
    index=menu.index(seccion_actual) if seccion_actual in menu else 0,
    key="menu_sidebar"
)

# Guardar la sección en la URL
clave = menu_keys.get(opcion, "inicio")

try:
    st.query_params["page"] = clave
except Exception:
    st.experimental_set_query_params(page=clave)

# ==========================================================
# INICIO
# ==========================================================
if opcion == "🏠 Inicio":
    ingresos = sumar_ingresos()
    pendientes = contar_pendientes()
    listos = contar_por_estado("Listo")
    total = contar_ordenes()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Órdenes", total)
    c2.metric("Ingresos", f"${ingresos:,.0f}")
    c3.metric("Pendientes", pendientes)
    c4.metric("Listos", listos)

    st.markdown("---")
    ordenes = obtener_ordenes()
    if ordenes:
        st.subheader("Últimas órdenes")
        # Mostrar solo las 5 más recientes
        data = []
        for o in ordenes[:5]:
            data.append({
                "ID": o["id"],
                "Fecha": o["fecha"],
                "Cliente": o["cliente"],
                "Equipo": o["equipo"],
                "Estado": o["estado"],
                "Precio": o["precio_estimado"]
            })
        st.dataframe(data, use_container_width=True, hide_index=True)

# ==========================================================
# NUEVA REPARACIÓN
# ==========================================================
elif opcion == "📋 Nueva Reparación":
    st.subheader("Nueva Orden de Reparación")

    c1, c2 = st.columns(2)
    with c1:
        cliente = st.text_input("Cliente")
        telefono = st.text_input("Teléfono / WhatsApp")
        equipo = st.text_input("Equipo")
    with c2:
        problema = st.text_area("Problema")
        precio = st.number_input("Precio estimado", min_value=0, step=1000)
        estado = st.selectbox("Estado", ["Recibido", "En reparación", "Listo", "Entregado"])

    st.markdown("### 📷 Fotos")
    antes = st.file_uploader("Antes", type=["jpg", "jpeg", "png"], key="antes")
    durante = st.file_uploader("Durante", type=["jpg", "jpeg", "png"], key="durante")
    despues = st.file_uploader("Después", type=["jpg", "jpeg", "png"], key="despues")

    st.markdown("### ✍️ Firma del cliente")
    canvas = st_canvas(
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
            fotos = {}
            if antes:
                fotos["antes"] = imagen_base64(antes)
            if durante:
                fotos["durante"] = imagen_base64(durante)
            if despues:
                fotos["despues"] = imagen_base64(despues)

            firma = ""
            if canvas.image_data is not None:
                img = Image.fromarray(canvas.image_data.astype("uint8"))
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                firma = base64.b64encode(buffer.getvalue()).decode()

            nuevo_id = crear_orden(
                cliente=cliente,
                telefono=telefono,
                equipo=equipo,
                problema=problema,
                precio=precio,
                estado=estado,
                tecnico=st.session_state.usuario,
                fotos=str(fotos),
                firma=firma
            )
            st.success(f"Orden #{nuevo_id} creada correctamente")
            st.balloons()
        else:
            st.error("Cliente y equipo son obligatorios.")

# ==========================================================
# VER ÓRDENES
# ==========================================================
elif opcion == "📋 Ver Órdenes":
    st.subheader("Órdenes")

    ordenes = obtener_ordenes()

    if not ordenes:
        st.info("No hay órdenes registradas.")
    else:
        ids = [o["id"] for o in ordenes]

        # Guardar la orden seleccionada en session_state para que no se pierda
        if "orden_seleccionada" not in st.session_state:
            st.session_state.orden_seleccionada = ids[0]

        # Si la orden guardada ya no existe, elegir la primera
        if st.session_state.orden_seleccionada not in ids:
            st.session_state.orden_seleccionada = ids[0]

        id_seleccionado = st.selectbox(
            "Selecciona una orden para ver / editar",
            options=ids,
            index=ids.index(st.session_state.orden_seleccionada),
            format_func=lambda x: f"#{x} - {next((o['cliente'] for o in ordenes if o['id'] == x), '')}",
            key="select_orden"
        )

        # Actualizar la orden guardada
        st.session_state.orden_seleccionada = id_seleccionado

        orden = obtener_orden(id_seleccionado)

        if orden:
            col1, col2 = st.columns([1, 2])

            with col1:
                try:
                    fotos = ast.literal_eval(orden["fotos"] or "{}")
                except Exception:
                    fotos = {}
                for nombre in ["antes", "durante", "despues"]:
                    if nombre in fotos and fotos[nombre]:
                        st.image(mostrar_base64(fotos[nombre]), caption=nombre.capitalize(), width=170)

            with col2:
                st.markdown(f"### Orden #{orden['id']}")
                st.write("**Cliente:**", orden["cliente"])
                st.write("**Equipo:**", orden["equipo"])
                st.write("**Problema:**", orden["problema"] or "")
                st.write("**Estado:**", orden["estado"])
                st.write("**Precio:**", f"${orden['precio_estimado']:,.0f}")

                if orden["firma"]:
                    st.image(mostrar_base64(orden["firma"]), caption="Firma del cliente", width=200)

                estados = ["Recibido", "En reparación", "Listo", "Entregado"]
                idx = estados.index(orden["estado"]) if orden["estado"] in estados else 0
                nuevo_estado = st.selectbox("Cambiar estado", estados, index=idx, key=f"est_{orden['id']}")

                if st.button("Actualizar Estado", key=f"btn_est_{orden['id']}"):
                    actualizar_estado(orden["id"], nuevo_estado)
                    st.success("Estado actualizado")
                    st.rerun()

                telefono = str(orden["telefono"] or "").replace(" ", "")
                mensaje = urllib.parse.quote(
                    f"Hola {orden['cliente']}, tu equipo ({orden['equipo']}) está en estado: {nuevo_estado}."
                )
                st.link_button("📲 WhatsApp", f"https://wa.me/57{telefono}?text={mensaje}")

            # Expander de edición (solo admin)
            if st.session_state.rol == "admin":
                # Controlamos si el expander debe estar abierto
                if "expander_abierto" not in st.session_state:
                    st.session_state.expander_abierto = False

                with st.expander("✏️ Editar Orden completa", expanded=st.session_state.expander_abierto):
                    with st.form(key=f"form_edit_{orden['id']}"):
                        cliente2 = st.text_input("Cliente", value=orden["cliente"])
                        telefono2 = st.text_input("Teléfono", value=orden["telefono"] or "")
                        equipo2 = st.text_input("Equipo", value=orden["equipo"])
                        problema2 = st.text_area("Problema", value=orden["problema"] or "")
                        precio2 = st.number_input("Precio estimado", value=float(orden["precio_estimado"] or 0), step=1000.0)
                        estado2 = st.selectbox("Estado", estados, index=idx)
                        notas2 = st.text_area("Notas", value=orden["notas"] or "")
                        opciones_pagado = ["Pendiente", "Parcial", "Pagado"]
                        idx_pag = opciones_pagado.index(orden["pagado"]) if orden["pagado"] in opciones_pagado else 0
                        pagado2 = st.selectbox("Pagado", opciones_pagado, index=idx_pag)

                        col_g, col_e = st.columns(2)
                        guardar = col_g.form_submit_button("💾 Guardar cambios")
                        eliminar = col_e.form_submit_button("🗑️ Eliminar orden")

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
                            st.session_state.expander_abierto = True  # Mantener abierto después de guardar
                            st.success("Orden actualizada correctamente")
                            st.rerun()

                        if eliminar:
                            eliminar_orden(orden["id"])
                            st.session_state.expander_abierto = False
                            st.success("Orden eliminada")
                            st.rerun()

# ==========================================================
# BUSCAR
# ==========================================================
elif opcion == "🔍 Buscar":
    st.subheader("Buscar")

    texto = st.text_input("Buscar por cliente, teléfono, equipo o ID")

    if texto:
        ordenes = obtener_ordenes()
        resultados = []
        texto_lower = texto.lower()
        for o in ordenes:
            if (texto_lower in str(o["cliente"]).lower() or
                texto_lower in str(o["telefono"] or "") or
                texto_lower in str(o["equipo"]).lower() or
                texto_lower in str(o["id"])):
                resultados.append(o)

        st.write(f"{len(resultados)} resultado(s)")

        if resultados:
            data = [{
                "ID": o["id"],
                "Fecha": o["fecha"],
                "Cliente": o["cliente"],
                "Teléfono": o["telefono"],
                "Equipo": o["equipo"],
                "Estado": o["estado"],
                "Precio": o["precio_estimado"]
            } for o in resultados]
            st.dataframe(data, use_container_width=True, hide_index=True)

            # Historial del primer cliente encontrado
            cliente = resultados[0]["cliente"]
            st.markdown("---")
            st.subheader(f"Historial de {cliente}")
            historial = [o for o in ordenes if o["cliente"] == cliente]
            data_h = [{
                "ID": o["id"],
                "Fecha": o["fecha"],
                "Equipo": o["equipo"],
                "Estado": o["estado"],
                "Precio": o["precio_estimado"]
            } for o in historial]
            st.dataframe(data_h, use_container_width=True, hide_index=True)

# ==========================================================
# RECIBOS
# ==========================================================
elif opcion == "🖨️ Recibos":
    st.subheader("Recibos")

    ordenes = obtener_ordenes()
    if not ordenes:
        st.info("No hay órdenes.")
    else:
        ids = [o["id"] for o in ordenes]
        id_recibo = st.selectbox("Selecciona la orden", ids)
        orden = obtener_orden(id_recibo)

        st.write("**Cliente:**", orden["cliente"])
        st.write("**Equipo:**", orden["equipo"])
        st.write("**Estado:**", orden["estado"])

        qr = crear_qr(f"ETS_{orden['id']}")
        st.image(qr, width=140)

        if st.button("Generar PDF"):
            pdf = crear_pdf(orden)
            with open(pdf, "rb") as f:
                st.download_button(
                    "📄 Descargar Recibo",
                    f,
                    file_name=f"Recibo_{orden['id']}.pdf",
                    mime="application/pdf"
                )

        if st.button("Generar Ticket"):
            ticket = f"""
Electronic Tech Service

Orden #{orden['id']}

Cliente:
{orden['cliente']}

Equipo:
{orden['equipo']}

Estado:
{orden['estado']}

Total:
${orden['precio_estimado']:,.0f}

WhatsApp:
3014874740

Gracias por preferirnos.
"""
            st.download_button(
                "🧾 Descargar Ticket",
                ticket,
                file_name=f"Ticket_{orden['id']}.txt"
            )

# ==========================================================
# COTIZACIONES
# ==========================================================
elif opcion == "📄 Cotizaciones":
    st.subheader("Nueva Cotización")

    c1, c2 = st.columns(2)
    with c1:
        cliente = st.text_input("Cliente", key="cot_cliente")
        telefono = st.text_input("Teléfono", key="cot_tel")
        equipo = st.text_input("Equipo", key="cot_equipo")
    with c2:
        descripcion = st.text_area("Descripción", key="cot_desc")
        precio = st.number_input("Precio", min_value=0, step=1000, key="cot_precio")

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
        """, unsafe_allow_html=True)

# ==========================================================
# INVENTARIO
# ==========================================================
elif opcion == "📦 Inventario":
    st.subheader("Inventario")

    tab1, tab2 = st.tabs(["Inventario", "Agregar"])

    with tab1:
        productos = obtener_inventario()
        if not productos:
            st.info("No hay productos.")
        else:
            for p in productos:
                color = "🟢"
                if p["cantidad"] <= 5:
                    color = "🔴"
                elif p["cantidad"] <= 10:
                    color = "🟡"

                with st.container(border=True):
                    st.write(f"{color} **{p['producto']}**")
                    c1, c2 = st.columns(2)
                    c1.write(f"Cantidad: {p['cantidad']}")
                    c2.write(f"${p['precio_unitario']:,.0f}")

                    nueva = st.number_input(
                        "Nueva cantidad",
                        value=int(p["cantidad"]),
                        key=f"cant{p['id']}"
                    )

                    c3, c4 = st.columns(2)
                    if c3.button("Actualizar", key=f"up{p['id']}"):
                        actualizar_producto(p["id"], cantidad=nueva)
                        st.rerun()
                    if c4.button("Eliminar", key=f"del{p['id']}"):
                        eliminar_producto(p["id"])
                        st.rerun()

    with tab2:
        prod = st.text_input("Producto")
        cant = st.number_input("Cantidad", min_value=1, value=1)
        precio = st.number_input("Precio Unitario", min_value=0, step=1000, key="inv_precio")

        if st.button("Guardar Producto"):
            if prod:
                crear_producto(prod, cant, precio)
                st.success("Producto agregado.")
                st.rerun()
            else:
                st.error("El nombre del producto es obligatorio.")

# ==========================================================
# CONTABILIDAD
# ==========================================================
elif opcion == "📊 Contabilidad":
    st.subheader("Contabilidad")

    ingresos = sumar_ingresos()
    egresos = sumar_gastos()
    utilidad = ingresos - egresos

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"${ingresos:,.0f}")
    c2.metric("Gastos", f"${egresos:,.0f}")
    c3.metric("Utilidad", f"${utilidad:,.0f}")

    st.markdown("---")

    ordenes = obtener_ordenes()
    if ordenes:
        # Gráfico por estado
        from collections import defaultdict
        por_estado = defaultdict(float)
        for o in ordenes:
            por_estado[o["estado"]] += o["precio_estimado"] or 0

        if por_estado:
            fig, ax = plt.subplots()
            ax.bar(list(por_estado.keys()), list(por_estado.values()))
            st.pyplot(fig)

        st.subheader("Equipos más reparados")
        contador = defaultdict(int)
        for o in ordenes:
            contador[o["equipo"]] += 1
        top = sorted(contador.items(), key=lambda x: x[1], reverse=True)[:5]
        if top:
            fig2, ax2 = plt.subplots()
            ax2.bar([t[0] for t in top], [t[1] for t in top])
            plt.xticks(rotation=25)
            st.pyplot(fig2)

# ==========================================================
# GASTOS
# ==========================================================
elif opcion == "💸 Gastos":
    st.subheader("Registrar Gasto")

    desc = st.text_input("Descripción")
    categoria = st.selectbox(
        "Categoría",
        ["Repuestos", "Herramientas", "Servicios", "Transporte", "Otros"]
    )
    monto = st.number_input("Monto", min_value=0, step=1000, key="gasto_monto")

    if st.button("Guardar Gasto"):
        if desc:
            crear_gasto(desc, monto, categoria)
            st.success("Gasto registrado.")
            st.rerun()
        else:
            st.error("La descripción es obligatoria.")

    gastos = obtener_gastos()
    if gastos:
        data = [{
            "ID": g["id"],
            "Fecha": g["fecha"],
            "Descripción": g["descripcion"],
            "Monto": g["monto"],
            "Categoría": g["categoria"]
        } for g in gastos]
        st.dataframe(data, use_container_width=True, hide_index=True)

# ==========================================================
# CORTE MENSUAL
# ==========================================================
elif opcion == "📅 Corte Mensual":
    st.subheader("Corte del Mes")

    st.warning("Esta acción archiva las órdenes actuales y deja la tabla vacía. Úsala solo al cerrar el mes.")

    if st.button("Cerrar Mes"):
        ordenes = obtener_ordenes()
        if not ordenes:
            st.info("No hay órdenes para archivar.")
        else:
            mes = datetime.now().strftime("%Y-%m")
            # Guardamos un CSV de respaldo
            import csv
            ruta = os.path.join(ARCHIVE, f"corte_{mes}.csv")
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "id", "fecha", "cliente", "telefono", "equipo", "problema",
                    "precio_estimado", "estado", "tecnico", "notas", "pagado"
                ])
                for o in ordenes:
                    writer.writerow([
                        o["id"], o["fecha"], o["cliente"], o["telefono"], o["equipo"],
                        o["problema"], o["precio_estimado"], o["estado"], o["tecnico"],
                        o["notas"], o["pagado"]
                    ])

            # Vaciar tabla de órdenes
            from database import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM ordenes")

            st.success(f"Corte realizado. Archivo guardado en: {ruta}")
            st.rerun()

# ==========================================================
# USUARIOS
# ==========================================================
elif opcion == "👥 Usuarios":
    st.subheader("Administrar Usuarios")

    tab1, tab2 = st.tabs(["Editar", "Nuevo"])

    with tab1:
        usuarios = obtener_usuarios()
        for u in usuarios:
            with st.container(border=True):
                nombre = st.text_input("Usuario", value=u["usuario"], key=f"user{u['id']}")
                clave = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password", key=f"pass{u['id']}")
                rol = st.selectbox(
                    "Rol",
                    ["trabajador", "admin"],
                    index=1 if u["rol"] == "admin" else 0,
                    key=f"rol{u['id']}"
                )

                c1, c2 = st.columns(2)
                if c1.button("Guardar", key=f"save{u['id']}"):
                    datos = {"usuario": nombre, "rol": rol}
                    if clave:
                        datos["password"] = clave
                    actualizar_usuario(u["id"], **datos)

                    if st.session_state.usuario == u["usuario"]:
                        st.session_state.usuario = nombre
                        st.session_state.rol = rol

                    st.success("Usuario actualizado.")
                    st.rerun()

                if u["usuario"].lower() != "admin":
                    if c2.button("Eliminar", key=f"deluser{u['id']}"):
                        eliminar_usuario(u["id"])
                        st.success("Usuario eliminado.")
                        st.rerun()

    with tab2:
        usuario = st.text_input("Nuevo Usuario")
        password = st.text_input("Contraseña", type="password", key="new_pass")
        rol = st.selectbox("Rol", ["trabajador", "admin"], key="new_role")

        if st.button("Crear Usuario"):
            if usuario and password:
                try:
                    crear_usuario(usuario, password, rol)
                    st.success("Usuario creado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Usuario y contraseña son obligatorios.")

# ==========================================================
# EXPORTAR
# ==========================================================
elif opcion == "📤 Exportar":
    st.subheader("Exportar Datos")

    ordenes = obtener_ordenes()
    if ordenes:
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Fecha", "Cliente", "Teléfono", "Equipo", "Problema",
                         "Precio", "Estado", "Técnico", "Notas", "Pagado"])
        for o in ordenes:
            writer.writerow([
                o["id"], o["fecha"], o["cliente"], o["telefono"], o["equipo"],
                o["problema"], o["precio_estimado"], o["estado"], o["tecnico"],
                o["notas"], o["pagado"]
            ])
        st.download_button(
            "Descargar Órdenes (CSV)",
            output.getvalue().encode("utf-8"),
            "reparaciones.csv",
            "text/csv"
        )

    productos = obtener_inventario()
    if productos:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Producto", "Cantidad", "Precio Unitario"])
        for p in productos:
            writer.writerow([p["id"], p["producto"], p["cantidad"], p["precio_unitario"]])
        st.download_button(
            "Descargar Inventario (CSV)",
            output.getvalue().encode("utf-8"),
            "inventario.csv",
            "text/csv"
        )

    gastos = obtener_gastos()
    if gastos:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Fecha", "Descripción", "Monto", "Categoría"])
        for g in gastos:
            writer.writerow([g["id"], g["fecha"], g["descripcion"], g["monto"], g["categoria"]])
        st.download_button(
            "Descargar Gastos (CSV)",
            output.getvalue().encode("utf-8"),
            "gastos.csv",
            "text/csv"
        )

# ==========================================================
# TALLER
# ==========================================================
elif opcion == "📍 Taller":
    st.subheader("Electronic Tech Service")
    st.write("📍 Barrio El Mundo López")
    st.write("Montería - Córdoba")
    st.write("📞 WhatsApp: 301 487 4740")
    st.link_button("Abrir Google Maps", "https://maps.google.com")

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
""", unsafe_allow_html=True)