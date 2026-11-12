# -*- coding: utf-8 -*-
"""AtencionDAO: base transaccional de las consultas (atencion, respuestas
y diagnostico). RNF-11: cada diagnostico guarda las reglas activadas."""
from app.datos.dao.base_dao import BaseDAO
from app.logica.entidades import Atencion

_COLUMNAS = ("id_atencion, id_area, fecha_inicio, fecha_fin, estado, id_vehiculo, id_consultante, "
             "testigos_tablero, codigos_obd")


class AtencionDAO(BaseDAO):
    # ----------------------------------------------------------- atencion
    def abrir(self, id_area: int, id_vehiculo: int = None, testigos: str = None, codigos_obd: str = None,
              id_consultante: int = None, tx=None) -> int:
        f = self._retornando(
            "INSERT INTO atencion (id_area, estado, id_vehiculo, id_consultante, testigos_tablero, codigos_obd) "
            "VALUES (%s, 'en_curso', %s, %s, %s, %s) RETURNING id_atencion",
            (id_area, id_vehiculo, id_consultante, testigos, codigos_obd), tx)
        return f["id_atencion"]

    def obtener(self, id_atencion: int, tx=None):
        f = self._fila(f"SELECT {_COLUMNAS} FROM atencion WHERE id_atencion = %s", (id_atencion,), tx)
        return Atencion(**f) if f else None

    def propietario(self, id_atencion: int, tx=None):
        """id_consultante duenio de la atencion (directo o por el vehiculo)."""
        return self._escalar(
            "SELECT COALESCE(a.id_consultante, v.id_consultante) FROM atencion a "
            "LEFT JOIN vehiculo v ON v.id_vehiculo = a.id_vehiculo WHERE a.id_atencion = %s",
            (id_atencion,), tx)

    def cerrar(self, id_atencion: int, tx=None) -> int:
        return self._ejecutar("UPDATE atencion SET estado = 'finalizada', fecha_fin = now() WHERE id_atencion = %s",
                              (id_atencion,), tx)

    def historial_por_consultante(self, id_consultante: int, tx=None) -> list:
        """Atenciones del consultante con vehiculo, area e hipotesis principal (dict)."""
        return self._filas(
            "SELECT a.id_atencion, a.fecha_inicio, a.fecha_fin, a.estado, a.id_area, ar.nombre AS area, "
            "a.id_vehiculo, v.placa, v.marca, v.modelo, "
            "d.id_hipotesis, h.nombre AS hipotesis, d.probabilidad, d.falla_confirmada "
            "FROM atencion a JOIN areas ar ON ar.id_area = a.id_area "
            "LEFT JOIN vehiculo v ON v.id_vehiculo = a.id_vehiculo "
            "LEFT JOIN atencion_diagnostico d ON d.id_atencion = a.id_atencion AND d.posicion = 1 "
            "LEFT JOIN hipotesis h ON h.id_hipotesis = d.id_hipotesis "
            "WHERE COALESCE(a.id_consultante, v.id_consultante) = %s "
            "ORDER BY a.fecha_inicio DESC, a.id_atencion DESC", (id_consultante,), tx)

    def contar(self, tx=None) -> int:
        return int(self._escalar("SELECT COUNT(*) FROM atencion", tx=tx))

    # ---------------------------------------------------------- respuestas
    def guardar_respuesta(self, id_atencion: int, id_pregunta: int, respuesta: str, certeza: float, orden: int,
                          tx=None) -> int:
        return self._ejecutar(
            "INSERT INTO atencion_respuesta (id_atencion, id_pregunta, respuesta, certeza, orden) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id_atencion, id_pregunta) DO UPDATE SET respuesta = EXCLUDED.respuesta, "
            "certeza = EXCLUDED.certeza", (id_atencion, id_pregunta, respuesta, certeza, orden), tx)

    def respuestas(self, id_atencion: int, tx=None) -> list:
        filas = self._filas(
            "SELECT r.orden, r.id_pregunta, p.enunciado, p.es_entrada, p.id_area, r.respuesta, r.certeza "
            "FROM atencion_respuesta r JOIN preguntas p ON p.id_pregunta = r.id_pregunta "
            "WHERE r.id_atencion = %s ORDER BY r.orden", (id_atencion,), tx)
        for f in filas:
            f["certeza"] = float(f["certeza"])
        return filas

    # --------------------------------------------------------- diagnostico
    def guardar_diagnostico(self, id_atencion: int, resultados, codigos_por_hipotesis: dict = None, tx=None):
        """Reemplaza el diagnostico de la atencion y la cierra. `resultados`
        son HipotesisPonderada; `codigos_por_hipotesis` = {id_h: ['R01', ...]}."""
        codigos_por_hipotesis = codigos_por_hipotesis or {}
        if tx is None:
            with self._db.transaccion() as cur:
                return self.guardar_diagnostico(id_atencion, resultados, codigos_por_hipotesis, cur)
        self._ejecutar("DELETE FROM atencion_diagnostico WHERE id_atencion = %s", (id_atencion,), tx)
        for hp in resultados:
            codigos = codigos_por_hipotesis.get(hp.hipotesis.id_hipotesis) or []
            self._ejecutar(
                "INSERT INTO atencion_diagnostico (id_atencion, id_hipotesis, puntaje, probabilidad, posicion, "
                "reglas_activadas) VALUES (%s, %s, %s, %s, %s, %s)",
                (id_atencion, hp.hipotesis.id_hipotesis, hp.puntaje, hp.probabilidad, hp.posicion,
                 ",".join(codigos) or None), tx)
        self.cerrar(id_atencion, tx)

    def diagnostico(self, id_atencion: int, tx=None) -> list:
        filas = self._filas(
            "SELECT d.posicion, d.id_hipotesis, h.nombre, h.descripcion, d.puntaje, d.probabilidad, "
            "d.falla_confirmada, d.reglas_activadas, d.observacion "
            "FROM atencion_diagnostico d JOIN hipotesis h ON h.id_hipotesis = d.id_hipotesis "
            "WHERE d.id_atencion = %s ORDER BY d.posicion", (id_atencion,), tx)
        for f in filas:
            f["puntaje"] = float(f["puntaje"])
            f["probabilidad"] = float(f["probabilidad"])
        return filas

    def confirmar_falla(self, id_atencion: int, id_hipotesis: int, observacion: str = None, tx=None) -> int:
        """Marca una sola hipotesis como la falla confirmada de la atencion."""
        if tx is None:
            with self._db.transaccion() as cur:
                return self.confirmar_falla(id_atencion, id_hipotesis, observacion, cur)
        self._ejecutar("UPDATE atencion_diagnostico SET falla_confirmada = FALSE "
                       "WHERE id_atencion = %s AND id_hipotesis <> %s", (id_atencion, id_hipotesis), tx)
        return self._ejecutar(
            "UPDATE atencion_diagnostico SET falla_confirmada = TRUE, observacion = %s "
            "WHERE id_atencion = %s AND id_hipotesis = %s", (observacion, id_atencion, id_hipotesis), tx)

    def eliminar(self, id_atencion: int, tx=None) -> int:
        """Borra una atencion y sus detalles (limpieza de pruebas)."""
        return self._ejecutar("DELETE FROM atencion WHERE id_atencion = %s", (id_atencion,), tx)
