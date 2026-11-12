# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Usuario

_COLUMNAS = ("id_usuario, id_rol, nombre_usuario, contrasena_hash, estado, intentos_fallidos, "
             "bloqueado_hasta, ultimo_acceso, creado, "
             "(bloqueado_hasta IS NOT NULL AND bloqueado_hasta > now()) AS bloqueo_vigente, "
             "GREATEST(0, CEIL(EXTRACT(EPOCH FROM (bloqueado_hasta - now())) / 60))::int AS minutos_restantes")


class UsuarioDAO(BaseDAO):
    def obtener(self, id_usuario: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM usuario WHERE id_usuario = %s", (id_usuario,), tx)
        return Usuario(**f) if f else None

    def obtener_por_nombre(self, nombre_usuario: str, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM usuario WHERE lower(nombre_usuario) = lower(%s)",
                       (nombre_usuario,), tx)
        return Usuario(**f) if f else None

    def existe_nombre(self, nombre_usuario: str, tx=None) -> bool:
        return self.obtener_por_nombre(nombre_usuario, tx) is not None

    def listar_detallado(self, tx=None) -> list:
        """Usuarios con rol y nombres (de consultante o empleado), como dict."""
        return self._filas(
            "SELECT u.id_usuario, u.nombre_usuario, u.id_rol, r.nombre AS rol_nombre, u.estado, "
            "u.intentos_fallidos, u.bloqueado_hasta, u.ultimo_acceso, u.creado, "
            "(u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > now()) AS bloqueo_vigente, "
            "COALESCE(c.nombres, e.nombres) AS nombres, c.id_consultante, e.id_empleado, "
            "c.correo, c.telefono, e.cargo "
            "FROM usuario u JOIN rol r ON r.id_rol = u.id_rol "
            "LEFT JOIN consultante c ON c.id_usuario = u.id_usuario "
            "LEFT JOIN empleado e ON e.id_usuario = u.id_usuario "
            "ORDER BY u.id_usuario", tx=tx)

    def crear(self, id_rol: int, nombre_usuario: str, contrasena_hash: str, estado: str = "activo", tx=None) -> int:
        f = self._retornando(
            "INSERT INTO usuario (id_rol, nombre_usuario, contrasena_hash, estado) "
            "VALUES (%s, %s, %s, %s) RETURNING id_usuario",
            (id_rol, nombre_usuario, contrasena_hash, estado), tx)
        return f["id_usuario"]

    def cambiar_hash(self, id_usuario: int, contrasena_hash: str, tx=None) -> int:
        return self._ejecutar("UPDATE usuario SET contrasena_hash = %s WHERE id_usuario = %s",
                              (contrasena_hash, id_usuario), tx)

    def cambiar_rol(self, id_usuario: int, id_rol: int, tx=None) -> int:
        return self._ejecutar("UPDATE usuario SET id_rol = %s WHERE id_usuario = %s", (id_rol, id_usuario), tx)

    def cambiar_estado(self, id_usuario: int, estado: str, tx=None) -> int:
        """Cambia el estado y limpia el bloqueo temporal y los intentos."""
        return self._ejecutar(
            "UPDATE usuario SET estado = %s, intentos_fallidos = 0, bloqueado_hasta = NULL "
            "WHERE id_usuario = %s", (estado, id_usuario), tx)

    def registrar_intento_fallido(self, id_usuario: int, max_intentos: int, minutos_bloqueo: int, tx=None) -> dict:
        """Suma un intento; al llegar a max_intentos bloquea por minutos_bloqueo.
        Devuelve {intentos_fallidos, estado, bloqueado_hasta}."""
        return self._retornando(
            "UPDATE usuario SET intentos_fallidos = intentos_fallidos + 1, "
            "estado = CASE WHEN intentos_fallidos + 1 >= %s THEN 'bloqueado' ELSE estado END, "
            "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= %s "
            "  THEN now() + make_interval(mins => %s) ELSE bloqueado_hasta END "
            "WHERE id_usuario = %s RETURNING intentos_fallidos, estado, bloqueado_hasta",
            (max_intentos, max_intentos, minutos_bloqueo, id_usuario), tx)

    def registrar_acceso(self, id_usuario: int, tx=None) -> int:
        return self._ejecutar(
            "UPDATE usuario SET ultimo_acceso = now(), intentos_fallidos = 0, bloqueado_hasta = NULL "
            "WHERE id_usuario = %s", (id_usuario,), tx)

    def liberar_bloqueo_vencido(self, id_usuario: int, tx=None) -> int:
        """Si el bloqueo temporal ya vencio, deja el usuario activo."""
        return self._ejecutar(
            "UPDATE usuario SET estado = 'activo', intentos_fallidos = 0, bloqueado_hasta = NULL "
            "WHERE id_usuario = %s AND estado = 'bloqueado' "
            "AND bloqueado_hasta IS NOT NULL AND bloqueado_hasta <= now()", (id_usuario,), tx)

    def fijar_bloqueo_hasta(self, id_usuario: int, minutos: int, tx=None) -> int:
        """Bloqueo temporal desde ahora (minutos negativos = ya vencido; util en pruebas)."""
        return self._ejecutar(
            "UPDATE usuario SET estado = 'bloqueado', bloqueado_hasta = now() + make_interval(mins => %s) "
            "WHERE id_usuario = %s", (minutos, id_usuario), tx)

    def eliminar(self, id_usuario: int, tx=None) -> int:
        """Borra perfil y usuario (limpieza de pruebas; falla si tiene historial)."""
        self._ejecutar("DELETE FROM consultante WHERE id_usuario = %s", (id_usuario,), tx)
        self._ejecutar("DELETE FROM empleado WHERE id_usuario = %s", (id_usuario,), tx)
        return self._ejecutar("DELETE FROM usuario WHERE id_usuario = %s", (id_usuario,), tx)
