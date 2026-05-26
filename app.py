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

# Logo + Nombre
col1, col2 = st.columns([1, 4])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=180)
    else:
        st.write("🔧")
with col2:
    st.title("Electronic Tech Service")

st.markdown("**Servicio Técnico Electrónico**")
st.markdown("---")

# ==================== ARCHIVOS ====================
DATA_FILE = "reparaciones.xlsx"
ARCHIVE_FOLDER = "cortes_mensuales"

if not os.path.exists(ARCHIVE_FOLDER):
    os.makedirs(ARCHIVE_FOLDER)

if os.path.exists(DATA_FILE):
    df = pd.read_excel(DATA_FILE)
else:
    df = pd.DataFrame(columns=["ID", "Fecha", "Cliente", "Telefono", "Equipo", "Problema", 
                               "Precio_Estimado", "Estado", "Tecnico", "Notas", "Pagado"])

if "Pagado" not in df.columns:
    df["Pagado"] = "Pendiente"

# ==================== MENÚ ====================
menu = st.sidebar.selectbox("Menú", 
    ["🏠 Inicio", "📋 Nueva Reparación", "📋 Ver Órdenes", "🔍 Buscar", 
     "📄 Cotizaciones", "🖨️ Imprimir Recibo", "📦 Inventario", "📊 Contabilidad", 
     "💸 Gastos", "📅 Corte de Mes"])

# ==================== INICIO ====================
if menu == "🏠 Inicio":
    st.subheader("Resumen del Día")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Órdenes", len(df))
    col2.metric("Pendientes", len(df[df["Estado"] != "Entregado"]) if not df.empty else 0)
    col3.metric("Hoy", len(df[df["Fecha"].astype(str).str.contains(datetime.now().strftime("%Y-%m-%d"))]) if not df.empty else 0)

# ==================== NUEVA REPARACIÓN ====================
elif menu == "📋 Nueva Reparación":
    # (código anterior)
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

# ==================== VER ÓRDENES (Editar + Eliminar) ====================
elif menu == "📋 Ver Órdenes":
    st.subheader("📋 Todas las Reparaciones")
    if not df.empty:
        df_display = df.copy()
        df_display["Precio_Estimado"] = df_display["Precio_Estimado"].apply(lambda x: f"${int(x):,}" if pd.notna(x) else "$0")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.subheader("✏️ Editar o Eliminar")
        id_accion = st.number_input("ID de la Orden", min_value=1, step=1)
        accion = st.radio("Acción", ["Editar", "Eliminar"])
        if st.button("Ejecutar Acción"):
            if id_accion in df["ID"].values:
                if accion == "Eliminar":
                    df = df[df["ID"] != id_accion]
                    df.to_excel(DATA_FILE, index=False)
                    st.success("Orden eliminada")
                    st.rerun()
                # Editar se puede expandir más adelante
            else:
                st.error("ID no encontrado")
    else:
        st.info("No hay órdenes")

# ==================== CORTE DE MES ====================
elif menu == "📅 Corte de Mes":
    st.subheader("📅 Corte Mensual")
    
    mes_actual = datetime.now().strftime("%Y-%m")
    if st.button("🔴 Cerrar Mes Actual y Guardar Corte"):
        if not df.empty:
            nombre_corte = f"corte_{mes_actual}.xlsx"
            ruta_corte = os.path.join("cortes_mensuales", nombre_corte)
            df.to_excel(ruta_corte, index=False)
            
            # Limpiar el archivo actual
            df = pd.DataFrame(columns=df.columns)
            df.to_excel(DATA_FILE, index=False)
            
            st.success(f"✅ Mes {mes_actual} cerrado correctamente. Archivo guardado.")
            st.balloons()
        else:
            st.warning("No hay datos para cerrar el mes.")

    st.subheader("Cortes Guardados")
    if os.path.exists("cortes_mensuales"):
        cortes = os.listdir("cortes_mensuales")
        if cortes:
            for corte in sorted(cortes, reverse=True):
                if st.button(f"Ver {corte}"):
                    df_corte = pd.read_excel(os.path.join("cortes_mensuales", corte))
                    st.dataframe(df_corte, use_container_width=True)
        else:
            st.info("Aún no hay cortes guardados.")

st.sidebar.metric("Total Órdenes", len(df))
