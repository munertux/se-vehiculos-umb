# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Area


class AreaDAO(BaseDAO):
    def obtener(self, id_area: int, tx=None):
        f = self._fila("SELECT id_area, nombre, descripcion FROM areas WHERE id_area = %s", (id_area,), tx)
        return Area(**f) if f else None

    def listar(self, tx=None) -> list:
        return [Area(**f) for f in self._filas("SELECT id_area, nombre, descripcion FROM areas ORDER BY id_area", tx=tx)]

    def listar_con_conteos(self, tx=None) -> list:
        """Areas con numero de preguntas, reglas y si tienen pregunta de entrada activa (dict)."""
        return self._filas(
            "SELECT a.id_area, a.nombre, a.descripcion, "
            "(SELECT COUNT(*) FROM preguntas p WHERE p.id_area = a.id_area) AS preguntas, "
            "(SELECT COUNT(*) FROM preguntas p WHERE p.id_area = a.id_area AND p.activa) AS preguntas_activas, "
            "(SELECT COUNT(*) FROM reglas r WHERE r.id_area = a.id_area) AS reglas, "
            "(SELECT COUNT(*) FROM reglas r WHERE r.id_area = a.id_area AND r.activa) AS reglas_activas, "
            "EXISTS (SELECT 1 FROM preguntas p WHERE p.id_area = a.id_area AND p.es_entrada AND p.activa) "
            "  AS tiene_entrada "
            "FROM areas a ORDER BY a.id_area", tx=tx)

    def existe_nombre(self, nombre: str, excluir_id: int = None, tx=None) -> bool:
        return self._fila("SELECT 1 FROM areas WHERE lower(nombre) = lower(%s) AND id_area <> %s",
                          (nombre, excluir_id or -1), tx) is not None

    def crear(self, nombre: str, descripcion: str = "", tx=None) -> int:
        f = self._retornando(
            "INSERT INTO areas (id_area, nombre, descripcion) "
            "SELECT COALESCE(MAX(id_area), 0) + 1, %s, %s FROM areas RETURNING id_area",
            (nombre, descripcion), tx)
        return f["id_area"]

    def actualizar(self, id_area: int, datos: dict, tx=None) -> int:
        sets, valores = self._set_dinamico(datos, ("nombre", "descripcion"))
        if not sets:
            return 0
        return self._ejecutar(f"UPDATE areas SET {sets} WHERE id_area = %s", valores + (id_area,), tx)

    def sin_pregunta_de_entrada(self, tx=None) -> list:
        return [Area(**f) for f in self._filas(
            "SELECT a.id_area, a.nombre, a.descripcion FROM areas a WHERE NOT EXISTS ("
            " SELECT 1 FROM preguntas p WHERE p.id_area = a.id_area AND p.es_entrada AND p.activa) "
            "ORDER BY a.id_area", tx=tx)]

    def contar(self, tx=None) -> int:
        return int(self._escalar("SELECT COUNT(*) FROM areas", tx=tx))
