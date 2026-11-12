# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Empleado

_COLUMNAS = "id_empleado, id_usuario, nombres, cargo"


class EmpleadoDAO(BaseDAO):
    def obtener(self, id_empleado: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM empleado WHERE id_empleado = %s", (id_empleado,), tx)
        return Empleado(**f) if f else None

    def obtener_por_usuario(self, id_usuario: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM empleado WHERE id_usuario = %s", (id_usuario,), tx)
        return Empleado(**f) if f else None

    def listar(self, tx=None) -> list:
        return [Empleado(**f) for f in self._filas(f"SELECT {_COLUMNAS} FROM empleado ORDER BY nombres", tx=tx)]

    def crear(self, id_usuario: int, nombres: str, cargo=None, tx=None) -> int:
        f = self._retornando(
            "INSERT INTO empleado (id_usuario, nombres, cargo) VALUES (%s, %s, %s) RETURNING id_empleado",
            (id_usuario, nombres, cargo), tx)
        return f["id_empleado"]

    def actualizar(self, id_empleado: int, datos: dict, tx=None) -> int:
        sets, valores = self._set_dinamico(datos, ("nombres", "cargo"))
        if not sets:
            return 0
        return self._ejecutar(f"UPDATE empleado SET {sets} WHERE id_empleado = %s", valores + (id_empleado,), tx)
