# -*- coding: utf-8 -*-
"""Pruebas del motor de inferencia sobre las 68 reglas reales (esquema
aislado se_pruebas_motor en PostgreSQL)."""
import pytest

from apoyo_bd import conexion_motor  # noqa: F401 (fixture)
from app.datos.repositorio_conocimiento import RepositorioConocimiento
from app.logica.memoria_trabajo import MemoriaTrabajo
from app.logica.modelos import ESCALA_CERTEZA, certeza_a_evidencia
from app.logica.motor_inferencia import MotorInferencia


@pytest.fixture(scope="module")
def repo(conexion_motor):
    return RepositorioConocimiento(conexion_motor)


@pytest.fixture(scope="module")
def reglas(conexion_motor):
    return conexion_motor.consultar(
        "SELECT r.id_regla, r.codigo, r.id_pregunta, r.id_hipotesis, r.id_area, r.peso "
        "FROM reglas r WHERE r.activa ORDER BY r.id_regla")


def recorrer(repo, id_area, decidir, limite=40):
    """Atencion completa. decidir(pregunta) -> clave de respuesta."""
    motor = MotorInferencia(repo)
    memoria = MemoriaTrabajo(motor._p["puntaje_base"])
    pregunta = motor.iniciar(id_area, memoria)
    formuladas = []
    while pregunta is not None and len(formuladas) < limite:
        formuladas.append(pregunta)
        clave = decidir(pregunta)
        motor.procesar_respuesta(memoria, pregunta, clave, ESCALA_CERTEZA[clave])
        if motor.debe_detenerse(memoria):
            break
        pregunta = motor.siguiente_pregunta(memoria, id_area)
    return motor, memoria, formuladas


def test_base_de_conocimiento_completa(repo):
    conteos = {f["conocimiento"]: f["cantidad"] for f in repo.conteos()}
    assert conteos == {"Areas": 24, "Preguntas": 92, "Hipotesis": 68, "Reglas": 68}


def test_parametros_de_inferencia(repo):
    p = repo.parametros()
    assert p["peso_entrada"] == 0.4 and p["puntaje_base"] == 0.1
    assert p["num_hipotesis"] == 5 and p["max_preguntas"] == 15


def test_escala_de_certeza_y_evidencia():
    assert certeza_a_evidencia(ESCALA_CERTEZA["si"]) == 1
    assert certeza_a_evidencia(ESCALA_CERTEZA["no_se"]) == 0
    assert certeza_a_evidencia(ESCALA_CERTEZA["no"]) == -1


def test_cada_area_tiene_pregunta_de_entrada(repo):
    for area in repo.areas():
        entrada = repo.pregunta_de_entrada_del_area(area.id_area)
        assert entrada is not None and entrada.es_entrada, area.nombre


def test_cada_una_de_las_68_reglas_lleva_su_hipotesis_al_primer_lugar(repo, reglas):
    """Para cada regla: se afirma la entrada del area y el sintoma de la
    regla, y se niega todo lo demas. La hipotesis de la regla debe quedar
    en la posicion 1 con la regla en su traza."""
    assert len(reglas) == 68
    fallas = []
    for r in reglas:
        def decidir(p, r=r):
            return "si" if p.es_entrada and p.id_area == r["id_area"] or p.id_pregunta == r["id_pregunta"] else "no"

        motor, memoria, formuladas = recorrer(repo, r["id_area"], decidir)
        resultado = motor.hipotesis_ponderadas(memoria)
        lider = resultado[0]
        if (lider.hipotesis.id_hipotesis != r["id_hipotesis"] or r["id_regla"] not in lider.reglas_activadas
                or not lider.sintoma_confirmado):
            fallas.append(r["codigo"])
        assert r["id_pregunta"] in [p.id_pregunta for p in formuladas], r["codigo"]
    assert fallas == []


def test_resultado_maximo_cinco_y_suma_100(repo):
    motor, memoria, _ = recorrer(repo, 9, lambda p: "si" if p.id_pregunta in (9, 26) else "no_se")
    resultado = motor.hipotesis_ponderadas(memoria)
    assert 1 <= len(resultado) <= 5
    assert [h.posicion for h in resultado] == list(range(1, len(resultado) + 1))
    puntajes = [h.puntaje for h in resultado]
    assert puntajes == sorted(puntajes, reverse=True)
    assert abs(sum(h.probabilidad for h in resultado) - 1.0) < 1e-6


def test_granulo_de_rama_reparte_peso_entrada(repo):
    motor = MotorInferencia(repo)
    memoria = MemoriaTrabajo(motor._p["puntaje_base"])
    entrada = motor.iniciar(9, memoria)
    motor.procesar_respuesta(memoria, entrada, "si", 1.0)
    hipotesis_area = repo.ids_hipotesis_activas(9)
    assert hipotesis_area
    for id_h in hipotesis_area:
        assert memoria.puntajes[id_h] == pytest.approx(0.1 + 0.4)


def test_negar_todo_no_deja_puntajes_negativos(repo):
    motor, memoria, formuladas = recorrer(repo, 2, lambda p: "no")
    assert formuladas
    assert all(v >= 0 for v in memoria.puntajes.values())


def test_tope_de_preguntas(repo):
    motor, memoria, formuladas = recorrer(repo, 8, lambda p: "no_se")
    assert len(formuladas) <= int(motor._p["max_preguntas"])


def test_no_repite_preguntas(repo):
    _, _, formuladas = recorrer(repo, 8, lambda p: "probablemente_si")
    ids = [p.id_pregunta for p in formuladas]
    assert len(ids) == len(set(ids))
