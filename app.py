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

# ==================== LOGIN ====================
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

# ==================== DESPUÉS DEL LOGIN ====================
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

# ==================== DATOS ====================
DATA_FILE = "reparaciones.xlsx"
USERS_FILE = "usuarios.xlsx"

if os.path.exists(DATA_FILE):
    df = pd.read_excel(DATA_FILE)
else:
    df = pd.DataFrame(columns=["ID", "Fecha", "Cliente", "Telefono", "Equipo", "Problema", "Precio_Estimado", "Estado", "Tecnico", "Notas", "Pagado"])

if "Pagado" not in df.columns:
    df["Pagado"] = "Pendiente"

if not os.path.exists(USERS_FILE):
    pd.DataFrame([{"usuario": "admin", "password": "123456", "rol": "admin"}]).to_excel(USERS_FILE, index=False)

usuarios = pd.read_excel(USERS_FILE)

# ==================== MENÚ ====================
menu_opciones = ["🏠 Inicio", "📋 Nueva Reparación", "📋 Ver Órdenes", "🔍 Buscar", "📄 Cotizaciones", "🖨️ Imprimir Recibo"]

if st.session_state.rol == "admin":
    menu_opciones += ["📦 Inventario", "📊 Contabilidad", "💸 Gastos", "📅 Corte de Mes", "👥 Gestionar Usuarios"]

menu = st.sidebar.selectbox("Menú", menu_opciones)

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
    
    if st.button("💾 Guardar Orden", type="primary"):
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
                "Tecnico": st.session_state.usuario,
                "Notas": "",
                "Pagado": "Pendiente"
            }
            df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            df.to_excel(DATA_FILE, index=False)
            st.success(f"✅ Orden #{nuevo_id} guardada!")
            st.balloons()
        else:
            st.error("Completa los campos obligatorios")

# ==================== VER ÓRDENES ====================
elif menu == "📋 Ver Órdenes":
    st.subheader("📋 Todas las Reparaciones")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        if st.session_state.rol == "admin":
            st.subheader("✏️ Eliminar Orden (Solo Administrador)")
            id_accion = st.number_input("ID de la Orden", min_value=1, step=1)
            if st.button("🗑️ Eliminar Orden"):
                if id_accion in df["ID"].values:
                    df = df[df["ID"] != id_accion]
                    df.to_excel(DATA_FILE, index=False)
                    st.success("Orden eliminada")
                    st.rerun()
                else:
                    st.error("ID no encontrado")
        else:
            st.info("Solo el administrador puede eliminar órdenes")
    else:
        st.info("No hay órdenes registradas")

# ==================== GESTIONAR USUARIOS ====================
elif menu == "👥 Gestionar Usuarios":
    if st.session_state.rol == "admin":
        st.subheader("👥 Gestionar Usuarios")
        st.dataframe(usuarios, use_container_width=True, hide_index=True)
        
        st.subheader("Crear nuevo usuario")
        nuevo_usuario = st.text_input("Nuevo usuario")
        nueva_password = st.text_input("Contraseña", type="password")
        nuevo_rol = st.selectbox("Rol", ["trabajador", "admin"])
        
        if st.button("Crear Usuario"):
            if nuevo_usuario and nueva_password:
                if nuevo_usuario in usuarios["usuario"].values:
                    st.error("Ese usuario ya existe")
                else:
                    nuevo = pd.DataFrame([{"usuario": nuevo_usuario, "password": nueva_password, "rol": nuevo_rol}])
                    usuarios = pd.concat([usuarios, nuevo], ignore_index=True)
                    usuarios.to_excel(USERS_FILE, index=False)
                    st.success(f"Usuario {nuevo_usuario} creado correctamente")
                    st.rerun()
    else:
        st.warning("Solo el administrador puede gestionar usuarios")

# ==================== OTRAS SECCIONES ====================
elif menu in ["🔍 Buscar", "📄 Cotizaciones", "🖨️ Imprimir Recibo", "📦 Inventario", "📊 Contabilidad", "💸 Gastos", "📅 Corte de Mes"]:
    st.info(f"La sección **{menu}** está lista para completar. Dime si quieres que la desarrolle ahora.")

st.sidebar.metric("Total Órdenes", len(df))
