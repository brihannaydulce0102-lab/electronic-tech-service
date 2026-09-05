import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import datetime
import hashlib

DATABASE_URL = os.environ.get("DATABASE_URL")

def hash_password(texto: str) -> str:
    return hashlib.sha256(str(texto).encode()).hexdigest()

@contextmanager
def get_connection():
    if not DATABASE_URL:
        raise Exception("No se encontró DATABASE_URL. Configúrala en Secrets de Streamlit.")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
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

        # Crear usuario admin por defecto si no existe
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
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(precio_estimado), 0) as total FROM ordenes")
        return cur.fetchone()["total"]

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
            (usuario,