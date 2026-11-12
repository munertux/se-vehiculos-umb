# -*- coding: utf-8 -*-
"""ServicioHistorial: historial de consultas del consultante y detalle de
una atencion (base del reporte imprimible)."""
from app.datos.dao.area_dao import AreaDAO
from app.datos.dao.atencion_dao import AtencionDAO
from app.datos.dao.regla_dao import ReglaDAO
from app.datos.dao.vehiculo_dao import VehiculoDAO
from app.datos.repositorio_conocimiento import RepositorioConocimiento
from app.logica.entidades import ETIQUETAS_COMBUSTIBLE, ETIQUETAS_TRANSMISION, a_dict, lista_texto
from app.logica.errores import ErrorNegocio
from app.logica.modelos import ETIQUETAS_RESPUESTA

ETIQUETAS_ESTADO = {"en_curso": "En curso", "finalizada": "Finalizada"}


class ServicioHistorial:
    def __init__(self, conexion):
        self._atenciones = AtencionDAO(conexion)
        self._vehiculos = VehiculoDAO(conexion)
        self._areas = AreaDAO(conexion)
        self._reglas = ReglaDAO(conexion)
        self._repo_c = RepositorioConocimiento(conexion)

    def historial(self, id_consultante: int) -> list:
        salida = []
        for f in self._atenciones.historial_por_consultante(id_consultante):
            vehiculo = f"{f['placa']} - {f['marca']} {f['modelo']}" if f["id_vehiculo"] else "Sin vehiculo"
            salida.append({
                "id_atencion": f["id_atencion"],
                "fecha": f["fecha_inicio"],
                "fecha_fin": f["fecha_fin"],
                "id_vehiculo": f["id_vehiculo"],
                "vehiculo": vehiculo,
                "placa": f["placa"],
                "id_area": f["id_area"],
                "area": f["area"],
                "estado": f["estado"],
                "estado_etiqueta": ETIQUETAS_ESTADO.get(f["estado"], f["estado"]),
                "id_hipotesis": f["id_hipotesis"],
                "hipotesis_principal": f["hipotesis"],
                "probabilidad": round(float(f["probabilidad"]) * 100, 1) if f["probabilidad"] is not None else None,
                "falla_confirmada": bool(f["falla_confirmada"]),
            })
        return salida

    def detalle(self, id_consultante: int, id_atencion: int) -> dict:
        atencion = self._atenciones.obtener(id_atencion)
        duenio = self._atenciones.propietario(id_atencion) if atencion else None
        if atencion is None or duenio is None or int(duenio) != int(id_consultante):
            raise ErrorNegocio("La consulta no existe o no pertenece al consultante.")
        return self._armar_detalle(atencion)

    def detalle_sin_restriccion(self, id_atencion: int) -> dict:
        """Igual que detalle() pero sin validar el consultante (uso de ingeniero/administrador)."""
        atencion = self._atenciones.obtener(id_atencion)
        if atencion is None:
            raise ErrorNegocio("La consulta no existe.")
        return self._armar_detalle(atencion)

    # ------------------------------------------------------------ internos
    def _armar_detalle(self, atencion) -> dict:
        vehiculo = None
        if atencion.id_vehiculo:
            v = self._vehiculos.obtener(atencion.id_vehiculo)
            if v:
                vehiculo = a_dict(v)
                vehiculo["descripcion"] = v.descripcion
                vehiculo["combustible_etiqueta"] = ETIQUETAS_COMBUSTIBLE.get(v.combustible, v.combustible)
                vehiculo["transmision_etiqueta"] = ETIQUETAS_TRANSMISION.get(v.transmision, v.transmision)
        area = self._areas.obtener(atencion.id_area)

        respuestas = []
        for r in self._atenciones.respuestas(atencion.id_atencion):
            respuestas.append({
                "orden": r["orden"],
                "id_pregunta": r["id_pregunta"],
                "enunciado": r["enunciado"],
                "es_entrada": r["es_entrada"],
                "respuesta": r["respuesta"],
                "respuesta_etiqueta": ETIQUETAS_RESPUESTA.get(r["respuesta"], r["respuesta"]),
                "certeza": r["certeza"],
            })
        afirmadas = {r["id_pregunta"] for r in respuestas if r["respuesta"] in ("si", "probablemente_si")}

        hipotesis = []
        for d in self._atenciones.diagnostico(atencion.id_atencion)[:5]:
            mejor = self._repo_c.mejor_regla_de_hipotesis(d["id_hipotesis"])
            nivel = mejor["nivel_atencion"] if mejor else "Sin informacion"
            sintoma = any(p.id_pregunta in afirmadas for p in self._repo_c.preguntas_que_apuntan_a(d["id_hipotesis"]))
            hipotesis.append({
                "posicion": d["posicion"],
                "id_hipotesis": d["id_hipotesis"],
                "nombre": d["nombre"],
                "descripcion": d["descripcion"],
                "puntaje": round(d["puntaje"], 4),
                "probabilidad": round(d["probabilidad"] * 100, 1),
                "nivel_atencion": nivel,
                "recomendacion": mejor["recomendacion"] if mejor else "",
                "advertencia": nivel.startswith("No debe seguir usandose"),
                "sintoma_confirmado": sintoma,
                "reglas_activadas": lista_texto(d["reglas_activadas"]),
                "falla_confirmada": bool(d["falla_confirmada"]),
                "observacion": d["observacion"],
            })

        reglas = []
        for h in hipotesis:
            for codigo in h["reglas_activadas"]:
                if codigo not in {r["codigo"] for r in reglas}:
                    regla = self._reglas.obtener_por_codigo(codigo)
                    reglas.append({"codigo": codigo, "id_hipotesis": h["id_hipotesis"],
                                   "hipotesis": h["nombre"],
                                   "version": regla.version if regla else None,
                                   "nivel_atencion": regla.nivel_atencion if regla else None})

        confirmada = next((h for h in hipotesis if h["falla_confirmada"]), None)
        principal = hipotesis[0] if hipotesis else None
        return {
            "id_atencion": atencion.id_atencion,
            "fecha_inicio": atencion.fecha_inicio,
            "fecha_fin": atencion.fecha_fin,
            "estado": atencion.estado,
            "estado_etiqueta": ETIQUETAS_ESTADO.get(atencion.estado, atencion.estado),
            "vehiculo": vehiculo,
            "id_area": atencion.id_area,
            "area": area.nombre if area else "",
            "testigos": lista_texto(atencion.testigos_tablero),
            "codigos_obd": lista_texto(atencion.codigos_obd),
            "respuestas": respuestas,
            "hipotesis": hipotesis,
            "recomendacion": principal["recomendacion"] if principal else "",
            "nivel_atencion": principal["nivel_atencion"] if principal else "",
            "advertencia": principal["advertencia"] if principal else False,
            "reglas": reglas,
            "falla_confirmada": confirmada,
        }
