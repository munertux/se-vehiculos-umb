# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Hipotesis


class HipotesisDAO(BaseDAO):
    def obtener(self, id_hipotesis: int, tx=None):
        f = self._fila("SELECT id_hipotesis, nombre, descripcion FROM hipotesis WHERE id_hipotesis = %s",
                       (id_hipotesis,), tx)
        return Hipotesis(**f) if f else None

    def listar(self, tx=None) -> list:
        """Hipotesis con su area (la de su primera regla) y conteo de reglas (dict)."""
        return self._filas(
            "SELECT h.id_hipotesis, h.nombre, h.descripcion, "
            "(SELECT COUNT(*) FROM reglas r WHERE r.id_hipotesis = h.id_hipotesis) AS reglas, "
            "(SELECT COUNT(*) FROM reglas r WHERE r.id_hipotesis = h.id_hipotesis AND r.activa) AS reglas_activas, "
            "(SELECT r.id_area FROM reglas r WHERE r.id_hipotesis = h.id_hipotesis ORDER BY r.id_regla LIMIT 1) AS id_area, "
            "(SELECT a.nombre FROM reglas r JOIN areas a ON a.id_area = r.id_area "
            "  WHERE r.id_hipotesis = h.id_hipotesis ORDER BY r.id_regla LIMIT 1) AS area "
            "FROM hipotesis h ORDER BY h.id_hipotesis", tx=tx)

    def existe_nombre(self, nombre: str, excluir_id: int = None, tx=None) -> bool:
        return self._fila("SELECT 1 FROM hipotesis WHERE lower(nombre) = lower(%s) AND id_hipotesis <> %s",
                          (nombre, excluir_id or -1), tx) is not None

    def crear(self, nombre: str, descripcion: str = "", tx=None) -> int:
        f = self._retornando(
            "INSERT INTO hipotesis (id_hipotesis, nombre, descripcion) "
            "SELECT COALESCE(MAX(id_hipotesis), 0) + 1, %s, %s FROM hipotesis RETURNING id_hipotesis",
            (nombre, descripcion), tx)
        return f["id_hipotesis"]

    def actualizar(self, id_hipotesis: int, datos: dict, tx=None) -> int:
        sets, valores = self._set_dinamico(datos, ("nombre", "descripcion"))
        if not sets:
            return 0
        return self._ejecutar(f"UPDATE hipotesis SET {sets} WHERE id_hipotesis = %s", valores + (id_hipotesis,), tx)

    def sin_regla_activa(self, tx=None) -> list:
        return [Hipotesis(**f) for f in self._filas(
            "SELECT h.id_hipotesis, h.nombre, h.descripcion FROM hipotesis h WHERE NOT EXISTS ("
            " SELECT 1 FROM reglas r WHERE r.id_hipotesis = h.id_hipotesis AND r.activa) "
            "ORDER BY h.id_hipotesis", tx=tx)]

    def areas_de(self, id_hipotesis: int, tx=None) -> list:
        """Ids de area de las reglas activas de la hipotesis."""
        return [f["id_area"] for f in self._filas(
            "SELECT DISTINCT id_area FROM reglas WHERE id_hipotesis = %s AND activa ORDER BY id_area",
            (id_hipotesis,), tx)]

    def contar(self, tx=None) -> int:
        return int(self._escalar("SELECT COUNT(*) FROM hipotesis", tx=tx))
