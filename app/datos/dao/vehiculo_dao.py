# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Vehiculo

_COLUMNAS = ("id_vehiculo, id_consultante, placa, marca, modelo, combustible, transmision, "
             "anio, kilometraje, activo, creado")
_EDITABLES = ("placa", "marca", "modelo", "combustible", "transmision", "anio", "kilometraje")


class VehiculoDAO(BaseDAO):
    def obtener(self, id_vehiculo: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM vehiculo WHERE id_vehiculo = %s", (id_vehiculo,), tx)
        return Vehiculo(**f) if f else None

    def listar_por_consultante(self, id_consultante: int, incluir_inactivos: bool = False, tx=None) -> list:
        sql = f"SELECT {_COLUMNAS} FROM vehiculo WHERE id_consultante = %s"
        if not incluir_inactivos:
            sql += " AND activo = TRUE"
        sql += " ORDER BY activo DESC, placa"
        return [Vehiculo(**f) for f in self._filas(sql, (id_consultante,), tx)]

    def buscar_placa_activa(self, placa: str, excluir_id: int = None, tx=None):
        f = self._fila(
            f"SELECT {_COLUMNAS} FROM vehiculo WHERE upper(placa) = upper(%s) AND activo = TRUE "
            "AND id_vehiculo <> %s LIMIT 1", (placa, excluir_id or -1), tx)
        return Vehiculo(**f) if f else None

    def crear(self, id_consultante: int, datos: dict, tx=None) -> int:
        f = self._retornando(
            "INSERT INTO vehiculo (id_consultante, placa, marca, modelo, combustible, transmision, anio, kilometraje) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_vehiculo",
            (id_consultante, datos["placa"], datos["marca"], datos["modelo"], datos["combustible"],
             datos["transmision"], datos.get("anio"), datos.get("kilometraje")), tx)
        return f["id_vehiculo"]

    def actualizar(self, id_vehiculo: int, datos: dict, tx=None) -> int:
        sets, valores = self._set_dinamico(datos, _EDITABLES)
        if not sets:
            return 0
        return self._ejecutar(f"UPDATE vehiculo SET {sets} WHERE id_vehiculo = %s", valores + (id_vehiculo,), tx)

    def cambiar_activo(self, id_vehiculo: int, activo: bool, tx=None) -> int:
        return self._ejecutar("UPDATE vehiculo SET activo = %s WHERE id_vehiculo = %s", (activo, id_vehiculo), tx)
