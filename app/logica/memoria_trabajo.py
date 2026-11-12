# -*- coding: utf-8 -*-
"""Memoria de trabajo de la atencion en curso (logica/memoria_trabajo.py).
Guarda los puntajes acumulados por hipotesis, la traza de reglas activadas
y las respuestas ya registradas, tal como lo describe el Diagrama de Caja
Negra (Figura 20) y el Diagrama de Flujo de Datos nivel 1 (Figura 22).
"""


class MemoriaTrabajo:
    def __init__(self, puntaje_base: float):
        self._puntaje_base = puntaje_base
        self.puntajes = {}          # id_hipotesis -> puntaje acumulado
        self.traza = {}             # id_hipotesis -> lista de codigos de regla activados
        self.respuestas = {}        # id_pregunta -> respuesta (texto)
        self.preguntas_respondidas = []   # orden de preguntas respondidas
        self.evidencia_por_area = {}      # id_area -> suma de |evidencia| acumulada
        self.contrastes_usados = 0

    def activar_hipotesis(self, id_hipotesis: int):
        if id_hipotesis not in self.puntajes:
            self.puntajes[id_hipotesis] = self._puntaje_base
            self.traza[id_hipotesis] = []

    def registrar_respuesta(self, id_pregunta: int, respuesta: str):
        self.respuestas[id_pregunta] = respuesta
        self.preguntas_respondidas.append(id_pregunta)

    def fue_respondida(self, id_pregunta: int) -> bool:
        return id_pregunta in self.respuestas

    def aplicar_evidencia(self, granulo, evidencia: float, id_area: int):
        """puntaje(h) <- max(0, puntaje(h) + peso(g) * e)  (formula pagina 44)."""
        self.activar_hipotesis(granulo.id_hipotesis)
        incremento = granulo.peso * evidencia
        nuevo = self.puntajes[granulo.id_hipotesis] + incremento
        self.puntajes[granulo.id_hipotesis] = max(0.0, nuevo)
        if granulo.id_regla is not None and incremento > 0:
            self.traza[granulo.id_hipotesis].append(granulo.id_regla)
        self.evidencia_por_area[id_area] = self.evidencia_por_area.get(id_area, 0.0) + abs(incremento)

    def ranking(self):
        """Lista (id_hipotesis, puntaje) ordenada de mayor a menor puntaje."""
        return sorted(self.puntajes.items(), key=lambda kv: kv[1], reverse=True)

    def total_evidencia(self) -> float:
        return sum(self.evidencia_por_area.values()) or 1e-9

    def area_dominante(self):
        """Area que concentra la mayor proporcion de evidencia y esa proporcion."""
        if not self.evidencia_por_area:
            return None, 0.0
        id_area, valor = max(self.evidencia_por_area.items(), key=lambda kv: kv[1])
        return id_area, valor / self.total_evidencia()
