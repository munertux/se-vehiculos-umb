# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Rol


class RolDAO(BaseDAO):
    def listar(self, tx=None) -> list:
        return [Rol(**f) for f in self._filas("SELECT id_rol, nombre FROM rol ORDER BY id_rol", tx=tx)]

    def obtener(self, id_rol: int, tx=None):
        f = self._fila("SELECT id_rol, nombre FROM rol WHERE id_rol = %s", (id_rol,), tx)
        return Rol(**f) if f else None
