import os
import re
import uuid
import hashlib
import psycopg2

from contextlib import contextmanager
from datetime import datetime
from psycopg2.extras import RealDictCursor


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

    conn = psycopg2.connect(
        url,
        cursor_factory=RealDictCursor,
        connect_timeout=15,
        application_name="electronic-tech-service",
    )

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

        cur.execute("SELECT 1 FROM usuarios WHERE LOWER(usuario) = 'admin'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
                ("admin", hash_password("123456"), "admin"),
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

def obtener_ordenes():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ordenes WHERE eliminado = FALSE ORDER BY id DESC")
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
        cur.execute("SELECT * FROM ordenes WHERE eliminado = TRUE ORDER BY fecha_eliminacion DESC, id DESC")
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
