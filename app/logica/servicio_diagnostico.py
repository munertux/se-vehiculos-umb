# -*- coding: utf-8 -*-
"""ServicioDiagnostico: caso de uso CU-03 "Consultar al sistema experto"
(RF03). Abre la atencion, conduce el ciclo de preguntas sucesivas y
cierra el diagnostico. Es la unica clase que la capa de presentacion
conoce de la logica de negocio."""
from app.logica.memoria_trabajo import MemoriaTrabajo
from app.logica.motor_inferencia import MotorInferencia
from app.logica.modelos import ESCALA_CERTEZA, ETIQUETAS_RESPUESTA

# Memoria de trabajo en curso por atencion (equivalente al almacen D2 del DFD).
_SESIONES = {}


class ServicioDiagnostico:
    def __init__(self, repo_conocimiento, repo_atencion):
        self._repo_c = repo_conocimiento
        self._repo_a = repo_atencion
        self._motor = MotorInferencia(repo_conocimiento)

    def areas(self):
        return self._repo_c.areas()

    def iniciar(self, id_area: int):
        memoria = MemoriaTrabajo(self._motor._p["puntaje_base"])
        pregunta = self._motor.iniciar(id_area, memoria)
        id_atencion = self._repo_a.abrir(id_area)
        _SESIONES[id_atencion] = {"memoria": memoria, "id_area": id_area, "orden": 0}
        return id_atencion, self._serializar_pregunta(pregunta)

    def responder(self, id_atencion: int, id_pregunta: int, respuesta_clave: str):
        sesion = _SESIONES.get(id_atencion)
        if sesion is None:
            raise ValueError("La atencion no existe o ya fue cerrada.")
        if respuesta_clave not in ESCALA_CERTEZA:
            raise ValueError("Respuesta no valida.")
        pregunta = self._repo_c.pregunta(id_pregunta)
        if pregunta is None:
            raise ValueError("Pregunta no valida.")

        certeza = ESCALA_CERTEZA[respuesta_clave]
        memoria = sesion["memoria"]
        self._motor.procesar_respuesta(memoria, pregunta, respuesta_clave, certeza)
        sesion["orden"] += 1
        self._repo_a.guardar_respuesta(id_atencion, id_pregunta, respuesta_clave, certeza, sesion["orden"])

        if self._motor.debe_detenerse(memoria):
            resultado = self.finalizar(id_atencion)
            return {"estado": "finalizado", "resultado": resultado}

        siguiente = self._motor.siguiente_pregunta(memoria, sesion["id_area"])
        if siguiente is None:
            resultado = self.finalizar(id_atencion)
            return {"estado": "finalizado", "resultado": resultado}

        return {"estado": "en_curso", "pregunta": self._serializar_pregunta(siguiente)}

    def finalizar(self, id_atencion: int):
        sesion = _SESIONES.get(id_atencion)
        if sesion is None:
            raise ValueError("La atencion no existe o ya fue cerrada.")
        memoria = sesion["memoria"]
        resultados = self._motor.hipotesis_ponderadas(memoria)
        self._repo_a.guardar_diagnostico(id_atencion, resultados)
        return [self._serializar_hipotesis(hp) for hp in resultados]

    def confirmar_falla(self, id_atencion: int, id_hipotesis: int):
        self._repo_a.confirmar_falla(id_atencion, id_hipotesis)

    # ------------------------------------------------------------ helpers
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
    def _serializar_hipotesis(hp):
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
        }
