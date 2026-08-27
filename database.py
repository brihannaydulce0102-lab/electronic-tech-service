import sqlite3
from contextlib import contextmanager
from datetime import datetime
import hashlib

DB = "database.db"

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def conectar():
    return sqlite3.connect(DB, check_same_thread=False)

def hash_password(texto: str) -> str:
    return hashlib.sha256(str(texto).encode()).hexdigest()

def crear_tablas():
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'trabajador'
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ordenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            cantidad INTEGER DEFAULT 0,
            precio_unitario REAL DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            descripcion TEXT,
            monto REAL DEFAULT 0,
            categoria TEXT
        )
        """)

        # Crear admin por defecto si no existe
        admin = cur.execute("SELECT 1 FROM usuarios WHERE LOWER(usuario) = 'admin'").fetchone()
        if not admin:
            cur.execute(
                "INSERT INTO usuarios (usuario, password, rol) VALUES (?, ?, ?)",
                ("admin", hash_password("123456"), "admin")
            )

# ==================== ÓRDENES ====================
def obtener_ordenes():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM ordenes ORDER BY id DESC").fetchall()

def obtener_orden(id_orden):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM ordenes WHERE id = ?", (id_orden,)).fetchone()

def crear_orden(cliente, telefono, equipo, problema, precio, estado, tecnico, fotos="{}", firma=""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ordenes
            (fecha, cliente, telefono, equipo, problema, precio_estimado, estado, tecnico, fotos, firma)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            cliente, telefono, equipo, problema, float(precio), estado, tecnico, fotos, firma
        ))
        return cur.lastrowid

def actualizar_orden(id_orden, **campos):
    if not campos:
        return
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [id_orden]
    with get_connection() as conn:
        conn.execute(f"UPDATE ordenes SET {sets} WHERE id = ?", valores)

def actualizar_estado(id_orden, nuevo_estado):
    actualizar_orden(id_orden, estado=nuevo_estado)

def eliminar_orden(id_orden):
    with get_connection() as conn:
        conn.execute("DELETE FROM ordenes WHERE id = ?", (id_orden,))

def contar_ordenes():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM ordenes").fetchone()[0]

def sumar_ingresos():
    with get_connection() as conn:
        r = conn.execute("SELECT COALESCE(SUM(precio_estimado), 0) FROM ordenes").fetchone()
        return r[0] if r else 0

def contar_por_estado(estado):
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM ordenes WHERE estado = ?", (estado,)).fetchone()[0]

def contar_pendientes():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM ordenes WHERE estado != 'Entregado'").fetchone()[0]

# ==================== USUARIOS ====================
def obtener_usuarios():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM usuarios ORDER BY id").fetchall()

def obtener_usuario_por_nombre(usuario):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM usuarios WHERE LOWER(usuario) = LOWER(?)", (usuario,)
        ).fetchone()

def crear_usuario(usuario, password, rol="trabajador"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO usuarios (usuario, password, rol) VALUES (?, ?, ?)",
            (usuario, hash_password(password), rol)
        )

def actualizar_usuario(id_usuario, **campos):
    if not campos:
        return
    if "password" in campos and campos["password"]:
        campos["password"] = hash_password(campos["password"])
    else:
        campos.pop("password", None)
    if not campos:
        return
    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [id_usuario]
    with get_connection() as conn:
        conn.execute(f"UPDATE usuarios SET {sets} WHERE id = ?", valores)

def eliminar_usuario(id_usuario):
    with get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,))

# ==================== INVENTARIO ====================
def obtener_inventario():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM inventario ORDER BY producto").fetchall()

def crear_producto(producto, cantidad, precio_unitario):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO inventario (producto, cantidad, precio_unitario) VALUES (?, ?, ?)",
            (producto, int(cantidad), float(precio_unitario))
        )

def actualizar_producto(id_producto, cantidad=None, precio_unitario=None):
    with get_connection() as conn:
        if cantidad is not None:
            conn.execute("UPDATE inventario SET cantidad = ? WHERE id = ?", (int(cantidad), id_producto))
        if precio_unitario is not None:
            conn.execute("UPDATE inventario SET precio_unitario = ? WHERE id = ?", (float(precio_unitario), id_producto))

def eliminar_producto(id_producto):
    with get_connection() as conn:
        conn.execute("DELETE FROM inventario WHERE id = ?", (id_producto,))

# ==================== GASTOS ====================
def obtener_gastos():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM gastos ORDER BY fecha DESC, id DESC").fetchall()

def crear_gasto(descripcion, monto, categoria):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO gastos (fecha, descripcion, monto, categoria) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d"), descripcion, float(monto), categoria)
        )

def sumar_gastos():
    with get_connection() as conn:
        r = conn.execute("SELECT COALESCE(SUM(monto), 0) FROM gastos").fetchone()
        return r[0] if r else 0

def eliminar_gasto(id_gasto):
    with get_connection() as conn:
        conn.execute("DELETE FROM gastos WHERE id = ?", (id_gasto,))

# Crear tablas al importar el módulo
crear_tablas()

# ===== REPARAR CONTRASEÑAS (ejecutar solo una vez) =====
def reparar_contraseñas():
    with get_connection() as conn:
        cur = conn.cursor()
        usuarios = cur.execute("SELECT id, usuario FROM usuarios").fetchall()
        
        for u in usuarios:
            # Contraseña nueva = el mismo nombre de usuario
            # Ejemplo: si el usuario se llama "juan", la contraseña queda "juan"
            nueva_clave = hash_password(u["usuario"])
            cur.execute(
                "UPDATE usuarios SET password = ? WHERE id = ?",
                (nueva_clave, u["id"])
            )
        
        print("✅ Contraseñas reparadas correctamente")

# Quita el comentario de la siguiente línea, guarda, ejecuta la app una vez,
# y luego vuelve a comentarla.
reparar_contraseñas()