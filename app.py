import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(
    page_title="Electronic Tech Service", 
    page_icon="logo.png",           # ← Usa tu logo como ícono
    layout="wide",
    initial_sidebar_state="expanded"
)
# ==================== ESTILO ====================
st.markdown("""
<style>
    .stApp { background-color: #0a0a23; color: #ffffff; }
    .stButton>button { background-color: #00f5ff; color: #000000; font-weight: bold; padding: 12px; border-radius: 10px; }
    h1, h2, h3 { color: #00f5ff; }
</style>
""", unsafe_allow_html=True)

# ==================== LOGO ====================
if os.path.exists("logo.png"):
    st.image("logo.png", width=320)
else:
    st.title("🔧 Electronic Tech Service")

st.markdown("**Sistema Profesional de Gestión de Reparaciones**")

# ==================== CARGAR DATOS ====================
DATA_FILE = "reparaciones.xlsx"
INV_FILE = "inventario.xlsx"
GASTOS_FILE = "gastos.xlsx"

if os.path.exists(DATA_FILE):
    df = pd.read_excel(DATA_FILE)
else:
    df = pd.DataFrame(columns=["ID", "Fecha", "Cliente", "Telefono", "Equipo", "Problema", 
                               "Precio_Estimado", "Estado", "Tecnico", "Notas", "Pagado"])

if "Pagado" not in df.columns:
    df["Pagado"] = "Pendiente"

if os.path.exists(INV_FILE):
    inv = pd.read_excel(INV_FILE)
else:
    inv = pd.DataFrame(columns=["Producto", "Cantidad", "Precio_Unitario", "Fecha_Actualizacion"])

if os.path.exists(GASTOS_FILE):
    gastos = pd.read_excel(GASTOS_FILE)
else:
    gastos = pd.DataFrame(columns=["Fecha", "Descripcion", "Monto", "Categoria"])

# ==================== MENÚ ====================
menu = st.sidebar.selectbox("Menú", 
    ["🏠 Inicio", "📋 Nueva Reparación", "📋 Ver Órdenes", "🔍 Buscar", 
     "📄 Cotizaciones", "🖨️ Imprimir Recibo", "📦 Inventario", "📊 Contabilidad", "💸 Gastos"])

# ==================== INICIO ====================
if menu == "🏠 Inicio":
    st.subheader("Resumen del Día")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Órdenes", len(df))
    col2.metric("Pendientes", len(df[df["Estado"] != "Entregado"]) if not df.empty else 0)
    col3.metric("Hoy", len(df[df["Fecha"].astype(str).str.contains(datetime.now().strftime("%Y-%m-%d"))]) if not df.empty else 0)

# ==================== NUEVA REPARACIÓN ====================
elif menu == "📋 Nueva Reparación":
    st.subheader("📋 Nueva Orden de Reparación")
    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input("Nombre del Cliente *")
        telefono = st.text_input("Teléfono / WhatsApp *")
        equipo = st.text_input("Equipo *")
    with col2:
        problema = st.text_area("Descripción del problema *")
        precio = st.number_input("Precio estimado ($)", min_value=0, step=1000)
        estado = st.selectbox("Estado", ["Recibido", "En reparación", "Listo", "Entregado"])
    
    if st.button("💾 Guardar Orden", type="primary", use_container_width=True):
        if cliente and telefono and equipo and problema:
            nuevo_id = len(df) + 1
            nueva = {
                "ID": nuevo_id,
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Cliente": cliente,
                "Telefono": telefono,
                "Equipo": equipo,
                "Problema": problema,
                "Precio_Estimado": int(precio),
                "Estado": estado,
                "Tecnico": "Tú",
                "Notas": "",
                "Pagado": "Pendiente"
            }
            df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            df.to_excel(DATA_FILE, index=False)
            st.success(f"✅ Orden #{nuevo_id} guardada!")
            st.balloons()
        else:
            st.error("❌ Completa los campos obligatorios (*)")

# ==================== VER ÓRDENES ====================
elif menu == "📋 Ver Órdenes":
    st.subheader("📋 Todas las Reparaciones")
    if not df.empty:
        df_display = df.copy()
        df_display["Precio_Estimado"] = df_display["Precio_Estimado"].apply(lambda x: f"${int(x):,}" if pd.notna(x) else "$0")
        estados = st.multiselect("Filtrar por estado", df["Estado"].unique().tolist(), default=df["Estado"].unique().tolist())
        df_mostrar = df_display[df_display["Estado"].isin(estados)]
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay órdenes registradas")

# ==================== BUSCAR ====================
elif menu == "🔍 Buscar":
    st.subheader("🔍 Buscar Orden")
    busqueda = st.text_input("Cliente, teléfono o ID")
    if busqueda and not df.empty:
        resultados = df[df.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)]
        st.dataframe(resultados, use_container_width=True, hide_index=True)
    else:
        st.info("Escribe algo para buscar")

# ==================== COTIZACIONES ====================
elif menu == "📄 Cotizaciones":
    st.subheader("📄 Nueva Cotización")
    col1, col2 = st.columns(2)
    with col1:
        cliente_cot = st.text_input("Nombre del Cliente")
        telefono_cot = st.text_input("Teléfono")
        equipo_cot = st.text_input("Equipo")
    with col2:
        descripcion_cot = st.text_area("Descripción del servicio / falla")
        precio_cot = st.number_input("Precio cotizado ($)", min_value=0, step=1000)
    
    if st.button("💾 Generar Cotización", type="primary"):
        if cliente_cot and precio_cot > 0:
            st.markdown(f"""
            <div style="background-color: white; color: black; padding: 25px; border-radius: 10px; max-width: 600px; margin: auto;">
                <h2 style="text-align: center;">Electronic Tech Service</h2>
                <p style="text-align: center;">Cotización #{len(df)+1} — {datetime.now().strftime("%d/%m/%Y")}</p>
                <hr>
                <p><strong>Cliente:</strong> {cliente_cot}</p>
                <p><strong>Teléfono:</strong> {telefono_cot}</p>
                <p><strong>Equipo:</strong> {equipo_cot}</p>
                <p><strong>Descripción:</strong> {descripcion_cot}</p>
                <h3 style="text-align: right;">Total: ${int(precio_cot):,}</h3>
                <hr>
                <p style="text-align: center;">Montería - Córdoba • Barrio El Mundo López</p>
                <p style="text-align: center;">WhatsApp: <strong>301 487 4740</strong></p>
                <p style="text-align: center; margin-top: 30px;">¡Gracias por elegirnos!</p>
            </div>
            """, unsafe_allow_html=True)
            st.info("👆 Usa ⋯ → Imprimir")
        else:
            st.error("Completa los campos")

# ==================== IMPRIMIR RECIBO ====================
elif menu == "🖨️ Imprimir Recibo":
    st.subheader("🖨️ Imprimir Recibo")
    id_recibo = st.number_input("ID de la Orden", min_value=1, step=1)
    if st.button("Generar Recibo"):
        if id_recibo in df["ID"].values:
            orden = df[df["ID"] == id_recibo].iloc[0]
            st.markdown(f"""
            <div style="background-color: white; color: black; padding: 25px; border-radius: 10px; max-width: 600px; margin: auto;">
                <h2 style="text-align: center;">Electronic Tech Service</h2>
                <p style="text-align: center;">Recibo Oficial • Orden #{orden['ID']}</p>
                <hr>
                <p><strong>Fecha:</strong> {orden['Fecha']}</p>
                <p><strong>Cliente:</strong> {orden['Cliente']}</p>
                <p><strong>Teléfono:</strong> {orden['Telefono']}</p>
                <p><strong>Equipo:</strong> {orden['Equipo']}</p>
                <p><strong>Problema:</strong> {orden['Problema']}</p>
                <p><strong>Estado:</strong> {orden['Estado']}</p>
                <h3 style="text-align: right;">Total: ${int(orden['Precio_Estimado']):,}</h3>
                <hr>
                <p style="text-align: center;">Montería - Córdoba • Barrio El Mundo López</p>
                <p style="text-align: center;">WhatsApp: <strong>301 487 4740</strong></p>
                <p style="text-align: center;">¡Gracias por su preferencia!</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("Orden no encontrada")

# ==================== INVENTARIO ====================
elif menu == "📦 Inventario":
    st.subheader("📦 Gestión de Inventario")
    tab1, tab2, tab3 = st.tabs(["Ver Inventario", "Agregar Repuesto", "Restar Stock"])

    with tab1:
        if not inv.empty:
            inv_display = inv.copy()
            inv_display["Estado"] = inv_display["Cantidad"].apply(lambda x: "🟢 Normal" if x > 5 else "🔴 Bajo Stock")
            st.dataframe(inv_display, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay repuestos en inventario.")

    with tab2:
        st.write("**Agregar nuevo repuesto**")
        col1, col2 = st.columns(2)
        with col1:
            producto = st.text_input("Nombre del Repuesto *")
            cantidad = st.number_input("Cantidad inicial", min_value=1, value=1)
        with col2:
            precio_unit = st.number_input("Precio Unitario ($)", min_value=0)
        if st.button("➕ Agregar", type="primary"):
            if producto:
                nuevo = {"Producto": producto, "Cantidad": cantidad, "Precio_Unitario": precio_unit,
                         "Fecha_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")}
                inv = pd.concat([inv, pd.DataFrame([nuevo])], ignore_index=True)
                inv.to_excel(INV_FILE, index=False)
                st.success(f"{producto} agregado")
                st.rerun()

    with tab3:
        st.write("**Restar stock**")
        if not inv.empty:
            producto_restar = st.selectbox("Repuesto", inv["Producto"])
            cantidad_restar = st.number_input("Cantidad a restar", min_value=1, value=1)
            if st.button("➖ Restar"):
                idx = inv[inv["Producto"] == producto_restar].index[0]
                if inv.loc[idx, "Cantidad"] >= cantidad_restar:
                    inv.loc[idx, "Cantidad"] -= cantidad_restar
                    inv.loc[idx, "Fecha_Actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    inv.to_excel(INV_FILE, index=False)
                    st.success(f"Restadas {cantidad_restar} de {producto_restar}")
                    st.rerun()
                else:
                    st.error("Stock insuficiente")

# ==================== CONTABILIDAD ====================
elif menu == "📊 Contabilidad":
    st.subheader("📊 Contabilidad")
    total = df["Precio_Estimado"].sum()
    cobrado = df[df["Pagado"] == "Pagado"]["Precio_Estimado"].sum() if not df.empty else 0
    por_cobrar = total - cobrado

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Ganado", f"${total:,.0f}")
    col2.metric("Cobrado", f"${cobrado:,.0f}")
    col3.metric("Por Cobrar", f"${por_cobrar:,.0f}")

# ==================== GASTOS ====================
elif menu == "💸 Gastos":
    st.subheader("💸 Gastos")
    tab1, tab2 = st.tabs(["Registrar", "Resumen"])
    with tab1:
        desc = st.text_input("Descripción")
        monto = st.number_input("Monto", min_value=0, step=1000)
        cat = st.selectbox("Categoría", ["Repuestos", "Herramientas", "Alquiler", "Servicios", "Otros"])
        if st.button("Registrar Gasto"):
            if desc and monto > 0:
                nuevo = {"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Descripcion": desc, "Monto": monto, "Categoria": cat}
                gastos = pd.concat([gastos, pd.DataFrame([nuevo])], ignore_index=True)
                gastos.to_excel(GASTOS_FILE, index=False)
                st.success("Gasto registrado")
                st.rerun()
    with tab2:
        if not gastos.empty:
            st.dataframe(gastos, use_container_width=True, hide_index=True)
            st.metric("Total Gastos", f"${gastos['Monto'].sum():,.0f}")

st.sidebar.metric("Total Órdenes", len(df))
