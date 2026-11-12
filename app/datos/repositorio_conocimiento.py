# -*- coding: utf-8 -*-
"""RepositorioConocimiento: consultas granulares a la base de conocimiento
(Tabla 20 del manual). El motor de inferencia nunca ejecuta SQL directo;
siempre pasa por aqui, y esta clase nunca conoce reglas de negocio."""
from app.logica.modelos import Area, Pregunta, Hipotesis, Granulo


class RepositorioConocimiento:
    def __init__(self, conexion):
        self._db = conexion

    def parametros(self) -> dict:
        filas = self._db.consultar("SELECT clave, valor FROM parametros_inferencia")
        return {f["clave"]: float(f["valor"]) for f in filas}

    def areas(self):
        filas = self._db.consultar("SELECT id_area, nombre, descripcion FROM areas ORDER BY id_area")
        return [Area(**f) for f in filas]

    def ids_hipotesis_activas(self, id_area: int):
        filas = self._db.consultar(
            "SELECT DISTINCT id_hipotesis FROM reglas WHERE id_area = %s AND activa = TRUE",
            (id_area,),
        )
        return [f["id_hipotesis"] for f in filas]

    def pregunta_de_entrada_del_area(self, id_area: int):
        fila = self._db.consultar(
            "SELECT id_pregunta, id_area, enunciado, sintoma_evaluado, es_entrada "
            "FROM preguntas WHERE id_area = %s AND es_entrada = TRUE AND activa = TRUE LIMIT 1",
            (id_area,),
        )
        return Pregunta(**fila[0]) if fila else None

    def pregunta(self, id_pregunta: int):
        fila = self._db.consultar(
            "SELECT id_pregunta, id_area, enunciado, sintoma_evaluado, es_entrada "
            "FROM preguntas WHERE id_pregunta = %s",
            (id_pregunta,),
        )
        return Pregunta(**fila[0]) if fila else None

    def granulos_del_area(self, id_area: int, peso_entrada: float):
        """Granulo de rama: reparte peso_entrada entre todas las hipotesis
        del area (pagina 43-44 del manual)."""
        filas = self._db.consultar(
            "SELECT DISTINCT id_hipotesis FROM reglas WHERE id_area = %s AND activa = TRUE",
            (id_area,),
        )
        return [Granulo(id_hipotesis=f["id_hipotesis"], peso=peso_entrada) for f in filas]

    def granulos_de_pregunta(self, id_pregunta: int):
        """Granulo directo: las reglas de la pregunta respondida, con su
        hipotesis y su peso (1.0 por defecto)."""
        filas = self._db.consultar(
            "SELECT id_regla, id_hipotesis, peso, nivel_atencion, gravedad, recomendacion "
            "FROM reglas WHERE id_pregunta = %s AND activa = TRUE",
            (id_pregunta,),
        )
        return [
            Granulo(
                id_hipotesis=f["id_hipotesis"],
                peso=float(f["peso"]),
                id_regla=f["id_regla"],
                nivel_atencion=f["nivel_atencion"],
                gravedad=f["gravedad"],
                recomendacion=f["recomendacion"],
            )
            for f in filas
        ]

    def preguntas_que_apuntan_a(self, id_hipotesis: int):
        filas = self._db.consultar(
            "SELECT p.id_pregunta, p.id_area, p.enunciado, p.sintoma_evaluado, p.es_entrada "
            "FROM preguntas p JOIN reglas r ON r.id_pregunta = p.id_pregunta "
            "WHERE r.id_hipotesis = %s AND r.activa = TRUE AND p.activa = TRUE",
            (id_hipotesis,),
        )
        return [Pregunta(**f) for f in filas]

    def riesgo_por_area(self, ids_area_excluidas):
        excluidas = tuple(ids_area_excluidas) or (-1,)
        filas = self._db.consultar(
            "SELECT id_area, MAX(gravedad) AS gravedad_max FROM reglas "
            "WHERE activa = TRUE AND id_area NOT IN %s "
            "GROUP BY id_area ORDER BY gravedad_max DESC",
            (excluidas,),
        )
        return [f["id_area"] for f in filas]

    def hipotesis(self, id_hipotesis: int):
        fila = self._db.consultar(
            "SELECT id_hipotesis, nombre, descripcion FROM hipotesis WHERE id_hipotesis = %s",
            (id_hipotesis,),
        )
        return Hipotesis(**fila[0]) if fila else None

    def regla_de(self, id_pregunta: int, id_hipotesis: int):
        filas = self._db.consultar(
            "SELECT codigo, nivel_atencion, gravedad, recomendacion FROM reglas "
            "WHERE id_pregunta = %s AND id_hipotesis = %s AND activa = TRUE LIMIT 1",
            (id_pregunta, id_hipotesis),
        )
        return filas[0] if filas else None

    def mejor_regla_de_hipotesis(self, id_hipotesis: int):
        """Nivel de atencion y recomendacion de mayor gravedad entre las
        reglas que sustentan la hipotesis (para el resultado final)."""
        filas = self._db.consultar(
            "SELECT codigo, nivel_atencion, gravedad, recomendacion FROM reglas "
            "WHERE id_hipotesis = %s AND activa = TRUE ORDER BY gravedad DESC LIMIT 1",
            (id_hipotesis,),
        )
        return filas[0] if filas else None

    def conteos(self):
        filas = self._db.consultar(
            "SELECT 'Areas' AS conocimiento, COUNT(*) AS cantidad FROM areas "
            "UNION ALL SELECT 'Preguntas', COUNT(*) FROM preguntas "
            "UNION ALL SELECT 'Hipotesis', COUNT(*) FROM hipotesis "
            "UNION ALL SELECT 'Reglas', COUNT(*) FROM reglas"
        )
        return filas
