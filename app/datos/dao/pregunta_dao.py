# -*- coding: utf-8 -*-
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Pregunta

_COLUMNAS = "id_pregunta, id_area, enunciado, sintoma_evaluado, es_entrada, activa"


class PreguntaDAO(BaseDAO):
    def obtener(self, id_pregunta: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM preguntas WHERE id_pregunta = %s", (id_pregunta,), tx)
        return Pregunta(**f) if f else None

    def listar(self, id_area: int = None, tx=None) -> list:
        """Preguntas con nombre de area y numero de reglas (dict)."""
        sql = ("SELECT p.id_pregunta, p.id_area, a.nombre AS area, p.enunciado, p.sintoma_evaluado, "
               "p.es_entrada, p.activa, "
               "(SELECT COUNT(*) FROM reglas r WHERE r.id_pregunta = p.id_pregunta) AS reglas "
               "FROM preguntas p JOIN areas a ON a.id_area = p.id_area")
        parametros = ()
        if id_area is not None:
            sql += " WHERE p.id_area = %s"
            parametros = (id_area,)
        sql += " ORDER BY p.id_area, p.es_entrada DESC, p.id_pregunta"
        return self._filas(sql, parametros, tx)

    def entrada_del_area(self, id_area: int, solo_activa: bool = True, excluir_id: int = None, tx=None):
        sql = f"SELECT {_COLUMNAS} FROM preguntas WHERE id_area = %s AND es_entrada AND id_pregunta <> %s"
        if solo_activa:
            sql += " AND activa"
        f = self._fila(sql + " ORDER BY id_pregunta LIMIT 1", (id_area, excluir_id or -1), tx)
        return Pregunta(**f) if f else None

    def crear(self, datos: dict, tx=None) -> int:
        f = self._retornando(
            "INSERT INTO preguntas (id_pregunta, id_area, enunciado, sintoma_evaluado, tipo_respuesta, es_entrada, activa) "
            "SELECT COALESCE(MAX(id_pregunta), 0) + 1, %s, %s, %s, 'escala_certeza', %s, %s FROM preguntas "
            "RETURNING id_pregunta",
            (datos["id_area"], datos["enunciado"], datos["sintoma_evaluado"],
             bool(datos.get("es_entrada", False)), bool(datos.get("activa", True))), tx)
        return f["id_pregunta"]

    def actualizar(self, id_pregunta: int, datos: dict, tx=None) -> int:
        sets, valores = self._set_dinamico(datos, ("id_area", "enunciado", "sintoma_evaluado", "es_entrada"))
        if not sets:
            return 0
        return self._ejecutar(f"UPDATE preguntas SET {sets} WHERE id_pregunta = %s", valores + (id_pregunta,), tx)

    def cambiar_activa(self, id_pregunta: int, activa: bool, tx=None) -> int:
        return self._ejecutar("UPDATE preguntas SET activa = %s WHERE id_pregunta = %s", (activa, id_pregunta), tx)

    def contar(self, solo_activas: bool = False, tx=None) -> int:
        sql = "SELECT COUNT(*) FROM preguntas" + (" WHERE activa" if solo_activas else "")
        return int(self._escalar(sql, tx=tx))
