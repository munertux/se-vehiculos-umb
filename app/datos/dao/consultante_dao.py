# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Consultante

_COLUMNAS = "id_consultante, id_usuario, nombres, correo, telefono"


class ConsultanteDAO(BaseDAO):
    def obtener(self, id_consultante: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM consultante WHERE id_consultante = %s", (id_consultante,), tx)
        return Consultante(**f) if f else None

    def obtener_por_usuario(self, id_usuario: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM consultante WHERE id_usuario = %s", (id_usuario,), tx)
        return Consultante(**f) if f else None

    def listar(self, tx=None) -> list:
        return [Consultante(**f) for f in self._filas(f"SELECT {_COLUMNAS} FROM consultante ORDER BY nombres", tx=tx)]

    def crear(self, id_usuario: int, nombres: str, correo=None, telefono=None, tx=None) -> int:
        f = self._retornando(
            "INSERT INTO consultante (id_usuario, nombres, correo, telefono) VALUES (%s, %s, %s, %s) "
            "RETURNING id_consultante", (id_usuario, nombres, correo, telefono), tx)
        return f["id_consultante"]

    def actualizar(self, id_consultante: int, datos: dict, tx=None) -> int:
        sets, valores = self._set_dinamico(datos, ("nombres", "correo", "telefono"))
        if not sets:
            return 0
        return self._ejecutar(f"UPDATE consultante SET {sets} WHERE id_consultante = %s",
                              valores + (id_consultante,), tx)
