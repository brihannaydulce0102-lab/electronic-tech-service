import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Electronic Tech Service", layout="wide", page_icon="🔧")

# Estilo
st.markdown("""
<style>
    .stApp { background-color: #0a0a23; color: #ffffff; }
    .stButton>button { background-color: #00f5ff; color: #000000; font-weight: bold; padding: 12px; border-radius: 10px; }
    h1, h2, h3 { color: #00f5ff; }
</style>
""", unsafe_allow_html=True)

# Logo
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
        
        if st.button("➕ Agregar al Inventario", type="primary"):
            if producto:
                nuevo = {"Producto": producto, "Cantidad": cantidad, "Precio_Unitario": precio_unit,
                         "Fecha_Actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M")}
                inv = pd.concat([inv, pd.DataFrame([nuevo])], ignore_index=True)
                inv.to_excel(INV_FILE, index=False)
                st.success(f"✅ {producto} agregado")
                st.rerun()

    with tab3:
        st.write("**Restar stock**")
        if not inv.empty:
            producto_restar = st.selectbox("Seleccionar Repuesto", inv["Producto"])
            cantidad_restar = st.number_input("Cantidad a restar", min_value=1, value=1)
            if st.button("➖ Restar Stock"):
                idx = inv[inv["Producto"] == producto_restar].index[0]
                if inv.loc[idx, "Cantidad"] >= cantidad_restar:
                    inv.loc[idx, "Cantidad"] -= cantidad_restar
                    inv.loc[idx, "Fecha_Actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    inv.to_excel(INV_FILE, index=False)
                    st.success(f"✅ Restadas {cantidad_restar} de {producto_restar}")
                    st.rerun()
                else:
                    st.error("No hay suficiente stock")
        else:
            st.info("Agrega repuestos primero")

# ==================== CONTABILIDAD ====================
elif menu == "📊 Contabilidad":
    st.subheader("📊 Contabilidad")
    total = df["Precio_Estimado"].sum()
    cobrado = df[df["Pagado"] == "Pagado"]["Precio_Estimado"].sum() if not df.empty else 0
    por_cobrar = total - cobrado

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Ganado", f"${total:,.0f}")
    col2.metric("✅ Cobrado", f"${cobrado:,.0f}")
    col3.metric("⏳ Por Cobrar", f"${por_cobrar:,.0f}")

    st.subheader("Marcar Pago")
    id_pago = st.number_input("ID de la Orden", min_value=1, step=1)
    nuevo_estado = st.selectbox("Estado de Pago", ["Pagado", "Pendiente"])
    if st.button("Actualizar Pago"):
        if id_pago in df["ID"].values:
            df.loc[df["ID"] == id_pago, "Pagado"] = nuevo_estado
            df.to_excel(DATA_FILE, index=False)
            st.success(f"Orden #{id_pago} actualizada")
            st.rerun()

# ==================== GASTOS ====================
elif menu == "💸 Gastos":
    st.subheader("💸 Gastos del Negocio")
    tab1, tab2 = st.tabs(["Registrar Gasto", "Ver Resumen"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            desc = st.text_input("Descripción del gasto")
            monto = st.number_input("Monto ($)", min_value=0, step=1000)
        with col2:
            cat = st.selectbox("Categoría", ["Repuestos", "Herramientas", "Alquiler", "Servicios", "Otros"])
        
        if st.button("💾 Registrar Gasto"):
            if desc and monto > 0:
                nuevo = {
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Descripcion": desc,
                    "Monto": monto,
                    "Categoria": cat
                }
                gastos = pd.concat([gastos, pd.DataFrame([nuevo])], ignore_index=True)
                gastos.to_excel(GASTOS_FILE, index=False)
                st.success("✅ Gasto registrado")
                st.rerun()

    with tab2:
        if not gastos.empty:
            st.dataframe(gastos, use_container_width=True, hide_index=True)
            st.metric("Total Gastos", f"${gastos['Monto'].sum():,.0f}")
        else:
            st.info("Aún no hay gastos registrados")

st.sidebar.metric("Total Órdenes", len(df))