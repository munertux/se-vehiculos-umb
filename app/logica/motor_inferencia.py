# -*- coding: utf-8 -*-
"""MotorInferencia: propaga evidencia, selecciona la siguiente pregunta,
contrasta ramas no examinadas y pondera las hipotesis lideres. Replica el
algoritmo descrito en "Estrategia de Inferencia" y "Diseno del Sistema de
Inferencia" del manual tecnico (paginas 43-51), sin contener ninguna
pregunta, regla o relacion sintoma-falla escrita en el codigo: todo se
consulta al RepositorioConocimiento (RNF-07).
"""
from app.logica.modelos import certeza_a_evidencia, HipotesisPonderada


class MotorInferencia:
    def __init__(self, repo_conocimiento):
        self._repo = repo_conocimiento
        self._p = repo_conocimiento.parametros()

    # ---------------------------------------------------------- iniciar
    def iniciar(self, id_area: int, memoria):
        for id_h in self._repo.ids_hipotesis_activas(id_area):
            memoria.activar_hipotesis(id_h)
        return self._repo.pregunta_de_entrada_del_area(id_area)

    # ------------------------------------------------------- propagar
    def procesar_respuesta(self, memoria, pregunta, respuesta_clave: str, certeza: float):
        memoria.registrar_respuesta(pregunta.id_pregunta, respuesta_clave)
        evidencia = certeza_a_evidencia(certeza)
        if pregunta.es_entrada:
            granulos = self._repo.granulos_del_area(pregunta.id_area, self._p["peso_entrada"])
        else:
            granulos = self._repo.granulos_de_pregunta(pregunta.id_pregunta)
        for granulo in granulos:
            memoria.aplicar_evidencia(granulo, evidencia, pregunta.id_area)
        return granulos

    # ------------------------------------------------------- seleccionar
    def siguiente_pregunta(self, memoria, id_area_inicial: int):
        """Escoge la hipotesis con mas evidencia y formula la primera
        pregunta especifica que apunte a ella y no haya sido respondida.
        Si no hay, intenta con la siguiente hipotesis del ranking. Si
        ninguna hipotesis activa tiene preguntas pendientes, se evalua
        contraste con otra area (ver _pregunta_de_contraste)."""
        for id_h, _puntaje in memoria.ranking():
            for pregunta in self._repo.preguntas_que_apuntan_a(id_h):
                if not memoria.fue_respondida(pregunta.id_pregunta):
                    return pregunta
        return self._pregunta_de_contraste(memoria, id_area_inicial)

    def _pregunta_de_contraste(self, memoria, id_area_inicial: int):
        if memoria.contrastes_usados >= self._p["max_contrastes"]:
            return None
        if len(memoria.preguntas_respondidas) < 3:
            return None
        id_area_dom, proporcion = memoria.area_dominante()
        if proporcion < self._p["umbral_dominancia"]:
            return None
        areas_ya_exploradas = {
            self._repo.pregunta(pid).id_area for pid in memoria.preguntas_respondidas
        }
        candidatas = self._repo.riesgo_por_area(areas_ya_exploradas)
        for id_area in candidatas:
            pregunta = self._repo.pregunta_de_entrada_del_area(id_area)
            if pregunta and not memoria.fue_respondida(pregunta.id_pregunta):
                memoria.contrastes_usados += 1
                for id_h in self._repo.ids_hipotesis_activas(id_area):
                    memoria.activar_hipotesis(id_h)
                return pregunta
        return None

    # -------------------------------------------------------- evaluar parada
    def debe_detenerse(self, memoria) -> bool:
        if len(memoria.preguntas_respondidas) >= self._p["max_preguntas"]:
            return True
        ranking = memoria.ranking()
        if not ranking:
            return False
        id_lider, puntaje_lider = ranking[0]
        total = sum(p for _, p in ranking) or 1e-9
        probabilidad_lider = puntaje_lider / total
        if probabilidad_lider < self._p["umbral_confianza"]:
            return False
        # el sintoma especifico de la hipotesis lider debe haber sido afirmado
        for pregunta in self._repo.preguntas_que_apuntan_a(id_lider):
            respuesta = memoria.respuestas.get(pregunta.id_pregunta)
            if respuesta in ("si", "probablemente_si"):
                return True
        return False

    # -------------------------------------------------------- ponderar
    def hipotesis_ponderadas(self, memoria):
        n = int(self._p["num_hipotesis"])
        ranking = memoria.ranking()

        def clave_orden(item):
            id_h, puntaje = item
            mejor = self._repo.mejor_regla_de_hipotesis(id_h)
            gravedad = mejor["gravedad"] if mejor else 0
            return (-puntaje, -gravedad)

        ranking = sorted(ranking, key=clave_orden)[:n]
        total = sum(p for _, p in ranking) or 1e-9

        resultado = []
        for posicion, (id_h, puntaje) in enumerate(ranking, start=1):
            hip = self._repo.hipotesis(id_h)
            mejor = self._repo.mejor_regla_de_hipotesis(id_h)
            sintoma_confirmado = False
            for pregunta in self._repo.preguntas_que_apuntan_a(id_h):
                if memoria.respuestas.get(pregunta.id_pregunta) in ("si", "probablemente_si"):
                    sintoma_confirmado = True
                    break
            resultado.append(
                HipotesisPonderada(
                    hipotesis=hip,
                    puntaje=puntaje,
                    probabilidad=puntaje / total,
                    posicion=posicion,
                    id_area=0,
                    nivel_atencion=mejor["nivel_atencion"] if mejor else "Sin informacion",
                    recomendacion=mejor["recomendacion"] if mejor else "",
                    sintoma_confirmado=sintoma_confirmado,
                    reglas_activadas=memoria.traza.get(id_h, []),
                )
            )
        return resultado
