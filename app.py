# Electronic Tech Service - versión estable de un solo archivo
# Datos persistentes: PostgreSQL/Neon

import os
import re
import ast
import csv
import json
import uuid
import time
import base64
import hashlib
import urllib.parse
from io import BytesIO, StringIO
from datetime import datetime
from collections import defaultdict
from contextlib import contextmanager

import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor

# Dependencias visuales opcionales: si una falta, la app principal no se cae.
try:
    import qrcode
    HAS_QRCODE = True
except Exception:
    qrcode = None
    HAS_QRCODE = False

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except Exception:
    plt = None
    HAS_MATPLOTLIB = False

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None
    HAS_PIL = False

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except Exception:
    SimpleDocTemplate = Paragraph = Spacer = RLImage = getSampleStyleSheet = None
    HAS_REPORTLAB = False

try:
    from streamlit_drawable_canvas import st_canvas
    HAS_CANVAS = True
except Exception:
    st_canvas = None
    HAS_CANVAS = False

try:
    import streamlit.components.v1 as components
    HAS_COMPONENTS = True
except Exception:
    components = None
    HAS_COMPONENTS = False

def _get_database_url():
    """Lee DATABASE_URL desde env o Streamlit Secrets."""
    url = os.environ.get("DATABASE_URL")

    if not url:
        try:
            import streamlit as st
            if "DATABASE_URL" in st.secrets:
                url = st.secrets["DATABASE_URL"]
        except Exception:
            pass

    if not url:
        return None

    url = str(url).strip()
    url = url.replace("\n", "").replace("\r", "").replace("\t", "")
    url = re.sub(r"\s+", "", url)
    return url


def hash_password(texto: str) -> str:
    # Se conserva SHA256 para mantener compatibilidad con usuarios existentes.
    return hashlib.sha256(str(texto).encode("utf-8")).hexdigest()


@contextmanager
def get_connection():
    url = _get_database_url()

    if not url:
        raise Exception(
            "No se encontró DATABASE_URL. Configúrala en Secrets de Streamlit Cloud."
        )

    if "@host/" in url or url.endswith("@host") or "://user:pass@host" in url:
        raise Exception(
            "DATABASE_URL todavía contiene un valor de ejemplo. Usa la conexión real de Neon."
        )

    if "sslmode" not in url and url.startswith("postgres"):
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"

    conn = None
    ultimo_error = None

    # Neon puede tardar unos segundos en despertar una rama archivada.
    # Reintentamos errores transitorios, pero no una contraseña incorrecta.
    for intento in range(3):
        try:
            conn = psycopg2.connect(
                url,
                cursor_factory=RealDictCursor,
                connect_timeout=10,
                application_name="electronic-tech-service",
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            break
        except psycopg2.OperationalError as exc:
            ultimo_error = exc
            mensaje = str(exc).lower()
            if "password authentication failed" in mensaje:
                raise
            if intento == 2:
                raise
            time.sleep(1.5)

    if conn is None:
        raise ultimo_error or RuntimeError("No fue posible abrir la conexión a PostgreSQL.")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def crear_tablas():
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)

        cur.execute("SELECT valor FROM configuracion WHERE clave = 'instalacion_id'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO configuracion (clave, valor) VALUES (%s, %s)",
                ("instalacion_id", str(uuid.uuid4())),
            )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                usuario TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'trabajador',
                eliminado BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_eliminacion TIMESTAMP,
                eliminado_por TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ordenes (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                cliente TEXT NOT NULL,
                telefono TEXT,
                equipo TEXT NOT NULL,
                problema TEXT,
                precio_estimado REAL DEFAULT 0,
                estado TEXT DEFAULT 'Recibido',
                tecnico TEXT,
                notas TEXT DEFAULT '',
                pagado TEXT DEFAULT 'Pendiente',
                fotos TEXT DEFAULT '{}',
                firma TEXT DEFAULT '',
                eliminado BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_eliminacion TIMESTAMP,
                eliminado_por TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventario (
                id SERIAL PRIMARY KEY,
                producto TEXT NOT NULL,
                cantidad INTEGER DEFAULT 0,
                precio_unitario REAL DEFAULT 0,
                eliminado BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_eliminacion TIMESTAMP,
                eliminado_por TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                descripcion TEXT,
                monto REAL DEFAULT 0,
                categoria TEXT,
                eliminado BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_eliminacion TIMESTAMP,
                eliminado_por TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                producto_id INTEGER REFERENCES inventario(id) ON DELETE SET NULL,
                producto_nombre TEXT NOT NULL,
                cantidad INTEGER NOT NULL DEFAULT 1,
                precio_unitario REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                cliente TEXT,
                vendedor TEXT,
                notas TEXT DEFAULT '',
                eliminado BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_eliminacion TIMESTAMP,
                eliminado_por TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS cortes_mensuales (
                id SERIAL PRIMARY KEY,
                periodo TEXT UNIQUE NOT NULL,
                fecha_cierre TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_ordenes INTEGER DEFAULT 0,
                ingresos_reparaciones REAL DEFAULT 0,
                ingresos_ventas REAL DEFAULT 0,
                gastos REAL DEFAULT 0,
                utilidad REAL DEFAULT 0,
                usuario TEXT
            )
        """)

        # Migración segura si las tablas ya existían antes de la papelera.
        for tabla in ["usuarios", "ordenes", "inventario", "gastos", "ventas"]:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS eliminado BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS fecha_eliminacion TIMESTAMP")
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS eliminado_por TEXT")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_ordenes_estado ON ordenes(estado)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ordenes_fecha ON ordenes(fecha)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ordenes_eliminado ON ordenes(eliminado)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ventas_eliminado ON ventas(eliminado)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gastos_eliminado ON gastos(eliminado)")

        cur.execute("SELECT id, eliminado FROM usuarios WHERE LOWER(usuario) = 'admin'")
        admin_existente = cur.fetchone()
        if not admin_existente:
            cur.execute(
                "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
                ("admin", hash_password("123456"), "admin"),
            )
        elif admin_existente.get("eliminado"):
            cur.execute(
                "UPDATE usuarios SET eliminado = FALSE, fecha_eliminacion = NULL, eliminado_por = NULL, rol = 'admin' WHERE id = %s",
                (admin_existente["id"],),
            )


def obtener_diagnostico_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM configuracion WHERE clave = 'instalacion_id'")
        instalacion = cur.fetchone()
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM ordenes WHERE eliminado = FALSE) AS ordenes,
                (SELECT COUNT(*) FROM inventario WHERE eliminado = FALSE) AS productos,
                (SELECT COUNT(*) FROM ventas WHERE eliminado = FALSE) AS ventas,
                (SELECT COUNT(*) FROM gastos WHERE eliminado = FALSE) AS gastos,
                (SELECT COUNT(*) FROM usuarios WHERE eliminado = FALSE) AS usuarios,
                (SELECT COUNT(*) FROM cortes_mensuales) AS cortes,
                (
                    (SELECT COUNT(*) FROM ordenes WHERE eliminado = TRUE) +
                    (SELECT COUNT(*) FROM inventario WHERE eliminado = TRUE) +
                    (SELECT COUNT(*) FROM ventas WHERE eliminado = TRUE) +
                    (SELECT COUNT(*) FROM gastos WHERE eliminado = TRUE) +
                    (SELECT COUNT(*) FROM usuarios WHERE eliminado = TRUE)
                ) AS papelera
        """)
        datos = cur.fetchone()
        return {
            "instalacion_id": instalacion["valor"] if instalacion else "Sin ID",
            "ordenes": datos["ordenes"],
            "productos": datos["productos"],
            "ventas": datos["ventas"],
            "gastos": datos["gastos"],
            "usuarios": datos["usuarios"],
            "cortes": datos["cortes"],
            "papelera": datos["papelera"],
        }


# ==================== ÓRDENES ====================

def obtener_ordenes(incluir_media=False, limite=None):
    """
    Lista órdenes sin descargar fotos ni firma por defecto.
    Esto reduce muchísimo el tráfico con Neon en cada navegación.
    """
    columnas = """
        id, fecha, cliente, telefono, equipo, problema,
        precio_estimado, estado, tecnico, notas, pagado,
        eliminado, fecha_eliminacion, eliminado_por
    """
    if incluir_media:
        columnas = "*"

    sql = f"SELECT {columnas} FROM ordenes WHERE eliminado = FALSE ORDER BY id DESC"
    params = ()

    if limite is not None:
        sql += " LIMIT %s"
        params = (max(1, int(limite)),)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def obtener_orden(id_orden):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ordenes WHERE id = %s AND eliminado = FALSE", (id_orden,))
        return cur.fetchone()


def crear_orden(cliente, telefono, equipo, problema, precio, estado, tecnico, fotos="{}", firma=""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ordenes
            (fecha, cliente, telefono, equipo, problema, precio_estimado, estado, tecnico, fotos, firma)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            cliente.strip(),
            (telefono or "").strip(),
            equipo.strip(),
            (problema or "").strip(),
            float(precio),
            estado,
            tecnico,
            fotos,
            firma,
        ))
        return cur.fetchone()["id"]


def actualizar_orden(id_orden, **campos):
    permitidos = {
        "cliente", "telefono", "equipo", "problema", "precio_estimado",
        "estado", "tecnico", "notas", "pagado", "fotos", "firma"
    }
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return
    sets = ", ".join([f"{k} = %s" for k in campos])
    valores = list(campos.values()) + [id_orden]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE ordenes SET {sets} WHERE id = %s AND eliminado = FALSE", valores)


def actualizar_estado(id_orden, nuevo_estado):
    actualizar_orden(id_orden, estado=nuevo_estado)


def eliminar_orden(id_orden, usuario=""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE ordenes
            SET eliminado = TRUE,
                fecha_eliminacion = CURRENT_TIMESTAMP,
                eliminado_por = %s
            WHERE id = %s AND eliminado = FALSE
        """, (usuario, id_orden))


def restaurar_orden(id_orden):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE ordenes
            SET eliminado = FALSE,
                fecha_eliminacion = NULL,
                eliminado_por = NULL
            WHERE id = %s AND eliminado = TRUE
        """, (id_orden,))


def obtener_ordenes_eliminadas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                id, fecha, cliente, telefono, equipo, problema,
                precio_estimado, estado, tecnico, notas, pagado,
                fecha_eliminacion, eliminado_por
            FROM ordenes
            WHERE eliminado = TRUE
            ORDER BY fecha_eliminacion DESC, id DESC
        """)
        return cur.fetchall()


def contar_ordenes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM ordenes WHERE eliminado = FALSE")
        return cur.fetchone()["total"]


def sumar_ingresos():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(precio_estimado), 0) AS total FROM ordenes WHERE eliminado = FALSE")
        return float(cur.fetchone()["total"] or 0)


def contar_por_estado(estado):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM ordenes WHERE eliminado = FALSE AND estado = %s", (estado,))
        return cur.fetchone()["total"]


def contar_pendientes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM ordenes WHERE eliminado = FALSE AND estado != 'Entregado'")
        return cur.fetchone()["total"]


def obtener_dashboard():
    """
    Obtiene todas las métricas del inicio y las últimas 7 órdenes
    usando una sola conexión a PostgreSQL.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE eliminado = FALSE) AS total_ordenes,
                COUNT(*) FILTER (
                    WHERE eliminado = FALSE AND estado != 'Entregado'
                ) AS pendientes,
                COUNT(*) FILTER (
                    WHERE eliminado = FALSE AND estado = 'Listo'
                ) AS listos,
                COALESCE(
                    SUM(precio_estimado) FILTER (WHERE eliminado = FALSE),
                    0
                ) AS ingresos_reparaciones
            FROM ordenes
        """)
        ordenes_stats = cur.fetchone()

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE eliminado = FALSE) AS total_ventas,
                COALESCE(
                    SUM(total) FILTER (WHERE eliminado = FALSE),
                    0
                ) AS ingresos_ventas
            FROM ventas
        """)
        ventas_stats = cur.fetchone()

        cur.execute("""
            SELECT id, fecha, cliente, equipo, estado, precio_estimado
            FROM ordenes
            WHERE eliminado = FALSE
            ORDER BY id DESC
            LIMIT 7
        """)
        ultimas = cur.fetchall()

        return {
            "total_ordenes": int(ordenes_stats["total_ordenes"] or 0),
            "pendientes": int(ordenes_stats["pendientes"] or 0),
            "listos": int(ordenes_stats["listos"] or 0),
            "ingresos_reparaciones": float(ordenes_stats["ingresos_reparaciones"] or 0),
            "total_ventas": int(ventas_stats["total_ventas"] or 0),
            "ingresos_ventas": float(ventas_stats["ingresos_ventas"] or 0),
            "ultimas": ultimas,
        }


def buscar_ordenes(texto, limite=100):
    """
    Busca directamente en PostgreSQL en vez de descargar todas las órdenes
    y filtrarlas en Python.
    """
    texto = (texto or "").strip()
    if not texto:
        return []

    patron = f"%{texto}%"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                id, fecha, cliente, telefono, equipo,
                precio_estimado, estado, tecnico, pagado
            FROM ordenes
            WHERE eliminado = FALSE
              AND (
                    cliente ILIKE %s
                 OR COALESCE(telefono, '') ILIKE %s
                 OR equipo ILIKE %s
                 OR CAST(id AS TEXT) ILIKE %s
              )
            ORDER BY id DESC
            LIMIT %s
        """, (patron, patron, patron, patron, int(limite)))
        return cur.fetchall()


def obtener_resumen_contabilidad():
    """
    Métricas y acumulados por estado con una sola conexión.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COALESCE(SUM(precio_estimado), 0) AS reparaciones
            FROM ordenes
            WHERE eliminado = FALSE
        """)
        reparaciones = float(cur.fetchone()["reparaciones"] or 0)

        cur.execute("""
            SELECT COALESCE(SUM(total), 0) AS ventas
            FROM ventas
            WHERE eliminado = FALSE
        """)
        ventas = float(cur.fetchone()["ventas"] or 0)

        cur.execute("""
            SELECT COALESCE(SUM(monto), 0) AS gastos
            FROM gastos
            WHERE eliminado = FALSE
        """)
        gastos = float(cur.fetchone()["gastos"] or 0)

        cur.execute("""
            SELECT estado, COALESCE(SUM(precio_estimado), 0) AS total
            FROM ordenes
            WHERE eliminado = FALSE
            GROUP BY estado
            ORDER BY estado
        """)
        estados = cur.fetchall()

        return {
            "reparaciones": reparaciones,
            "ventas": ventas,
            "gastos": gastos,
            "estados": estados,
        }


# ==================== USUARIOS ====================

def obtener_usuarios():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE eliminado = FALSE ORDER BY id")
        return cur.fetchall()


def obtener_usuario_por_nombre(usuario):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM usuarios
            WHERE eliminado = FALSE AND LOWER(usuario) = LOWER(%s)
        """, (usuario,))
        return cur.fetchone()


def crear_usuario(usuario, password, rol="trabajador"):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
            (usuario.strip(), hash_password(password), rol),
        )


def actualizar_usuario(id_usuario, **campos):
    permitidos = {"usuario", "password", "rol"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return
    if "password" in campos and campos["password"]:
        campos["password"] = hash_password(campos["password"])
    elif "password" in campos:
        del campos["password"]
    if not campos:
        return
    sets = ", ".join([f"{k} = %s" for k in campos])
    valores = list(campos.values()) + [id_usuario]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id = %s AND eliminado = FALSE", valores)


def eliminar_usuario(id_usuario, usuario_actual=""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT usuario FROM usuarios WHERE id = %s", (id_usuario,))
        fila = cur.fetchone()
        if not fila:
            return
        if fila["usuario"].lower() == "admin":
            raise ValueError("El usuario admin principal no se puede eliminar.")
        cur.execute("""
            UPDATE usuarios
            SET eliminado = TRUE,
                fecha_eliminacion = CURRENT_TIMESTAMP,
                eliminado_por = %s
            WHERE id = %s AND eliminado = FALSE
        """, (usuario_actual, id_usuario))


def restaurar_usuario(id_usuario):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE usuarios
            SET eliminado = FALSE,
                fecha_eliminacion = NULL,
                eliminado_por = NULL
            WHERE id = %s AND eliminado = TRUE
        """, (id_usuario,))


def obtener_usuarios_eliminados():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE eliminado = TRUE ORDER BY fecha_eliminacion DESC, id DESC")
        return cur.fetchall()


# ==================== INVENTARIO ====================

def obtener_inventario():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventario WHERE eliminado = FALSE ORDER BY id")
        return cur.fetchall()


def obtener_producto(id_producto):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventario WHERE id = %s AND eliminado = FALSE", (id_producto,))
        return cur.fetchone()


def crear_producto(producto, cantidad, precio_unitario):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO inventario (producto, cantidad, precio_unitario) VALUES (%s, %s, %s)",
            (producto.strip(), int(cantidad), float(precio_unitario)),
        )


def actualizar_producto(id_producto, **campos):
    permitidos = {"producto", "cantidad", "precio_unitario"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return
    sets = ", ".join([f"{k} = %s" for k in campos])
    valores = list(campos.values()) + [id_producto]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE inventario SET {sets} WHERE id = %s AND eliminado = FALSE", valores)


def eliminar_producto(id_producto, usuario=""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE inventario
            SET eliminado = TRUE,
                fecha_eliminacion = CURRENT_TIMESTAMP,
                eliminado_por = %s
            WHERE id = %s AND eliminado = FALSE
        """, (usuario, id_producto))


def restaurar_producto(id_producto):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE inventario
            SET eliminado = FALSE,
                fecha_eliminacion = NULL,
                eliminado_por = NULL
            WHERE id = %s AND eliminado = TRUE
        """, (id_producto,))


def obtener_productos_eliminados():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventario WHERE eliminado = TRUE ORDER BY fecha_eliminacion DESC, id DESC")
        return cur.fetchall()


# ==================== VENTAS ====================

def crear_venta(producto_id, cantidad, cliente="", vendedor="", notas=""):
    cantidad = int(cantidad)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM inventario
            WHERE id = %s AND eliminado = FALSE
            FOR UPDATE
        """, (producto_id,))
        prod = cur.fetchone()

        if not prod:
            raise ValueError("Producto no encontrado o está en la papelera.")
        if prod["cantidad"] < cantidad:
            raise ValueError(
                f"Stock insuficiente. Disponible: {prod['cantidad']}, solicitado: {cantidad}"
            )

        precio_unit = float(prod["precio_unitario"] or 0)
        total = precio_unit * cantidad

        cur.execute(
            "UPDATE inventario SET cantidad = cantidad - %s WHERE id = %s",
            (cantidad, producto_id),
        )

        cur.execute("""
            INSERT INTO ventas
            (fecha, producto_id, producto_nombre, cantidad, precio_unitario, total, cliente, vendedor, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            producto_id,
            prod["producto"],
            cantidad,
            precio_unit,
            total,
            cliente or "",
            vendedor or "",
            notas or "",
        ))
        return cur.fetchone()["id"]


def obtener_ventas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas WHERE eliminado = FALSE ORDER BY id DESC")
        return cur.fetchall()


def eliminar_venta(id_venta, usuario=""):
    """Manda la venta a papelera y devuelve el stock una sola vez."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas WHERE id = %s AND eliminado = FALSE FOR UPDATE", (id_venta,))
        venta = cur.fetchone()
        if not venta:
            return

        if venta["producto_id"]:
            cur.execute(
                "UPDATE inventario SET cantidad = cantidad + %s WHERE id = %s",
                (venta["cantidad"], venta["producto_id"]),
            )

        cur.execute("""
            UPDATE ventas
            SET eliminado = TRUE,
                fecha_eliminacion = CURRENT_TIMESTAMP,
                eliminado_por = %s
            WHERE id = %s
        """, (usuario, id_venta))


def restaurar_venta(id_venta):
    """Restaura la venta y vuelve a descontar el stock."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas WHERE id = %s AND eliminado = TRUE FOR UPDATE", (id_venta,))
        venta = cur.fetchone()
        if not venta:
            return

        if venta["producto_id"]:
            cur.execute("SELECT * FROM inventario WHERE id = %s FOR UPDATE", (venta["producto_id"],))
            prod = cur.fetchone()
            if not prod:
                raise ValueError("No se puede restaurar: el producto asociado ya no existe.")
            if prod.get("eliminado"):
                raise ValueError("Restaura primero el producto asociado desde la Papelera y luego restaura la venta.")
            if prod["cantidad"] < venta["cantidad"]:
                raise ValueError(
                    f"No se puede restaurar la venta: stock actual {prod['cantidad']}, se necesitan {venta['cantidad']}."
                )
            cur.execute(
                "UPDATE inventario SET cantidad = cantidad - %s WHERE id = %s",
                (venta["cantidad"], venta["producto_id"]),
            )

        cur.execute("""
            UPDATE ventas
            SET eliminado = FALSE,
                fecha_eliminacion = NULL,
                eliminado_por = NULL
            WHERE id = %s
        """, (id_venta,))


def obtener_ventas_eliminadas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas WHERE eliminado = TRUE ORDER BY fecha_eliminacion DESC, id DESC")
        return cur.fetchall()


def sumar_ventas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(total), 0) AS total FROM ventas WHERE eliminado = FALSE")
        return float(cur.fetchone()["total"] or 0)


def contar_ventas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM ventas WHERE eliminado = FALSE")
        return cur.fetchone()["total"]


# ==================== GASTOS ====================

def obtener_gastos():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM gastos WHERE eliminado = FALSE ORDER BY id DESC")
        return cur.fetchall()


def crear_gasto(descripcion, monto, categoria):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO gastos (fecha, descripcion, monto, categoria) VALUES (%s, %s, %s, %s)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), descripcion.strip(), float(monto), categoria),
        )


def sumar_gastos():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(monto), 0) AS total FROM gastos WHERE eliminado = FALSE")
        return float(cur.fetchone()["total"] or 0)


def eliminar_gasto(id_gasto, usuario=""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE gastos
            SET eliminado = TRUE,
                fecha_eliminacion = CURRENT_TIMESTAMP,
                eliminado_por = %s
            WHERE id = %s AND eliminado = FALSE
        """, (usuario, id_gasto))


def restaurar_gasto(id_gasto):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE gastos
            SET eliminado = FALSE,
                fecha_eliminacion = NULL,
                eliminado_por = NULL
            WHERE id = %s AND eliminado = TRUE
        """, (id_gasto,))


def obtener_gastos_eliminados():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM gastos WHERE eliminado = TRUE ORDER BY fecha_eliminacion DESC, id DESC")
        return cur.fetchall()


# ==================== CORTES MENSUALES ====================

def crear_corte_mensual(periodo, usuario=""):
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*) AS cantidad, COALESCE(SUM(precio_estimado), 0) AS total
            FROM ordenes
            WHERE eliminado = FALSE AND LEFT(fecha, 7) = %s
        """, (periodo,))
        reparaciones = cur.fetchone()

        cur.execute("""
            SELECT COALESCE(SUM(total), 0) AS total
            FROM ventas
            WHERE eliminado = FALSE AND LEFT(fecha, 7) = %s
        """, (periodo,))
        ventas = cur.fetchone()

        cur.execute("""
            SELECT COALESCE(SUM(monto), 0) AS total
            FROM gastos
            WHERE eliminado = FALSE AND LEFT(fecha, 7) = %s
        """, (periodo,))
        gastos = cur.fetchone()

        total_reparaciones = float(reparaciones["total"] or 0)
        total_ventas = float(ventas["total"] or 0)
        total_gastos = float(gastos["total"] or 0)
        utilidad = total_reparaciones + total_ventas - total_gastos

        cur.execute("""
            INSERT INTO cortes_mensuales
            (periodo, total_ordenes, ingresos_reparaciones, ingresos_ventas, gastos, utilidad, usuario)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (periodo)
            DO UPDATE SET
                fecha_cierre = CURRENT_TIMESTAMP,
                total_ordenes = EXCLUDED.total_ordenes,
                ingresos_reparaciones = EXCLUDED.ingresos_reparaciones,
                ingresos_ventas = EXCLUDED.ingresos_ventas,
                gastos = EXCLUDED.gastos,
                utilidad = EXCLUDED.utilidad,
                usuario = EXCLUDED.usuario
        """, (
            periodo,
            reparaciones["cantidad"],
            total_reparaciones,
            total_ventas,
            total_gastos,
            utilidad,
            usuario,
        ))

        return {
            "periodo": periodo,
            "ordenes": reparaciones["cantidad"],
            "reparaciones": total_reparaciones,
            "ventas": total_ventas,
            "gastos": total_gastos,
            "utilidad": utilidad,
        }


def obtener_cortes_mensuales():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cortes_mensuales ORDER BY periodo DESC")
        return cur.fetchall()


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

ICONO = "logo.png" if os.path.exists("logo.png") else "🔧"

st.set_page_config(
    page_title="Electronic Tech Service",
    page_icon=ICONO,
    layout="wide",
    initial_sidebar_state="auto",
)

# ==========================================================
# ESTILO
# ==========================================================

st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at top, #101047 0%, #07071f 40%, #040412 100%);
    color: white;
}
.block-container {
    max-width: 1200px;
    padding-top: 1.2rem;
    padding-bottom: 5rem;
}
h1, h2, h3 { color: #ffffff; }
.stButton > button,
.stDownloadButton > button,
[data-testid="stLinkButton"] > a {
    background: linear-gradient(135deg, #00e5ff, #00b8d4);
    color: #001014;
    font-weight: 800;
    border: none;
    border-radius: 16px;
    min-height: 46px;
    width: 100%;
}
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #12123b, #0c0c2c);
    border: 1px solid rgba(0,229,255,.18);
    padding: 16px;
    border-radius: 18px;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0a28, #05051b);
}
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
div[data-baseweb="select"] > div {
    border-radius: 14px !important;
}
footer { visibility: hidden; }
@media (max-width: 768px) {
    .block-container {
        padding-left: .8rem;
        padding-right: .8rem;
        padding-top: .7rem;
    }
    h1 { font-size: 1.65rem !important; }
    h2 { font-size: 1.35rem !important; }
    .stButton > button, .stDownloadButton > button {
        min-height: 50px;
    }
}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BASE DE DATOS
# ==========================================================

if "_db_inicializada" not in st.session_state:
    try:
        crear_tablas()
        st.session_state._db_inicializada = True
    except Exception as e:
        st.error(f"Error conectando con la base de datos: {e}")
        st.info("Verifica DATABASE_URL en Secrets de Streamlit.")
        st.stop()

ASSETS = "assets"
os.makedirs(ASSETS, exist_ok=True)

# ==========================================================
# AUXILIARES
# ==========================================================

def imagen_base64(upload):
    if not HAS_PIL:
        raise RuntimeError("Falta Pillow. Agrega 'Pillow' a requirements.txt.")
    imagen = Image.open(upload)
    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")
    imagen.thumbnail((1280, 1280))
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG", quality=78, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def mostrar_base64(texto):
    if not texto:
        return None
    return base64.b64decode(texto)


def normalizar_whatsapp(telefono):
    numeros = re.sub(r"\D", "", str(telefono or ""))
    if not numeros:
        return ""
    return numeros if numeros.startswith("57") else f"57{numeros}"


def crear_qr(texto):
    if not HAS_QRCODE:
        raise RuntimeError("Falta qrcode. Agrega 'qrcode[pil]' a requirements.txt.")
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    nombre = re.sub(r"[^a-zA-Z0-9_-]", "_", str(texto))
    ruta = os.path.join(ASSETS, f"{nombre}.png")
    img.save(ruta)
    return ruta


def crear_pdf(orden):
    if not HAS_REPORTLAB:
        raise RuntimeError("Falta reportlab. Agrega 'reportlab' a requirements.txt.")
    ruta = os.path.join(ASSETS, f"Recibo_{orden['id']}.pdf")
    doc = SimpleDocTemplate(ruta)
    estilos = getSampleStyleSheet()
    elementos = []

    if os.path.exists("logo.png"):
        elementos.append(RLImage("logo.png", 100, 100))

    elementos.append(Paragraph("<b>Electronic Tech Service</b>", estilos["Title"]))
    elementos.append(Paragraph("Montería - Córdoba", estilos["Normal"]))
    elementos.append(Spacer(1, 12))

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
        elementos.append(Paragraph(f"<b>{k}:</b> {v}", estilos["Normal"]))

    elementos.append(Paragraph(
        f"<b>Total:</b> ${float(orden['precio_estimado'] or 0):,.0f}",
        estilos["Normal"],
    ))

    qr = crear_qr(f"ETS_{orden['id']}")
    elementos.append(Spacer(1, 10))
    elementos.append(RLImage(qr, 100, 100))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        "Gracias por confiar en Electronic Tech Service.",
        estilos["Italic"],
    ))
    doc.build(elementos)
    return ruta


def boton_menu(texto):
    if st.sidebar.button(texto, use_container_width=True):
        st.session_state.opcion = texto
        st.rerun()

# ==========================================================
# LOGIN
# ==========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.usuario = ""
    st.session_state.rol = ""

if not st.session_state.logged_in:
    _, centro, _ = st.columns([1, 1.5, 1])
    with centro:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=220)
        st.title("Electronic Tech Service")
        st.caption("Sistema de gestión técnica")
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")

        if st.button("🔐 Entrar", use_container_width=True):
            user = obtener_usuario_por_nombre(usuario)
            if user and user["password"] == hash_password(clave):
                st.session_state.logged_in = True
                st.session_state.usuario = user["usuario"]
                st.session_state.rol = user["rol"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==========================================================
# CABECERA / MENÚ
# ==========================================================

c_logo, c_titulo = st.columns([1, 5])
with c_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=90)
with c_titulo:
    st.title("Electronic Tech Service")
    st.caption(f"👤 {st.session_state.usuario} • {st.session_state.rol}")

if "opcion" not in st.session_state:
    st.session_state.opcion = "🏠 Inicio"

st.sidebar.markdown("## 🔧 Electronic Tech")
st.sidebar.caption(f"Sesión: {st.session_state.usuario}")
st.sidebar.markdown("---")

for item in [
    "🏠 Inicio", "➕ Nueva Reparación", "📋 Ver Órdenes", "🔍 Buscar",
    "📄 Cotizaciones", "🖨️ Recibos", "🛒 Ventas", "📤 Exportar", "📍 Taller"
]:
    boton_menu(item)

if st.session_state.rol == "admin":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Administración")
    for item in [
        "📦 Inventario", "📊 Contabilidad", "💸 Gastos", "📅 Corte Mensual",
        "🗑️ Papelera", "👥 Usuarios", "🛡️ Sistema"
    ]:
        boton_menu(item)

st.sidebar.markdown("---")
st.sidebar.link_button("💬 WhatsApp", "https://wa.me/573014874740", use_container_width=True)
if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.usuario = ""
    st.session_state.rol = ""
    st.session_state.opcion = "🏠 Inicio"
    st.rerun()

opcion = st.session_state.opcion

# Protección de permisos: aunque quede una opción antigua en session_state,
# un trabajador nunca puede abrir pantallas exclusivas de administrador.
OPCIONES_ADMIN = {
    "📦 Inventario", "📊 Contabilidad", "💸 Gastos", "📅 Corte Mensual",
    "🗑️ Papelera", "👥 Usuarios", "🛡️ Sistema"
}
if opcion in OPCIONES_ADMIN and st.session_state.rol != "admin":
    st.session_state.opcion = "🏠 Inicio"
    opcion = "🏠 Inicio"
    st.warning("Esta sección requiere permisos de administrador.")

# ==========================================================
# INICIO
# ==========================================================

if opcion == "🏠 Inicio":
    st.subheader("🏠 Panel principal")

    panel = obtener_dashboard()
    ingresos_rep = panel["ingresos_reparaciones"]
    ingresos_ven = panel["ingresos_ventas"]
    ingresos = ingresos_rep + ingresos_ven

    c1, c2 = st.columns(2)
    c1.metric("🔧 Órdenes", panel["total_ordenes"])
    c2.metric("🛒 Ventas", panel["total_ventas"])
    c3, c4 = st.columns(2)
    c3.metric("⏳ Pendientes", panel["pendientes"])
    c4.metric("✅ Listos", panel["listos"])
    st.metric("💰 Ingresos registrados", f"${ingresos:,.0f}")
    st.caption(f"Reparaciones: ${ingresos_rep:,.0f} • Ventas: ${ingresos_ven:,.0f}")

    st.markdown("---")
    st.subheader("Últimas órdenes")
    if panel["ultimas"]:
        st.dataframe([{
            "ID": o["id"],
            "Fecha": o["fecha"],
            "Cliente": o["cliente"],
            "Equipo": o["equipo"],
            "Estado": o["estado"],
            "Precio": o["precio_estimado"],
        } for o in panel["ultimas"]], use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay órdenes.")

# ==========================================================
# NUEVA REPARACIÓN
# ==========================================================

elif opcion == "➕ Nueva Reparación":
    st.subheader("➕ Nueva orden de reparación")
    c1, c2 = st.columns(2)
    with c1:
        cliente = st.text_input("Cliente")
        telefono = st.text_input("Teléfono / WhatsApp")
        equipo = st.text_input("Equipo")
    with c2:
        problema = st.text_area("Problema reportado")
        precio = st.number_input("Precio estimado", min_value=0, step=1000)
        estado = st.selectbox("Estado", ["Recibido", "En reparación", "Listo", "Entregado"])

    st.markdown("### 📷 Evidencia fotográfica")
    antes = st.file_uploader("Foto antes", type=["jpg", "jpeg", "png"], key="foto_antes")
    durante = st.file_uploader("Foto durante", type=["jpg", "jpeg", "png"], key="foto_durante")
    despues = st.file_uploader("Foto después", type=["jpg", "jpeg", "png"], key="foto_despues")

    st.markdown("### ✍️ Firma del cliente")
    canvas = None
    firma_subida = None
    if HAS_CANVAS:
        # streamlit-drawable-canvas >= 0.10 hace image_data opcional.
        # Lo pedimos explícitamente para poder guardar la firma.
        canvas_kwargs = dict(
            stroke_width=3,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=180,
            width=320,
            drawing_mode="freedraw",
            key="firma_canvas",
        )
        try:
            canvas = st_canvas(return_image_data=True, **canvas_kwargs)
        except TypeError as exc:
            # Compatibilidad con versiones antiguas (0.9.x), donde ese
            # parámetro todavía no existía y image_data venía habilitado.
            if "return_image_data" in str(exc):
                canvas = st_canvas(**canvas_kwargs)
            else:
                raise
    else:
        st.info("El componente de firma no está disponible. Puedes subir una firma en imagen o continuar sin firma.")
        firma_subida = st.file_uploader(
            "Firma en imagen (opcional)", type=["jpg", "jpeg", "png"], key="firma_subida"
        )

    if st.button("💾 Guardar orden", type="primary", use_container_width=True):
        if not cliente.strip():
            st.error("El nombre del cliente es obligatorio.")
        elif not equipo.strip():
            st.error("El equipo es obligatorio.")
        else:
            try:
                fotos = {}
                if antes:
                    fotos["antes"] = imagen_base64(antes)
                if durante:
                    fotos["durante"] = imagen_base64(durante)
                if despues:
                    fotos["despues"] = imagen_base64(despues)

                firma = ""
                if HAS_CANVAS and canvas is not None and canvas.image_data is not None:
                    if not HAS_PIL:
                        raise RuntimeError("Falta Pillow para guardar la firma.")
                    img = Image.fromarray(canvas.image_data.astype("uint8"))
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    firma = base64.b64encode(buffer.getvalue()).decode("utf-8")
                elif firma_subida is not None:
                    firma = imagen_base64(firma_subida)

                nuevo_id = crear_orden(
                    cliente=cliente, telefono=telefono, equipo=equipo, problema=problema,
                    precio=precio, estado=estado, tecnico=st.session_state.usuario,
                    fotos=str(fotos), firma=firma,
                )
                st.success(f"✅ Orden #{nuevo_id} creada correctamente.")
                st.balloons()
            except Exception as e:
                st.error(f"No fue posible guardar la orden: {e}")

# ==========================================================
# VER ÓRDENES
# ==========================================================

elif opcion == "📋 Ver Órdenes":
    st.subheader("📋 Órdenes")
    ordenes = obtener_ordenes()
    if not ordenes:
        st.info("No hay órdenes registradas.")
    else:
        ids = [o["id"] for o in ordenes]
        if "orden_seleccionada" not in st.session_state or st.session_state.orden_seleccionada not in ids:
            st.session_state.orden_seleccionada = ids[0]

        id_sel = st.selectbox(
            "Selecciona una orden",
            ids,
            index=ids.index(st.session_state.orden_seleccionada),
            format_func=lambda x: f"#{x} - {next((o['cliente'] for o in ordenes if o['id'] == x), '')}",
        )
        st.session_state.orden_seleccionada = id_sel
        orden = obtener_orden(id_sel)

        if orden:
            col1, col2 = st.columns([1, 2])
            with col1:
                try:
                    fotos = ast.literal_eval(orden["fotos"] or "{}")
                except Exception:
                    fotos = {}
                for nombre in ["antes", "durante", "despues"]:
                    if fotos.get(nombre):
                        st.image(mostrar_base64(fotos[nombre]), caption=nombre.capitalize(), use_container_width=True)

            with col2:
                st.markdown(f"### Orden #{orden['id']}")
                st.write("**Fecha:**", orden["fecha"])
                st.write("**Cliente:**", orden["cliente"])
                st.write("**Teléfono:**", orden["telefono"] or "")
                st.write("**Equipo:**", orden["equipo"])
                st.write("**Problema:**", orden["problema"] or "")
                st.write("**Estado:**", orden["estado"])
                st.write("**Pago:**", orden["pagado"])
                st.write("**Precio:**", f"${float(orden['precio_estimado'] or 0):,.0f}")

                if orden["firma"]:
                    st.image(mostrar_base64(orden["firma"]), caption="Firma del cliente", width=250)

                estados = ["Recibido", "En reparación", "Listo", "Entregado"]
                idx = estados.index(orden["estado"]) if orden["estado"] in estados else 0
                nuevo_estado = st.selectbox("Cambiar estado", estados, index=idx, key=f"est_{orden['id']}")

                if st.button("Actualizar estado", key=f"btn_est_{orden['id']}", use_container_width=True):
                    actualizar_estado(orden["id"], nuevo_estado)
                    st.success("Estado actualizado.")
                    st.rerun()

                numero = normalizar_whatsapp(orden["telefono"])
                if numero:
                    mensaje = urllib.parse.quote(
                        f"Hola {orden['cliente']}, tu equipo ({orden['equipo']}) está en estado: {nuevo_estado}."
                    )
                    st.link_button("📲 Enviar WhatsApp", f"https://wa.me/{numero}?text={mensaje}", use_container_width=True)

            if st.session_state.rol == "admin":
                with st.expander("✏️ Editar orden completa"):
                    with st.form(key=f"form_edit_{orden['id']}"):
                        cliente2 = st.text_input("Cliente", value=orden["cliente"])
                        telefono2 = st.text_input("Teléfono", value=orden["telefono"] or "")
                        equipo2 = st.text_input("Equipo", value=orden["equipo"])
                        problema2 = st.text_area("Problema", value=orden["problema"] or "")
                        precio2 = st.number_input("Precio estimado", value=float(orden["precio_estimado"] or 0), step=1000.0)
                        estado2 = st.selectbox("Estado", estados, index=idx, key=f"estado_edit_{orden['id']}")
                        notas2 = st.text_area("Notas", value=orden["notas"] or "")
                        opciones_pago = ["Pendiente", "Parcial", "Pagado"]
                        idx_pago = opciones_pago.index(orden["pagado"]) if orden["pagado"] in opciones_pago else 0
                        pagado2 = st.selectbox("Pago", opciones_pago, index=idx_pago)
                        confirmar = st.checkbox("Confirmo enviar esta orden a la papelera")

                        cg, ce = st.columns(2)
                        guardar = cg.form_submit_button("💾 Guardar")
                        eliminar = ce.form_submit_button("🗑️ Papelera")

                        if guardar:
                            actualizar_orden(
                                orden["id"], cliente=cliente2, telefono=telefono2, equipo=equipo2,
                                problema=problema2, precio_estimado=precio2, estado=estado2,
                                notas=notas2, pagado=pagado2,
                            )
                            st.success("Orden actualizada.")
                            st.rerun()

                        if eliminar:
                            if confirmar:
                                eliminar_orden(orden["id"], st.session_state.usuario)
                                st.success("Orden enviada a la papelera. Puedes restaurarla.")
                                st.rerun()
                            else:
                                st.error("Marca la casilla de confirmación.")

# ==========================================================
# BUSCAR
# ==========================================================

elif opcion == "🔍 Buscar":
    st.subheader("🔍 Buscar")
    texto = st.text_input("Cliente, teléfono, equipo o ID")

    if texto.strip():
        resultados = buscar_ordenes(texto, limite=100)
        st.write(f"{len(resultados)} resultado(s)")

        if resultados:
            st.dataframe([{
                "ID": o["id"],
                "Fecha": o["fecha"],
                "Cliente": o["cliente"],
                "Teléfono": o["telefono"],
                "Equipo": o["equipo"],
                "Estado": o["estado"],
                "Precio": o["precio_estimado"],
            } for o in resultados], use_container_width=True, hide_index=True)

            if len(resultados) >= 100:
                st.caption("Se muestran los primeros 100 resultados. Escribe una búsqueda más específica.")

# ==========================================================
# RECIBOS
# ==========================================================

elif opcion == "🖨️ Recibos":
    st.subheader("🖨️ Recibos")
    ordenes = obtener_ordenes()
    if not ordenes:
        st.info("No hay órdenes.")
    else:
        id_recibo = st.selectbox("Selecciona una orden", [o["id"] for o in ordenes])
        orden = obtener_orden(id_recibo)
        st.write("**Cliente:**", orden["cliente"])
        st.write("**Equipo:**", orden["equipo"])
        st.write("**Estado:**", orden["estado"])
        st.write("**Total:**", f"${float(orden['precio_estimado'] or 0):,.0f}")

        qr = crear_qr(f"ETS_{orden['id']}")
        st.image(qr, width=140)
        pdf = crear_pdf(orden)
        with open(pdf, "rb") as f:
            st.download_button(
                "📄 Descargar recibo PDF", f.read(), file_name=f"Recibo_{orden['id']}.pdf",
                mime="application/pdf", use_container_width=True,
            )

        ticket = f"""Electronic Tech Service

Orden #{orden['id']}
Fecha: {orden['fecha']}
Cliente: {orden['cliente']}
Equipo: {orden['equipo']}
Estado: {orden['estado']}
Total: ${float(orden['precio_estimado'] or 0):,.0f}

WhatsApp: 3014874740
Gracias por preferirnos.
"""
        st.download_button(
            "🧾 Descargar ticket", ticket, file_name=f"Ticket_{orden['id']}.txt",
            mime="text/plain", use_container_width=True,
        )

# ==========================================================
# COTIZACIONES
# ==========================================================

elif opcion == "📄 Cotizaciones":
    st.subheader("📄 Cotización de cámaras")
    c1, c2 = st.columns(2)
    with c1:
        cliente = st.text_input("Cliente / Empresa", key="cot_cliente")
        telefono = st.text_input("Teléfono", key="cot_tel")
        direccion = st.text_input("Dirección", key="cot_dir")
    with c2:
        fecha_cot = st.date_input("Fecha", value=datetime.now().date())
        validez = st.number_input("Validez (días)", min_value=1, value=15)
        forma_pago = st.selectbox("Forma de pago", ["Efectivo", "Transferencia", "50% anticipo - 50% entrega", "Otro"])

    c1, c2, c3 = st.columns(3)
    with c1:
        tipo = st.selectbox("Tipo de cámara", ["IP (Red)", "Analógica HD", "WiFi", "PTZ", "Otra"])
        cantidad = st.number_input("Cantidad de cámaras", min_value=1, value=4)
    with c2:
        resolucion = st.selectbox("Resolución", ["2MP", "4MP", "5MP", "8MP (4K)", "Otra"])
        audio = st.checkbox("Incluye audio")
    with c3:
        grabador = st.selectbox("Grabador", ["NVR", "DVR", "No incluye", "Otro"])
        discos = st.number_input("Almacenamiento (TB)", min_value=0, value=1, step=1)

    descripcion = st.text_area(
        "Descripción del servicio",
        value="Instalación de sistema de videovigilancia, configuración de grabación, acceso remoto por celular y capacitación básica al cliente.",
        height=110,
    )

    c1, c2 = st.columns(2)
    with c1:
        p_cam = st.number_input("Cámaras ($)", min_value=0, step=10000)
        p_grab = st.number_input("Grabador + Disco ($)", min_value=0, step=10000)
        p_cab = st.number_input("Cableado y accesorios ($)", min_value=0, step=10000)
    with c2:
        p_mo = st.number_input("Mano de obra ($)", min_value=0, step=10000)
        otros = st.number_input("Otros ($)", min_value=0, step=5000)
        descuento = st.number_input("Descuento ($)", min_value=0, step=5000)

    subtotal = p_cam + p_grab + p_cab + p_mo + otros
    total = max(subtotal - descuento, 0)
    st.metric("Total cotización", f"${total:,.0f}")

    if st.button("Generar cotización", type="primary", use_container_width=True):
        html = f"""
        <div style="background:white;color:#111;padding:28px;border-radius:14px;font-family:Arial;max-width:820px;margin:auto;">
            <div style="text-align:center;border-bottom:3px solid #00E5FF;padding-bottom:12px;">
                <h1 style="color:#05051b;">Electronic Tech Service</h1>
                <p>Montería, Córdoba • WhatsApp: 301 487 4740</p>
            </div>
            <h2 style="text-align:center;color:#05051b;">COTIZACIÓN DE CÁMARAS DE SEGURIDAD</h2>
            <p><b>Fecha:</b> {fecha_cot.strftime('%d/%m/%Y')} &nbsp; <b>Validez:</b> {validez} días</p>
            <p><b>Cliente:</b> {cliente or '________________'}</p>
            <p><b>Teléfono:</b> {telefono or '________________'}</p>
            <p><b>Dirección:</b> {direccion or '________________'}</p>
            <hr>
            <p><b>Sistema:</b> {cantidad} cámara(s) {tipo}, {resolucion}, audio: {'Sí' if audio else 'No'}, grabador: {grabador}, almacenamiento: {discos} TB.</p>
            <p>{descripcion}</p>
            <hr>
            <p>Cámaras: <b>${p_cam:,.0f}</b></p>
            <p>Grabador + Disco: <b>${p_grab:,.0f}</b></p>
            <p>Cableado y accesorios: <b>${p_cab:,.0f}</b></p>
            <p>Mano de obra: <b>${p_mo:,.0f}</b></p>
            <p>Otros: <b>${otros:,.0f}</b></p>
            <p>Descuento: <b>-${descuento:,.0f}</b></p>
            <h2 style="background:#05051b;color:white;padding:12px;">TOTAL: ${total:,.0f}</h2>
            <p><b>Forma de pago:</b> {forma_pago}</p>
        </div>
        """
        if HAS_COMPONENTS:
            components.html(html, height=950, scrolling=True)
        else:
            st.error("No está disponible el componente HTML de Streamlit para mostrar la cotización.")

# ==========================================================
# INVENTARIO
# ==========================================================

elif opcion == "📦 Inventario":
    st.subheader("📦 Inventario")
    tab1, tab2 = st.tabs(["Productos", "Agregar producto"])

    with tab1:
        productos = obtener_inventario()
        if not productos:
            st.info("No hay productos.")
        for p in productos:
            color = "🔴" if p["cantidad"] <= 5 else "🟡" if p["cantidad"] <= 10 else "🟢"
            with st.container(border=True):
                st.markdown(f"### {color} {p['producto']}")
                c1, c2 = st.columns(2)
                c1.metric("Stock", p["cantidad"])
                c2.metric("Precio", f"${float(p['precio_unitario'] or 0):,.0f}")
                nueva = st.number_input("Nueva cantidad", min_value=0, value=int(p["cantidad"]), key=f"cant_{p['id']}")
                c3, c4 = st.columns(2)
                if c3.button("Actualizar", key=f"up_{p['id']}"):
                    actualizar_producto(p["id"], cantidad=nueva)
                    st.rerun()
                if c4.button("🗑️ Papelera", key=f"del_{p['id']}"):
                    eliminar_producto(p["id"], st.session_state.usuario)
                    st.success("Producto enviado a la papelera.")
                    st.rerun()

    with tab2:
        prod = st.text_input("Producto")
        cant = st.number_input("Cantidad", min_value=1, value=1)
        precio = st.number_input("Precio unitario", min_value=0, step=1000)
        if st.button("Guardar producto", use_container_width=True):
            if prod.strip():
                crear_producto(prod, cant, precio)
                st.success("Producto agregado.")
                st.rerun()
            else:
                st.error("El nombre es obligatorio.")

# ==========================================================
# VENTAS
# ==========================================================

elif opcion == "🛒 Ventas":
    st.subheader("🛒 Ventas")
    tab1, tab2 = st.tabs(["Vender", "Historial"])

    with tab1:
        productos = obtener_inventario()
        disponibles = [p for p in productos if (p["cantidad"] or 0) > 0]
        if not disponibles:
            st.warning("No hay productos con stock.")
        else:
            opciones = {
                f"{p['producto']} • Stock: {p['cantidad']} • ${float(p['precio_unitario'] or 0):,.0f}": p
                for p in disponibles
            }
            elegido = st.selectbox("Producto", list(opciones.keys()))
            prod = opciones[elegido]
            cantidad = st.number_input("Cantidad", min_value=1, max_value=int(prod["cantidad"]), value=1)
            cliente_v = st.text_input("Cliente (opcional)")
            notas_v = st.text_input("Notas (opcional)")
            total_v = float(prod["precio_unitario"] or 0) * cantidad
            c1, c2 = st.columns(2)
            c1.metric("Precio unitario", f"${float(prod['precio_unitario'] or 0):,.0f}")
            c2.metric("Total", f"${total_v:,.0f}")

            if st.button("💰 Registrar venta", type="primary", use_container_width=True):
                try:
                    vid = crear_venta(prod["id"], cantidad, cliente_v, st.session_state.usuario, notas_v)
                    st.success(f"Venta #{vid} registrada.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        ventas = obtener_ventas()
        if not ventas:
            st.info("No hay ventas.")
        else:
            st.dataframe([{
                "ID": v["id"], "Fecha": v["fecha"], "Producto": v["producto_nombre"],
                "Cantidad": v["cantidad"], "P. Unitario": v["precio_unitario"],
                "Total": v["total"], "Cliente": v["cliente"] or "", "Vendedor": v["vendedor"] or ""
            } for v in ventas], use_container_width=True, hide_index=True)
            st.metric("Total vendido", f"${sumar_ventas():,.0f}")

            if st.session_state.rol == "admin":
                id_del = st.selectbox("Venta a enviar a papelera", [v["id"] for v in ventas])
                confirmar = st.checkbox("Confirmo enviar la venta a la papelera")
                if st.button("🗑️ Enviar venta a papelera", use_container_width=True):
                    if confirmar:
                        eliminar_venta(id_del, st.session_state.usuario)
                        st.success("Venta enviada a papelera y stock devuelto.")
                        st.rerun()
                    else:
                        st.warning("Debes confirmar.")

# ==========================================================
# GASTOS
# ==========================================================

elif opcion == "💸 Gastos":
    st.subheader("💸 Gastos")
    desc = st.text_input("Descripción")
    categoria = st.selectbox("Categoría", ["Repuestos", "Herramientas", "Servicios", "Transporte", "Otros"])
    monto = st.number_input("Monto", min_value=0, step=1000)

    if st.button("Guardar gasto", use_container_width=True):
        if desc.strip():
            crear_gasto(desc, monto, categoria)
            st.success("Gasto registrado.")
            st.rerun()
        else:
            st.error("La descripción es obligatoria.")

    gastos = obtener_gastos()
    if gastos:
        st.dataframe([{
            "ID": g["id"], "Fecha": g["fecha"], "Descripción": g["descripcion"],
            "Monto": g["monto"], "Categoría": g["categoria"]
        } for g in gastos], use_container_width=True, hide_index=True)

        id_gasto = st.selectbox("Gasto a enviar a papelera", [g["id"] for g in gastos])
        confirmar = st.checkbox("Confirmo enviar el gasto a la papelera")
        if st.button("🗑️ Enviar gasto a papelera", use_container_width=True):
            if confirmar:
                eliminar_gasto(id_gasto, st.session_state.usuario)
                st.success("Gasto enviado a la papelera.")
                st.rerun()
            else:
                st.warning("Debes confirmar.")

# ==========================================================
# CONTABILIDAD
# ==========================================================

elif opcion == "📊 Contabilidad":
    st.subheader("📊 Contabilidad")

    resumen = obtener_resumen_contabilidad()
    rep = resumen["reparaciones"]
    ven = resumen["ventas"]
    gastos = resumen["gastos"]
    ingresos = rep + ven
    utilidad = ingresos - gastos

    c1, c2 = st.columns(2)
    c1.metric("Reparaciones", f"${rep:,.0f}")
    c2.metric("Ventas", f"${ven:,.0f}")
    c3, c4 = st.columns(2)
    c3.metric("Gastos", f"${gastos:,.0f}")
    c4.metric("Utilidad", f"${utilidad:,.0f}")

    if HAS_MATPLOTLIB:
        fig, ax = plt.subplots()
        ax.bar(["Reparaciones", "Ventas"], [rep, ven])
        ax.set_ylabel("Pesos")
        st.pyplot(fig)
        plt.close(fig)

        if resumen["estados"]:
            fig2, ax2 = plt.subplots()
            ax2.bar(
                [fila["estado"] for fila in resumen["estados"]],
                [float(fila["total"] or 0) for fila in resumen["estados"]],
            )
            plt.xticks(rotation=20)
            st.pyplot(fig2)
            plt.close(fig2)
    else:
        st.info("Las gráficas están desactivadas porque falta matplotlib; los datos contables siguen disponibles.")

# ==========================================================
# CORTE MENSUAL
# ==========================================================

elif opcion == "📅 Corte Mensual":
    st.subheader("📅 Corte mensual")
    st.success("El corte mensual NO borra órdenes, ventas, gastos ni inventario.")
    periodo = st.text_input("Periodo", value=datetime.now().strftime("%Y-%m"), help="Formato: AAAA-MM")

    if re.match(r"^\d{4}-\d{2}$", periodo):
        if st.button("📊 Realizar corte", type="primary", use_container_width=True):
            resultado = crear_corte_mensual(periodo, st.session_state.usuario)
            st.success("Corte guardado sin eliminar información.")
            c1, c2 = st.columns(2)
            c1.metric("Órdenes", resultado["ordenes"])
            c2.metric("Reparaciones", f"${resultado['reparaciones']:,.0f}")
            c3, c4 = st.columns(2)
            c3.metric("Ventas", f"${resultado['ventas']:,.0f}")
            c4.metric("Gastos", f"${resultado['gastos']:,.0f}")
            st.metric("Utilidad", f"${resultado['utilidad']:,.0f}")
    else:
        st.warning("Usa formato AAAA-MM. Ejemplo: 2026-10")

    cortes = obtener_cortes_mensuales()
    if cortes:
        st.dataframe([{
            "Periodo": c["periodo"], "Fecha corte": c["fecha_cierre"],
            "Órdenes": c["total_ordenes"], "Reparaciones": c["ingresos_reparaciones"],
            "Ventas": c["ingresos_ventas"], "Gastos": c["gastos"],
            "Utilidad": c["utilidad"], "Usuario": c["usuario"]
        } for c in cortes], use_container_width=True, hide_index=True)

# ==========================================================
# PAPELERA
# ==========================================================

elif opcion == "🗑️ Papelera":
    st.subheader("🗑️ Papelera y restauración")
    st.info("Nada de esta sección se borra definitivamente. Puedes restaurar los registros.")

    tabs = st.tabs(["Órdenes", "Productos", "Ventas", "Gastos", "Usuarios"])

    with tabs[0]:
        items = obtener_ordenes_eliminadas()
        if not items:
            st.info("No hay órdenes en la papelera.")
        else:
            for o in items:
                with st.container(border=True):
                    st.write(f"**Orden #{o['id']} — {o['cliente']} — {o['equipo']}**")
                    st.caption(f"Eliminada: {o['fecha_eliminacion']} • Por: {o['eliminado_por'] or '-'}")
                    if st.button("♻️ Restaurar orden", key=f"rest_ord_{o['id']}", use_container_width=True):
                        restaurar_orden(o["id"])
                        st.success("Orden restaurada.")
                        st.rerun()

    with tabs[1]:
        items = obtener_productos_eliminados()
        if not items:
            st.info("No hay productos en la papelera.")
        else:
            for p in items:
                with st.container(border=True):
                    st.write(f"**{p['producto']}** — Stock: {p['cantidad']} — ${float(p['precio_unitario'] or 0):,.0f}")
                    st.caption(f"Eliminado: {p['fecha_eliminacion']} • Por: {p['eliminado_por'] or '-'}")
                    if st.button("♻️ Restaurar producto", key=f"rest_prod_{p['id']}", use_container_width=True):
                        restaurar_producto(p["id"])
                        st.success("Producto restaurado.")
                        st.rerun()

    with tabs[2]:
        items = obtener_ventas_eliminadas()
        if not items:
            st.info("No hay ventas en la papelera.")
        else:
            for v in items:
                with st.container(border=True):
                    st.write(f"**Venta #{v['id']} — {v['producto_nombre']} — ${float(v['total'] or 0):,.0f}**")
                    st.caption(f"Eliminada: {v['fecha_eliminacion']} • Por: {v['eliminado_por'] or '-'}")
                    if st.button("♻️ Restaurar venta", key=f"rest_venta_{v['id']}", use_container_width=True):
                        try:
                            restaurar_venta(v["id"])
                            st.success("Venta restaurada y stock descontado nuevamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    with tabs[3]:
        items = obtener_gastos_eliminados()
        if not items:
            st.info("No hay gastos en la papelera.")
        else:
            for g in items:
                with st.container(border=True):
                    st.write(f"**Gasto #{g['id']} — {g['descripcion']} — ${float(g['monto'] or 0):,.0f}**")
                    st.caption(f"Eliminado: {g['fecha_eliminacion']} • Por: {g['eliminado_por'] or '-'}")
                    if st.button("♻️ Restaurar gasto", key=f"rest_gasto_{g['id']}", use_container_width=True):
                        restaurar_gasto(g["id"])
                        st.success("Gasto restaurado.")
                        st.rerun()

    with tabs[4]:
        items = obtener_usuarios_eliminados()
        if not items:
            st.info("No hay usuarios en la papelera.")
        else:
            for u in items:
                with st.container(border=True):
                    st.write(f"**{u['usuario']} — {u['rol']}**")
                    st.caption(f"Eliminado: {u['fecha_eliminacion']} • Por: {u['eliminado_por'] or '-'}")
                    if st.button("♻️ Restaurar usuario", key=f"rest_user_{u['id']}", use_container_width=True):
                        restaurar_usuario(u["id"])
                        st.success("Usuario restaurado.")
                        st.rerun()

# ==========================================================
# USUARIOS
# ==========================================================

elif opcion == "👥 Usuarios":
    st.subheader("👥 Usuarios")
    tab1, tab2 = st.tabs(["Usuarios", "Nuevo"])

    with tab1:
        for u in obtener_usuarios():
            with st.container(border=True):
                nombre = st.text_input("Usuario", value=u["usuario"], key=f"user_{u['id']}")
                clave = st.text_input("Nueva contraseña", type="password", key=f"pass_{u['id']}", help="Déjala vacía para conservarla.")
                rol = st.selectbox("Rol", ["trabajador", "admin"], index=1 if u["rol"] == "admin" else 0, key=f"rol_{u['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Guardar", key=f"save_{u['id']}"):
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
                    if c2.button("🗑️ Papelera", key=f"deluser_{u['id']}"):
                        try:
                            eliminar_usuario(u["id"], st.session_state.usuario)
                            st.success("Usuario enviado a papelera.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    with tab2:
        usuario_nuevo = st.text_input("Nuevo usuario")
        password_nuevo = st.text_input("Contraseña", type="password")
        rol_nuevo = st.selectbox("Rol", ["trabajador", "admin"])
        if st.button("Crear usuario", use_container_width=True):
            if usuario_nuevo.strip() and password_nuevo:
                try:
                    crear_usuario(usuario_nuevo, password_nuevo, rol_nuevo)
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
    st.subheader("📤 Exportar información")

    ordenes = obtener_ordenes()
    if ordenes:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Fecha", "Cliente", "Teléfono", "Equipo", "Problema", "Precio", "Estado", "Técnico", "Notas", "Pagado"])
        for o in ordenes:
            writer.writerow([o["id"], o["fecha"], o["cliente"], o["telefono"], o["equipo"], o["problema"], o["precio_estimado"], o["estado"], o["tecnico"], o["notas"], o["pagado"]])
        st.download_button("📥 Descargar órdenes", output.getvalue().encode("utf-8-sig"), "reparaciones.csv", "text/csv", use_container_width=True)

    respaldo = {
        "fecha_respaldo": datetime.now().isoformat(),
        "ordenes": [dict(x) for x in obtener_ordenes(incluir_media=True)],
        "inventario": [dict(x) for x in obtener_inventario()],
        "ventas": [dict(x) for x in obtener_ventas()],
        "gastos": [dict(x) for x in obtener_gastos()],
        "cortes": [dict(x) for x in obtener_cortes_mensuales()],
    }
    respaldo_json = json.dumps(respaldo, ensure_ascii=False, indent=2, default=str)
    st.download_button(
        "💾 Descargar respaldo completo",
        respaldo_json.encode("utf-8"),
        file_name=f"electronic_tech_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        use_container_width=True,
    )

# ==========================================================
# SISTEMA
# ==========================================================

elif opcion == "🛡️ Sistema":
    st.subheader("🛡️ Estado del sistema")
    diagnostico = obtener_diagnostico_db()
    st.success("✅ Base de datos conectada y modo optimizado activo.")
    st.caption("Guarda una captura del ID. Si algún día cambia, la app quedó conectada a otra base.")
    st.code(diagnostico["instalacion_id"])
    st.caption("Este ID pertenece a tu base actual. Si cambia en el futuro, revisa DATABASE_URL antes de guardar datos nuevos.")

    c1, c2 = st.columns(2)
    c1.metric("Órdenes", diagnostico["ordenes"])
    c2.metric("Productos", diagnostico["productos"])
    c3, c4 = st.columns(2)
    c3.metric("Ventas", diagnostico["ventas"])
    c4.metric("Gastos", diagnostico["gastos"])
    c5, c6 = st.columns(2)
    c5.metric("Usuarios", diagnostico["usuarios"])
    c6.metric("Papelera", diagnostico["papelera"])

# ==========================================================
# TALLER
# ==========================================================

elif opcion == "📍 Taller":
    st.subheader("📍 Electronic Tech Service")
    st.write("📍 Barrio El Mundo López")
    st.write("Montería - Córdoba")
    st.write("📞 WhatsApp: 301 487 4740")
    st.link_button("🗺️ Abrir Google Maps", "https://maps.google.com", use_container_width=True)
    st.link_button("📲 Abrir WhatsApp", "https://wa.me/573014874740", use_container_width=True)
