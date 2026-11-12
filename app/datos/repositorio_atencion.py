# -*- coding: utf-8 -*-
"""RepositorioAtencion: persistencia de la base transaccional (RNF-11:
cada diagnostico guarda el 100% de las reglas activadas y su version)."""


class RepositorioAtencion:
    def __init__(self, conexion):
        self._db = conexion

    def abrir(self, id_area: int) -> int:
        fila = self._db.ejecutar_retornando(
            "INSERT INTO atencion (id_area, estado) VALUES (%s, 'en_curso') RETURNING id_atencion",
            (id_area,),
        )
        return fila["id_atencion"]

    def guardar_respuesta(self, id_atencion: int, id_pregunta: int, respuesta: str, certeza: float, orden: int):
        self._db.ejecutar(
            "INSERT INTO atencion_respuesta (id_atencion, id_pregunta, respuesta, certeza, orden) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id_atencion, id_pregunta) DO UPDATE SET respuesta = EXCLUDED.respuesta, certeza = EXCLUDED.certeza",
            (id_atencion, id_pregunta, respuesta, certeza, orden),
        )

    def guardar_diagnostico(self, id_atencion: int, resultados):
        for hp in resultados:
            self._db.ejecutar(
                "INSERT INTO atencion_diagnostico (id_atencion, id_hipotesis, puntaje, probabilidad, posicion) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (id_atencion, id_hipotesis) DO UPDATE SET puntaje = EXCLUDED.puntaje, "
                "probabilidad = EXCLUDED.probabilidad, posicion = EXCLUDED.posicion",
                (id_atencion, hp.hipotesis.id_hipotesis, hp.puntaje, hp.probabilidad, hp.posicion),
            )
        self._db.ejecutar(
            "UPDATE atencion SET estado = 'finalizada', fecha_fin = now() WHERE id_atencion = %s",
            (id_atencion,),
        )

    def confirmar_falla(self, id_atencion: int, id_hipotesis: int):
        self._db.ejecutar(
            "UPDATE atencion_diagnostico SET falla_confirmada = TRUE "
            "WHERE id_atencion = %s AND id_hipotesis = %s",
            (id_atencion, id_hipotesis),
        )
