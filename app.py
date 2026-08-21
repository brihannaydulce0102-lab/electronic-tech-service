import streamlit as st
import pandas as pd
from datetime import datetime
import os
import shutil

st.set_page_config(
    page_title="Electronic Tech Service",
    page_icon="logo.png",
    layout="wide"
)

st.markdown("""
<style>
    .stApp { background-color: #0a0a23; color: #ffffff; }
    .stButton>button {
        background-color: #00f5ff;
        color: #000000;
        font-weight: bold;
        padding: 12px;
        border-radius: 10px;
    }
    h1, h2, h3 { color: #00f5ff; }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# ARCHIVOS
# ==========================================================

DATA_FILE = "reparaciones.xlsx"
INV_FILE = "inventario.xlsx"
GASTOS_FILE = "gastos.xlsx"
USERS_FILE = "usuarios.xlsx"

ARCHIVE_FOLDER = "cortes_mensuales"
PHOTO_FOLDER = "fotos_equipos"

if not os.path.exists(ARCHIVE_FOLDER):
    os.makedirs(ARCHIVE_FOLDER)

if not os.path.exists(PHOTO_FOLDER):
    os.makedirs(PHOTO_FOLDER)


# ==========================================================
# USUARIOS
# ==========================================================

if not os.path.exists(USERS_FILE):
    pd.DataFrame([
        {
            "usuario": "admin",
            "password": "123456",
            "rol": "admin"
        }
    ]).to_excel(USERS_FILE, index=False)

usuarios = pd.read_excel(USERS_FILE)


# ==========================================================
# LOGIN
# ==========================================================

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

        if st.button(
            "Entrar",
            type="primary",
            use_container_width=True
        ):

            usuario_busqueda = usuarios[
                usuarios["usuario"].astype(str).str.strip().str.lower()
                == usuario.strip().lower()
            ]

            if not usuario_busqueda.empty:

                usuario_encontrado = usuario_busqueda.iloc[0]

                if str(usuario_encontrado["password"]) == password.strip():

                    st.session_state.logged_in = True
                    st.session_state.usuario = usuario_encontrado["usuario"]
                    st.session_state.rol = usuario_encontrado["rol"]

                    st.success(
                        f"Bienvenido {st.session_state.usuario}"
                    )

                    st.rerun()

                else:
                    st.error("Usuario o contraseña incorrectos")

            else:
                st.error("Usuario o contraseña incorrectos")

    st.stop()


# ==========================================================
# DESPUÉS DEL LOGIN
# ==========================================================

col1, col2 = st.columns([1, 4])

with col1:

    if os.path.exists("logo.png"):
        st.image("logo.png", width=180)

with col2:

    st.title("Electronic Tech Service")


st.markdown(
    f"**Usuario:** {st.session_state.usuario} "
    f"({st.session_state.rol})"
)

st.markdown("---")


if st.sidebar.button("Cerrar Sesión"):

    st.session_state.logged_in = False
    st.session_state.usuario = ""
    st.session_state.rol = ""

    st.rerun()


# ==========================================================
# REPARACIONES
# ==========================================================

if os.path.exists(DATA_FILE):

    df = pd.read_excel(DATA_FILE)

else:

    df = pd.DataFrame(columns=[
        "ID",
        "Fecha",
        "Cliente",
        "Telefono",
        "Equipo",
        "Problema",
        "Precio_Estimado",
        "Estado",
        "Tecnico",
        "Notas",
        "Pagado",
        "Foto"
    ])


# Si el archivo viejo no tiene Foto
if "Foto" not in df.columns:
    df["Foto"] = ""


if "Pagado" not in df.columns:
    df["Pagado"] = "Pendiente"


# ==========================================================
# INVENTARIO
# ==========================================================

if os.path.exists(INV_FILE):

    inv = pd.read_excel(INV_FILE)

else:

    inv = pd.DataFrame(columns=[
        "Producto",
        "Cantidad",
        "Precio_Unitario",
        "Fecha_Actualizacion"
    ])


# ==========================================================
# GASTOS
# ==========================================================

if os.path.exists(GASTOS_FILE):

    gastos = pd.read_excel(GASTOS_FILE)

else:

    gastos = pd.DataFrame(columns=[
        "Fecha",
        "Descripcion",
        "Monto",
        "Categoria"
    ])


# ==========================================================
# MENÚ
# ==========================================================

menu_opciones = [
    "🏠 Inicio",
    "📋 Nueva Reparación",
    "📋 Ver Órdenes",
    "🔍 Buscar",
    "📄 Cotizaciones",
    "🖨️ Imprimir Recibo"
]


if st.session_state.rol == "admin":

    menu_opciones += [
        "📦 Inventario",
        "📊 Contabilidad",
        "💸 Gastos",
        "📅 Corte de Mes",
        "👥 Gestionar Usuarios"
    ]


menu = st.sidebar.selectbox(
    "Menú",
    menu_opciones
)


# ==========================================================
# INICIO
# ==========================================================

if menu == "🏠 Inicio":

    st.subheader("Resumen del Día")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Órdenes",
        len(df)
    )

    col2.metric(
        "Pendientes",
        len(df[df["Estado"] != "Entregado"])
        if not df.empty else 0
    )

    col3.metric(
        "Hoy",
        len(
            df[
                df["Fecha"]
                .astype(str)
                .str.contains(
                    datetime.now().strftime("%Y-%m-%d")
                )
            ]
        )
        if not df.empty else 0
    )


# ==========================================================
# NUEVA REPARACIÓN
# ==========================================================

elif menu == "📋 Nueva Reparación":

    st.subheader("📋 Nueva Orden de Reparación")

    col1, col2 = st.columns(2)

    with col1:

        cliente = st.text_input(
            "Nombre del Cliente *"
        )

        telefono = st.text_input(
            "Teléfono / WhatsApp *"
        )

        equipo = st.text_input(
            "Equipo *"
        )

        # NUEVO
        foto_equipo = st.file_uploader(
            "📷 Foto del equipo",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp"
            ]
        )

    with col2:

        problema = st.text_area(
            "Descripción del problema *"
        )

        precio = st.number_input(
            "Precio estimado ($)",
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


    # Mostrar vista previa
    if foto_equipo is not None:

        st.markdown("### 📷 Vista previa")

        st.image(
            foto_equipo,
            width=300
        )


    if st.button(
        "💾 Guardar Orden",
        type="primary"
    ):

        if cliente and telefono and equipo and problema:

            # CORRECCIÓN DEL ID
            if df.empty:
                nuevo_id = 1
            else:
                nuevo_id = int(df["ID"].max()) + 1


            # ==========================================
            # GUARDAR FOTO
            # ==========================================

            ruta_foto = ""

            if foto_equipo is not None:

                extension = os.path.splitext(
                    foto_equipo.name
                )[1].lower()

                nombre_foto = (
                    f"orden_{nuevo_id}"
                    f"_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    f"{extension}"
                )

                ruta_foto = os.path.join(
                    PHOTO_FOLDER,
                    nombre_foto
                )

                with open(
                    ruta_foto,
                    "wb"
                ) as archivo:

                    archivo.write(
                        foto_equipo.getbuffer()
                    )


            # ==========================================
            # NUEVA ORDEN
            # ==========================================

            nueva = {

                "ID": nuevo_id,

                "Fecha":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    ),

                "Cliente":
                    cliente,

                "Telefono":
                    telefono,

                "Equipo":
                    equipo,

                "Problema":
                    problema,

                "Precio_Estimado":
                    int(precio),

                "Estado":
                    estado,

                "Tecnico":
                    st.session_state.usuario,

                "Notas":
                    "",

                "Pagado":
                    "Pendiente",

                "Foto":
                    ruta_foto
            }


            df = pd.concat(
                [
                    df,
                    pd.DataFrame([nueva])
                ],
                ignore_index=True
            )


            df.to_excel(
                DATA_FILE,
                index=False
            )


            st.success(
                f"✅ Orden #{nuevo_id} guardada!"
            )

            if ruta_foto:
                st.success(
                    "📷 Fotografía del equipo guardada correctamente"
                )

            st.balloons()

        else:

            st.error(
                "Completa los campos obligatorios"
            )


# ==========================================================
# VER ÓRDENES
# ==========================================================

elif menu == "📋 Ver Órdenes":

    st.subheader("📋 Todas las Reparaciones")

    if not df.empty:

        # ==========================================
        # MOSTRAR ÓRDENES CON FOTO
        # ==========================================

        for _, orden in df.iterrows():

            st.markdown("---")

            col_foto, col_info = st.columns(
                [1, 4]
            )


            # FOTO
            with col_foto:

                foto = str(
                    orden.get("Foto", "")
                )

                if foto and os.path.exists(foto):

                    st.image(
                        foto,
                        width=180
                    )

                else:

                    st.info(
                        "📷 Sin foto"
                    )


            # INFORMACIÓN
            with col_info:

                st.markdown(
                    f"### 🔧 Orden #{orden['ID']}"
                )

                st.write(
                    f"**Cliente:** "
                    f"{orden['Cliente']}"
                )

                st.write(
                    f"**Teléfono:** "
                    f"{orden['Telefono']}"
                )

                st.write(
                    f"**Equipo:** "
                    f"{orden['Equipo']}"
                )

                st.write(
                    f"**Problema:** "
                    f"{orden['Problema']}"
                )

                st.write(
                    f"**Precio estimado:** "
                    f"${orden['Precio_Estimado']:,.0f}"
                )

                st.write(
                    f"**Estado:** "
                    f"{orden['Estado']}"
                )

                st.write(
                    f"**Técnico:** "
                    f"{orden['Tecnico']}"
                )

                st.write(
                    f"**Fecha:** "
                    f"{orden['Fecha']}"
                )


        # ==========================================
        # TABLA COMPLETA
        # ==========================================

        with st.expander(
            "📊 Ver tabla completa"
        ):

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )


        # ==========================================
        # ELIMINAR ORDEN
        # ==========================================

        if st.session_state.rol == "admin":

            st.subheader(
                "✏️ Eliminar Orden "
                "(Solo Administrador)"
            )

            id_accion = st.number_input(
                "ID de la Orden",
                min_value=1,
                step=1
            )


            if st.button(
                "🗑️ Eliminar Orden"
            ):

                if id_accion in df["ID"].values:

                    # Buscar fotografía
                    orden_eliminar = df[
                        df["ID"] == id_accion
                    ]

                    if not orden_eliminar.empty:

                        foto = str(
                            orden_eliminar.iloc[0].get(
                                "Foto",
                                ""
                            )
                        )

                        # Eliminar foto
                        if foto and os.path.exists(foto):

                            os.remove(foto)


                    df = df[
                        df["ID"] != id_accion
                    ]

                    df.to_excel(
                        DATA_FILE,
                        index=False
                    )

                    st.success(
                        "Orden eliminada"
                    )

                    st.rerun()

                else:

                    st.error(
                        "ID no encontrado"
                    )

        else:

            st.info(
                "Solo el administrador puede eliminar órdenes"
            )

    else:

        st.info(
            "No hay órdenes registradas"
        )


# ==========================================================
# BUSCAR
# ==========================================================

elif menu == "🔍 Buscar":

    st.subheader("🔍 Buscar Órdenes")

    texto_busqueda = st.text_input(
        "Buscar por cliente, teléfono, equipo o ID"
    )

    if texto_busqueda:

        resultado = df[
            df["Cliente"]
            .astype(str)
            .str.contains(
                texto_busqueda,
                case=False,
                na=False
            )
            |
            df["Telefono"]
            .astype(str)
            .str.contains(
                texto_busqueda,
                case=False,
                na=False
            )
            |
            df["Equipo"]
            .astype(str)
            .str.contains(
                texto_busqueda,
                case=False,
                na=False
            )
            |
            df["ID"]
            .astype(str)
            .str.contains(
                texto_busqueda,
                case=False,
                na=False
            )
        ]


        if not resultado.empty:

            st.success(
                f"Se encontraron {len(resultado)} orden(es)"
            )


            for _, orden in resultado.iterrows():

                st.markdown("---")

                col_foto, col_info = st.columns(
                    [1, 4]
                )


                with col_foto:

                    foto = str(
                        orden.get(
                            "Foto",
                            ""
                        )
                    )

                    if foto and os.path.exists(foto):

                        st.image(
                            foto,
                            width=180
                        )

                    else:

                        st.info(
                            "📷 Sin foto"
                        )


                with col_info:

                    st.markdown(
                        f"### 🔧 Orden #{orden['ID']}"
                    )

                    st.write(
                        f"**Cliente:** "
                        f"{orden['Cliente']}"
                    )

                    st.write(
                        f"**Equipo:** "
                        f"{orden['Equipo']}"
                    )

                    st.write(
                        f"**Problema:** "
                        f"{orden['Problema']}"
                    )

                    st.write(
                        f"**Estado:** "
                        f"{orden['Estado']}"
                    )

                    st.write(
                        f"**Precio:** "
                        f"${orden['Precio_Estimado']:,.0f}"
                    )

        else:

            st.warning(
                "No se encontraron órdenes"
            )


# ==========================================================
# COTIZACIONES
# ==========================================================

elif menu == "📄 Cotizaciones":

    st.subheader("📄 Nueva Cotización")

    col1, col2 = st.columns(2)

    with col1:

        cliente_cot = st.text_input(
            "Nombre del Cliente"
        )

        telefono_cot = st.text_input(
            "Teléfono"
        )

        equipo_cot = st.text_input(
            "Equipo"
        )

    with col2:

        descripcion_cot = st.text_area(
            "Descripción del servicio"
        )

        precio_cot = st.number_input(
            "Precio cotizado ($)",
            min_value=0,
            step=1000
        )


    if st.button(
        "Generar Cotización",
        type="primary"
    ):

        if cliente_cot and precio_cot > 0:

            st.markdown(
                f"""
                <div style="
                    background-color: white;
                    color: black;
                    padding: 25px;
                    border-radius: 10px;
                    max-width: 600px;
                    margin: auto;
                ">

                    <h2 style="text-align: center;">
                        Electronic Tech Service
                    </h2>

                    <p style="text-align: center;">
                        Cotización —
                        {datetime.now().strftime("%d/%m/%Y")}
                    </p>

                    <hr>

                    <p>
                        <strong>Cliente:</strong>
                        {cliente_cot}
                    </p>

                    <p>
                        <strong>Teléfono:</strong>
                        {telefono_cot}
                    </p>

                    <p>
                        <strong>Equipo:</strong>
                        {equipo_cot}
                    </p>

                    <p>
                        <strong>Descripción:</strong>
                        {descripcion_cot}
                    </p>

                    <h3 style="text-align: right;">
                        Total: ${int(precio_cot):,}
                    </h3>

                    <hr>

                    <p style="text-align: center;">
                        Montería - Córdoba
                        • Barrio El Mundo López
                    </p>

                    <p style="text-align: center;">
                        WhatsApp:
                        <strong>301 487 4740</strong>
                    </p>

                </div>
                """,
                unsafe_allow_html=True
            )

        else:

            st.error(
                "Completa los campos"
            )


# ==========================================================
# INVENTARIO
# ==========================================================

elif menu == "📦 Inventario":

    if st.session_state.rol == "admin":

        st.subheader(
            "📦 Gestión de Inventario"
        )

        tab1, tab2 = st.tabs(
            [
                "Ver Inventario",
                "Agregar Producto"
            ]
        )


        with tab1:

            if not inv.empty:

                st.dataframe(
                    inv,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "No hay productos en inventario"
                )


        with tab2:

            producto = st.text_input(
                "Nombre del Producto"
            )

            cantidad = st.number_input(
                "Cantidad",
                min_value=1,
                value=1
            )

            precio = st.number_input(
                "Precio Unitario",
                min_value=0
            )


            if st.button("Agregar"):

                if producto:

                    nuevo = {

                        "Producto":
                            producto,

                        "Cantidad":
                            cantidad,

                        "Precio_Unitario":
                            precio,

                        "Fecha_Actualizacion":
                            datetime.now().strftime(
                                "%Y-%m-%d %H:%M"
                            )
                    }


                    inv = pd.concat(
                        [
                            inv,
                            pd.DataFrame([nuevo])
                        ],
                        ignore_index=True
                    )


                    inv.to_excel(
                        INV_FILE,
                        index=False
                    )


                    st.success(
                        "Producto agregado"
                    )

                    st.rerun()

    else:

        st.warning(
            "Solo el administrador puede ver el inventario"
        )


# ==========================================================
# CONTABILIDAD
# ==========================================================

elif menu == "📊 Contabilidad":

    if st.session_state.rol == "admin":

        st.subheader(
            "📊 Contabilidad"
        )

        total = (
            df["Precio_Estimado"].sum()
            if not df.empty
            else 0
        )

        st.metric(
            "Total Estimado",
            f"${total:,.0f}"
        )

    else:

        st.warning(
            "Solo el administrador puede ver la contabilidad"
        )


# ==========================================================
# GASTOS
# ==========================================================

elif menu == "💸 Gastos":

    if st.session_state.rol == "admin":

        st.subheader(
            "💸 Gastos"
        )

        desc = st.text_input(
            "Descripción del gasto"
        )

        monto = st.number_input(
            "Monto",
            min_value=0,
            step=1000
        )


        if st.button(
            "Registrar Gasto"
        ):

            if desc and monto > 0:

                nuevo = {

                    "Fecha":
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M"
                        ),

                    "Descripcion":
                        desc,

                    "Monto":
                        monto,

                    "Categoria":
                        "General"
                }


                gastos = pd.concat(
                    [
                        gastos,
                        pd.DataFrame([nuevo])
                    ],
                    ignore_index=True
                )


                gastos.to_excel(
                    GASTOS_FILE,
                    index=False
                )


                st.success(
                    "Gasto registrado"
                )

                st.rerun()


        if not gastos.empty:

            st.dataframe(
                gastos,
                use_container_width=True,
                hide_index=True
            )

    else:

        st.warning(
            "Solo el administrador puede registrar gastos"
        )


# ==========================================================
# CORTE DE MES
# ==========================================================

elif menu == "📅 Corte de Mes":

    if st.session_state.rol == "admin":

        st.subheader(
            "📅 Corte Mensual"
        )


        if st.button(
            "🔴 Cerrar Mes Actual"
        ):

            if not df.empty:

                mes = datetime.now().strftime(
                    "%Y-%m"
                )

                ruta = os.path.join(
                    ARCHIVE_FOLDER,
                    f"corte_{mes}.xlsx"
                )


                df.to_excel(
                    ruta,
                    index=False
                )


                df = pd.DataFrame(
                    columns=df.columns
                )


                df.to_excel(
                    DATA_FILE,
                    index=False
                )


                st.success(
                    f"Mes {mes} cerrado y guardado"
                )

                st.balloons()

            else:

                st.warning(
                    "No hay datos para cerrar"
                )

    else:

        st.warning(
            "Solo el administrador puede hacer el corte de mes"
        )


# ==========================================================
# GESTIONAR USUARIOS
# ==========================================================

elif menu == "👥 Gestionar Usuarios":

    if st.session_state.rol == "admin":

        st.subheader(
            "👥 Gestionar Usuarios"
        )


        st.dataframe(
            usuarios,
            use_container_width=True,
            hide_index=True
        )


        st.subheader(
            "Crear nuevo usuario"
        )


        nuevo_usuario = st.text_input(
            "Nuevo usuario"
        )

        nueva_password = st.text_input(
            "Contraseña",
            type="password"
        )

        nuevo_rol = st.selectbox(
            "Rol",
            [
                "trabajador",
                "admin"
            ]
        )


        if st.button(
            "Crear Usuario"
        ):

            if nuevo_usuario and nueva_password:

                if nuevo_usuario in usuarios[
                    "usuario"
                ].values:

                    st.error(
                        "Ese usuario ya existe"
                    )

                else:

                    nuevo = pd.DataFrame([
                        {
                            "usuario":
                                nuevo_usuario,

                            "password":
                                nueva_password,

                            "rol":
                                nuevo_rol
                        }
                    ])


                    usuarios = pd.concat(
                        [
                            usuarios,
                            nuevo
                        ],
                        ignore_index=True
                    )


                    usuarios.to_excel(
                        USERS_FILE,
                        index=False
                    )


                    st.success(
                        f"Usuario {nuevo_usuario} creado"
                    )

                    st.rerun()

    else:

        st.warning(
            "Solo el administrador puede gestionar usuarios"
        )


# ==========================================================
# TOTAL ÓRDENES
# ==========================================================

st.sidebar.metric(
    "Total Órdenes",
    len(df)
)
