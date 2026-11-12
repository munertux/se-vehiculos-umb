# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import RegistroBitacora

_COLUMNAS = "id_bitacora, id_empleado, entidad, id_registro, id_regla, accion, fecha, detalle"


class BitacoraDAO(BaseDAO):
    def registrar(self, entidad: str, id_registro: int, accion: str, id_empleado: int = None,
                  id_regla: int = None, detalle: str = None, tx=None) -> int:
        f = self._retornando(
            "INSERT INTO bitacora_conocimiento (id_empleado, entidad, id_registro, id_regla, accion, detalle) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_bitacora",
            (id_empleado, entidad, id_registro, id_regla, accion, detalle), tx)
        return f["id_bitacora"]

    def listar(self, limite: int = 200, entidad: str = None, tx=None) -> list:
        """Ultimos registros con nombre del empleado, usuario y codigo de regla (dict)."""
        sql = ("SELECT b.id_bitacora, b.fecha, b.entidad, b.id_registro, b.accion, b.detalle, "
               "b.id_empleado, e.nombres AS empleado, u.nombre_usuario, b.id_regla, r.codigo AS codigo_regla "
               "FROM bitacora_conocimiento b "
               "LEFT JOIN empleado e ON e.id_empleado = b.id_empleado "
               "LEFT JOIN usuario u ON u.id_usuario = e.id_usuario "
               "LEFT JOIN reglas r ON r.id_regla = b.id_regla")
        parametros = ()
        if entidad:
            sql += " WHERE b.entidad = %s"
            parametros = (entidad,)
        sql += " ORDER BY b.fecha DESC, b.id_bitacora DESC LIMIT %s"
        return self._filas(sql, parametros + (int(limite),), tx)

    def por_registro(self, entidad: str, id_registro: int, tx=None) -> list:
        return [RegistroBitacora(**f) for f in self._filas(
            f"SELECT {_COLUMNAS} FROM bitacora_conocimiento WHERE entidad = %s AND id_registro = %s "
            "ORDER BY id_bitacora", (entidad, id_registro), tx)]
