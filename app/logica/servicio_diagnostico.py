# -*- coding: utf-8 -*-
"""ServicioDiagnostico: caso de uso CU-03 "Consultar al sistema experto"
(RF03). Abre la atencion, conduce el ciclo de preguntas sucesivas y
cierra el diagnostico. Es la unica clase que la capa de presentacion
conoce de la logica de negocio para la consulta.

Se construye con una Conexion (ServicioDiagnostico(conexion)) o, por
compatibilidad, con los dos repositorios de siempre
(ServicioDiagnostico(repo_conocimiento, repo_atencion))."""
import re

from app.datos.dao.vehiculo_dao import VehiculoDAO
from app.datos.repositorio_atencion import RepositorioAtencion
from app.datos.repositorio_conocimiento import RepositorioConocimiento
from app.logica.entidades import lista_texto
from app.logica.errores import ErrorNegocio
from app.logica.memoria_trabajo import MemoriaTrabajo
from app.logica.modelos import ESCALA_CERTEZA, ETIQUETAS_RESPUESTA
from app.logica.motor_inferencia import MotorInferencia

# Memoria de trabajo en curso por atencion (equivalente al almacen D2 del DFD).
# Si se pierde (reinicio del servidor u otro worker) se reconstruye
# reproduciendo las respuestas guardadas en atencion_respuesta.
_SESIONES = {}

PATRON_OBD = re.compile(r"^[PCBU][0-9A-F]{4}$")

TESTIGOS_TABLERO = (
    "Check engine (falla del motor)",
    "Bateria o sistema de carga",
    "Presion de aceite",
    "Temperatura del refrigerante",
    "Frenos o freno de estacionamiento",
    "ABS",
    "Airbag",
    "Control de estabilidad o traccion (ESP/TCS)",
    "Presion de neumaticos (TPMS)",
    "Direccion asistida (EPS)",
    "Precalentamiento de bujias (diesel)",
    "Inmovilizador o antirrobo",
    "Nivel bajo de combustible",
)


class ServicioDiagnostico:
    def __init__(self, conexion_o_repo, repo_atencion=None):
        if repo_atencion is None:
            conexion = conexion_o_repo
            self._repo_c = RepositorioConocimiento(conexion)
            self._repo_a = RepositorioAtencion(conexion)
        else:
            self._repo_c = conexion_o_repo
            self._repo_a = repo_atencion
        self._vehiculos = VehiculoDAO(self._repo_a.conexion)
        self._motor = MotorInferencia(self._repo_c)

    # ------------------------------------------------------------ catalogos
    def areas(self):
        return self._repo_c.areas()

    @staticmethod
    def testigos_disponibles() -> list:
        return list(TESTIGOS_TABLERO)

    # --------------------------------------------------------------- ciclo
    def iniciar(self, id_area: int, id_vehiculo: int = None, testigos=None, codigos_obd=None,
                id_consultante: int = None):
        """Abre la atencion. `testigos` y `codigos_obd` pueden ser lista o
        texto separado por comas. Si se da id_consultante, el vehiculo debe
        ser suyo. Devuelve (id_atencion, pregunta)."""
        area = self._repo_c.area(int(id_area))
        if area is None:
            raise ErrorNegocio("El area seleccionada no existe.")
        if id_vehiculo:
            vehiculo = self._vehiculos.obtener(int(id_vehiculo))
            if vehiculo is None or not vehiculo.activo:
                raise ErrorNegocio("El vehiculo seleccionado no existe o esta inactivo.")
            if id_consultante is not None and vehiculo.id_consultante != int(id_consultante):
                raise ErrorNegocio("El vehiculo seleccionado no pertenece al consultante.")
            id_consultante = vehiculo.id_consultante
        testigos_txt = ", ".join(lista_texto(testigos)) or None
        obd_txt = ", ".join(self.normalizar_obd(codigos_obd)) or None

        memoria = MemoriaTrabajo(self._motor._p["puntaje_base"])
        pregunta = self._motor.iniciar(area.id_area, memoria)
        if pregunta is None:
            raise ErrorNegocio("El area no tiene una pregunta de entrada activa.")
        id_atencion = self._repo_a.abrir(area.id_area, id_vehiculo=id_vehiculo or None, testigos=testigos_txt,
                                         codigos_obd=obd_txt, id_consultante=id_consultante)
        _SESIONES[id_atencion] = {"memoria": memoria, "id_area": area.id_area, "orden": 0, "pendiente": pregunta}
        return id_atencion, self._serializar_pregunta(pregunta)

    def responder(self, id_atencion: int, id_pregunta: int, respuesta_clave: str):
        sesion = self._sesion(id_atencion)
        if respuesta_clave not in ESCALA_CERTEZA:
            raise ErrorNegocio("Respuesta no valida.")
        pregunta = self._repo_c.pregunta(id_pregunta)
        if pregunta is None:
            raise ErrorNegocio("Pregunta no valida.")

        certeza = ESCALA_CERTEZA[respuesta_clave]
        memoria = sesion["memoria"]
        self._motor.procesar_respuesta(memoria, pregunta, respuesta_clave, certeza)
        sesion["orden"] += 1
        self._repo_a.guardar_respuesta(id_atencion, id_pregunta, respuesta_clave, certeza, sesion["orden"])

        if self._motor.debe_detenerse(memoria):
            return {"estado": "finalizado", "resultado": self.finalizar(id_atencion)}

        siguiente = self._motor.siguiente_pregunta(memoria, sesion["id_area"])
        if siguiente is None:
            return {"estado": "finalizado", "resultado": self.finalizar(id_atencion)}
        sesion["pendiente"] = siguiente
        return {"estado": "en_curso", "pregunta": self._serializar_pregunta(siguiente)}

    def finalizar(self, id_atencion: int):
        """Pondera las hipotesis, guarda el diagnostico (con reglas
        activadas) y cierra la atencion. Si ya estaba cerrada, devuelve el
        diagnostico guardado."""
        atencion = self._repo_a.obtener(id_atencion)
        if atencion is None:
            raise ErrorNegocio("La atencion no existe.")
        if atencion.estado != "en_curso":
            _SESIONES.pop(id_atencion, None)
            return self.resultado_guardado(id_atencion)
        sesion = self._sesion(id_atencion)
        resultados = self._motor.hipotesis_ponderadas(sesion["memoria"])
        ids_regla = {i for hp in resultados for i in hp.reglas_activadas}
        codigos = self._repo_c.codigos_de_reglas(ids_regla)
        por_hipotesis = {
            hp.hipotesis.id_hipotesis: self._sin_repetir([codigos.get(i, str(i)) for i in hp.reglas_activadas])
            for hp in resultados
        }
        self._repo_a.guardar_diagnostico(id_atencion, resultados, por_hipotesis)
        _SESIONES.pop(id_atencion, None)
        return [self._serializar_hipotesis(hp, por_hipotesis[hp.hipotesis.id_hipotesis]) for hp in resultados]

    def confirmar_falla(self, id_atencion: int, id_hipotesis: int, observacion: str = None):
        diagnostico = self._repo_a.diagnostico(id_atencion)
        if not diagnostico:
            raise ErrorNegocio("La atencion no tiene un diagnostico finalizado.")
        if int(id_hipotesis) not in {d["id_hipotesis"] for d in diagnostico}:
            raise ErrorNegocio("La hipotesis no hace parte del diagnostico de esta atencion.")
        observacion = (observacion or "").strip()[:1000] or None
        self._repo_a.confirmar_falla(id_atencion, int(id_hipotesis), observacion)

    # ------------------------------------------------------------ consultas
    def pertenece(self, id_atencion: int, id_consultante: int) -> bool:
        """True si la atencion es del consultante (para validar en la web)."""
        duenio = self._repo_a.propietario(id_atencion)
        return duenio is not None and int(duenio) == int(id_consultante)

    def estado(self, id_atencion: int) -> dict:
        """Estado actual de la atencion; si esta en curso incluye la
        pregunta pendiente (para retomar la consulta tras recargar)."""
        atencion = self._repo_a.obtener(id_atencion)
        if atencion is None:
            raise ErrorNegocio("La atencion no existe.")
        if atencion.estado != "en_curso":
            return {"estado": "finalizado", "resultado": self.resultado_guardado(id_atencion)}
        sesion = self._sesion(id_atencion)
        return {"estado": "en_curso", "pregunta": self._serializar_pregunta(sesion.get("pendiente"))}

    def resultado_guardado(self, id_atencion: int) -> list:
        """Diagnostico persistido, con el mismo formato de finalizar()."""
        respuestas = {r["id_pregunta"]: r["respuesta"] for r in self._repo_a.respuestas(id_atencion)}
        salida = []
        for d in self._repo_a.diagnostico(id_atencion):
            mejor = self._repo_c.mejor_regla_de_hipotesis(d["id_hipotesis"])
            nivel = mejor["nivel_atencion"] if mejor else "Sin informacion"
            sintoma = any(respuestas.get(p.id_pregunta) in ("si", "probablemente_si")
                          for p in self._repo_c.preguntas_que_apuntan_a(d["id_hipotesis"]))
            salida.append({
                "id_hipotesis": d["id_hipotesis"],
                "nombre": d["nombre"],
                "descripcion": d["descripcion"],
                "puntaje": round(d["puntaje"], 4),
                "probabilidad": round(d["probabilidad"] * 100, 1),
                "posicion": d["posicion"],
                "nivel_atencion": nivel,
                "recomendacion": mejor["recomendacion"] if mejor else "",
                "sintoma_confirmado": sintoma,
                "advertencia": nivel.startswith("No debe seguir usandose"),
                "reglas_activadas": lista_texto(d["reglas_activadas"]),
                "falla_confirmada": bool(d["falla_confirmada"]),
                "observacion": d["observacion"],
            })
        return salida

    @staticmethod
    def normalizar_obd(codigos) -> list:
        """Valida codigos OBD-II (P0300, C1234, B0001, U0100)."""
        salida = []
        for c in lista_texto(codigos.replace(";", ",").replace(" ", ",") if isinstance(codigos, str) else codigos):
            c = c.upper()
            if not PATRON_OBD.match(c):
                raise ErrorNegocio(f"Codigo OBD no valido: {c}. Use el formato P0300, C1234, B0001 o U0100.")
            if c not in salida:
                salida.append(c)
        return salida

    # ------------------------------------------------------------ internos
    def _sesion(self, id_atencion: int) -> dict:
        sesion = _SESIONES.get(id_atencion)
        if sesion is None:
            sesion = self._reconstruir(id_atencion)
            if sesion is None:
                raise ErrorNegocio("La atencion no existe o ya fue cerrada.")
            _SESIONES[id_atencion] = sesion
        return sesion

    def _reconstruir(self, id_atencion: int):
        """Reproduce las respuestas guardadas para recuperar la memoria de trabajo."""
        atencion = self._repo_a.obtener(id_atencion)
        if atencion is None or atencion.estado != "en_curso":
            return None
        memoria = MemoriaTrabajo(self._motor._p["puntaje_base"])
        pendiente = self._motor.iniciar(atencion.id_area, memoria)
        respuestas = self._repo_a.respuestas(id_atencion)
        for r in respuestas:
            pregunta = self._repo_c.pregunta(r["id_pregunta"])
            self._motor.procesar_respuesta(memoria, pregunta, r["respuesta"], r["certeza"])
            # replica la seleccion (puede consumir un contraste, igual que en vivo)
            pendiente = self._motor.siguiente_pregunta(memoria, atencion.id_area)
        return {"memoria": memoria, "id_area": atencion.id_area, "orden": len(respuestas), "pendiente": pendiente}

    @staticmethod
    def _sin_repetir(lista) -> list:
        vistos = []
        for x in lista:
            if x not in vistos:
                vistos.append(x)
        return vistos

    @staticmethod
    def _serializar_pregunta(pregunta):
        if pregunta is None:
            return None
        return {
            "id_pregunta": pregunta.id_pregunta,
            "id_area": pregunta.id_area,
            "enunciado": pregunta.enunciado,
            "es_entrada": pregunta.es_entrada,
            "opciones": [{"clave": k, "etiqueta": v} for k, v in ETIQUETAS_RESPUESTA.items()],
        }

    @staticmethod
    def _serializar_hipotesis(hp, codigos=None):
        return {
            "id_hipotesis": hp.hipotesis.id_hipotesis,
            "nombre": hp.hipotesis.nombre,
            "descripcion": hp.hipotesis.descripcion,
            "puntaje": round(hp.puntaje, 4),
            "probabilidad": round(hp.probabilidad * 100, 1),
            "posicion": hp.posicion,
            "nivel_atencion": hp.nivel_atencion,
            "recomendacion": hp.recomendacion,
            "sintoma_confirmado": hp.sintoma_confirmado,
            "advertencia": hp.nivel_atencion.startswith("No debe seguir usandose"),
            "reglas_activadas": list(codigos or []),
        }
