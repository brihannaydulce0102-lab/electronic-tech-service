import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import datetime
import hashlib

def _get_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            if "DATABASE_URL" in st.secrets:
                url = st.secrets["DATABASE_URL"]
        except Exception:
            pass
    if url:
        # Quita espacios y saltos de línea (útil en celular)
        url = str(url).strip().replace("\n", "").replace("\r", "").replace(" ", "")
    return url

DATABASE_URL = _get_database_url()

def hash_password(texto: str) -> str:
    return hashlib.sha256(str(texto).encode()).hexdigest()

@contextmanager
def get_connection():
    if not DATABASE_URL:
        raise Exception(
            "No se encontró DATABASE_URL. Configúrala en Secrets de Streamlit Cloud "
            "o como variable de entorno."
        )
    # Compatible con Neon, Supabase, Railway, etc.
    url = DATABASE_URL
    if "sslmode" not in url and url.startswith("postgres"):
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
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
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'trabajador'
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
            firma TEXT DEFAULT ''
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id SERIAL PRIMARY KEY,
            producto TEXT NOT NULL,
            cantidad INTEGER DEFAULT 0,
            precio_unitario REAL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id SERIAL PRIMARY KEY,
            fecha TEXT NOT NULL,
            descripcion TEXT,
            monto REAL DEFAULT 0,
            categoria TEXT
        )
        """)

        # NUEVA TABLA: Ventas de productos
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
            notas TEXT DEFAULT ''
        )
        """)

        # Usuario admin por defecto
        cur.execute("SELECT 1 FROM usuarios WHERE LOWER(usuario) = 'admin'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
                ("admin", hash_password("123456"), "admin")
            )

# ==================== ÓRDENES ====================
def obtener_ordenes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ordenes ORDER BY id DESC")
        return cur.fetchall()

def obtener_orden(id_orden):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ordenes WHERE id = %s", (id_orden,))
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
            cliente, telefono, equipo, problema, float(precio), estado, tecnico, fotos, firma
        ))
        return cur.fetchone()["id"]

def actualizar_orden(id_orden, **campos):
    if not campos:
        return
    sets = ", ".join([f"{k} = %s" for k in campos])
    valores = list(campos.values()) + [id_orden]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE ordenes SET {sets} WHERE id = %s", valores)

def actualizar_estado(id_orden, nuevo_estado):
    actualizar_orden(id_orden, estado=nuevo_estado)

def eliminar_orden(id_orden):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ordenes WHERE id = %s", (id_orden,))

def contar_ordenes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM ordenes")
        return cur.fetchone()["total"]

def sumar_ingresos():
    """Suma ingresos de reparaciones (órdenes)"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(precio_estimado), 0) as total FROM ordenes")
        return float(cur.fetchone()["total"] or 0)

def contar_por_estado(estado):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM ordenes WHERE estado = %s", (estado,))
        return cur.fetchone()["total"]

def contar_pendientes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM ordenes WHERE estado != 'Entregado'")
        return cur.fetchone()["total"]

# ==================== USUARIOS ====================
def obtener_usuarios():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios ORDER BY id")
        return cur.fetchall()

def obtener_usuario_por_nombre(usuario):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(%s)", (usuario,))
        return cur.fetchone()

def crear_usuario(usuario, password, rol="trabajador"):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
            (usuario, hash_password(password), rol)
        )

def actualizar_usuario(id_usuario, **campos):
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
        cur.execute(f"UPDATE usuarios SET {sets} WHERE id = %s", valores)

def eliminar_usuario(id_usuario):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE id = %s", (id_usuario,))

# ==================== INVENTARIO ====================
def obtener_inventario():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventario ORDER BY id")
        return cur.fetchall()

def obtener_producto(id_producto):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventario WHERE id = %s", (id_producto,))
        return cur.fetchone()

def crear_producto(producto, cantidad, precio_unitario):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO inventario (producto, cantidad, precio_unitario) VALUES (%s, %s, %s)",
            (producto, int(cantidad), float(precio_unitario))
        )

def actualizar_producto(id_producto, **campos):
    if not campos:
        return
    sets = ", ".join([f"{k} = %s" for k in campos])
    valores = list(campos.values()) + [id_producto]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE inventario SET {sets} WHERE id = %s", valores)

def eliminar_producto(id_producto):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM inventario WHERE id = %s", (id_producto,))

# ==================== VENTAS DE PRODUCTOS ====================
def crear_venta(producto_id, cantidad, cliente="", vendedor="", notas=""):
    """
    Registra una venta, descuenta del inventario y devuelve el id de la venta.
    Lanza ValueError si no hay stock suficiente.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventario WHERE id = %s FOR UPDATE", (producto_id,))
        prod = cur.fetchone()
        if not prod:
            raise ValueError("Producto no encontrado")
        if prod["cantidad"] < cantidad:
            raise ValueError(
                f"Stock insuficiente. Disponible: {prod['cantidad']}, solicitado: {cantidad}"
            )
        precio_unit = float(prod["precio_unitario"] or 0)
        total = precio_unit * cantidad
        # Descontar inventario
        cur.execute(
            "UPDATE inventario SET cantidad = cantidad - %s WHERE id = %s",
            (int(cantidad), producto_id)
        )
        # Registrar venta
        cur.execute("""
            INSERT INTO ventas
            (fecha, producto_id, producto_nombre, cantidad, precio_unitario, total, cliente, vendedor, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            producto_id,
            prod["producto"],
            int(cantidad),
            precio_unit,
            total,
            cliente or "",
            vendedor or "",
            notas or ""
        ))
        return cur.fetchone()["id"]

def obtener_ventas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas ORDER BY id DESC")
        return cur.fetchall()

def obtener_venta(id_venta):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas WHERE id = %s", (id_venta,))
        return cur.fetchone()

def eliminar_venta(id_venta):
    """
    Elimina una venta y devuelve el stock al inventario (si el producto aún existe).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ventas WHERE id = %s", (id_venta,))
        venta = cur.fetchone()
        if not venta:
            return
        if venta["producto_id"]:
            cur.execute(
                "UPDATE inventario SET cantidad = cantidad + %s WHERE id = %s",
                (venta["cantidad"], venta["producto_id"])
            )
        cur.execute("DELETE FROM ventas WHERE id = %s", (id_venta,))

def sumar_ventas():
    """Suma el total de todas las ventas de productos"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(total), 0) as total FROM ventas")
        return float(cur.fetchone()["total"] or 0)

def contar_ventas():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM ventas")
        return cur.fetchone()["total"]

# ==================== GASTOS ====================
def obtener_gastos():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM gastos ORDER BY id DESC")
        return cur.fetchall()

def crear_gasto(descripcion, monto, categoria):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO gastos (fecha, descripcion, monto, categoria) VALUES (%s, %s, %s, %s)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), descripcion, float(monto), categoria)
        )

def sumar_gastos():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(monto), 0) as total FROM gastos")
        return float(cur.fetchone()["total"] or 0)

def eliminar_gasto(id_gasto):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM gastos WHERE id = %s", (id_gasto,))
