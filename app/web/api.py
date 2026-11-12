# -*- coding: utf-8 -*-
"""Blueprint de la API REST (JSON) que usa la pantalla de consulta.

Se conservan las rutas historicas (/api/salud, /api/areas y
/api/atenciones...). Las llamadas POST deben enviar la cabecera
X-CSRF-Token con el token de la sesion. Un consultante solo puede operar
sobre sus propias atenciones.
"""
from flask import Blueprint, jsonify, request, session

from app.web.presentacion import clase_nivel, es_critico, tildes
from app.web.seguridad import login_requerido, rol_requerido
from app.web.servicios import ERRORES_USUARIO, mensaje, servicio

bp = Blueprint("api", __name__, url_prefix="/api")


# --------------------------------------------------------- presentacion
def presentar_pregunta(p):
    if not p:
        return p
    p = dict(p)
    p["enunciado"] = tildes(p.get("enunciado"))
    p["opciones"] = [dict(o, etiqueta=tildes(o.get("etiqueta"))) for o in p.get("opciones", [])]
    return p


def presentar_resultado(hipotesis):
    salida = []
    for h in hipotesis or []:
        h = dict(h)
        nivel = h.get("nivel_atencion") or ""
        h["nombre"] = tildes(h.get("nombre"))
        h["descripcion"] = tildes(h.get("descripcion"))
        h["recomendacion"] = tildes(h.get("recomendacion"))
        h["nivel_texto"] = tildes(nivel)
        h["nivel_clase"] = clase_nivel(nivel)
        h["advertencia"] = bool(h.get("advertencia")) or es_critico(nivel)
        h["reglas_activadas"] = list(h.get("reglas_activadas") or [])
        salida.append(h)
    return salida


def es_propia(id_atencion):
    """True si la atencion pertenece al consultante de la sesion."""
    id_c = session.get("id_consultante")
    if not id_c:
        return False
    try:
        return bool(servicio("diagnostico").pertenece(id_atencion, id_c))
    except ERRORES_USUARIO:
        return False


def _error(exc, codigo=400):
    return jsonify({"error": exc if isinstance(exc, str) else mensaje(exc)}), codigo


def _ajena():
    return jsonify({"error": "La atención no existe o no pertenece a su cuenta."}), 404


# --------------------------------------------------------------- rutas
@bp.get("/salud")
def salud():
    """Sonda publica: no exige sesion para poder verificar el despliegue."""
    try:
        resumen = servicio("conocimiento").resumen()
        return jsonify({"estado": "ok", "base_de_conocimiento": resumen})
    except Exception as exc:  # pragma: no cover - depende de la base
        return jsonify({"estado": "error", "detalle": str(exc)}), 500


@bp.get("/areas")
@login_requerido
def listar_areas():
    salida = []
    for a in servicio("diagnostico").areas():
        if isinstance(a, dict):
            salida.append({"id_area": a["id_area"], "nombre": tildes(a["nombre"]),
                           "descripcion": tildes(a.get("descripcion"))})
        else:
            salida.append({"id_area": a.id_area, "nombre": tildes(a.nombre),
                           "descripcion": tildes(a.descripcion)})
    return jsonify(salida)


@bp.post("/atenciones")
@rol_requerido("consultante")
def iniciar_atencion():
    datos = request.get_json(silent=True) or {}
    try:
        id_area = int(datos["id_area"])
    except (KeyError, TypeError, ValueError):
        return _error("Debe indicar un área válida.")
    try:
        id_atencion, pregunta = servicio("diagnostico").iniciar(
            id_area,
            id_vehiculo=datos.get("id_vehiculo") or None,
            testigos=datos.get("testigos") or None,
            codigos_obd=datos.get("codigos_obd") or None,
            id_consultante=session.get("id_consultante"),
        )
    except ERRORES_USUARIO as exc:
        return _error(exc)
    return jsonify({"id_atencion": id_atencion, "pregunta": presentar_pregunta(pregunta)})


@bp.get("/atenciones/<int:id_atencion>")
@rol_requerido("consultante")
def estado(id_atencion):
    if not es_propia(id_atencion):
        return _ajena()
    try:
        r = dict(servicio("diagnostico").estado(id_atencion))
    except ERRORES_USUARIO as exc:
        return _error(exc)
    if r.get("estado") == "finalizado":
        r["resultado"] = presentar_resultado(r.get("resultado"))
    else:
        r["pregunta"] = presentar_pregunta(r.get("pregunta"))
    return jsonify(r)


@bp.post("/atenciones/<int:id_atencion>/respuestas")
@rol_requerido("consultante")
def responder(id_atencion):
    if not es_propia(id_atencion):
        return _ajena()
    datos = request.get_json(silent=True) or {}
    try:
        id_pregunta = int(datos["id_pregunta"])
        respuesta = str(datos["respuesta"])
    except (KeyError, TypeError, ValueError):
        return _error("Solicitud incompleta: falta la pregunta o la respuesta.")
    try:
        resultado = dict(servicio("diagnostico").responder(id_atencion, id_pregunta, respuesta))
    except ERRORES_USUARIO as exc:
        return _error(exc)
    if resultado.get("estado") == "finalizado":
        resultado["resultado"] = presentar_resultado(resultado.get("resultado"))
    else:
        resultado["pregunta"] = presentar_pregunta(resultado.get("pregunta"))
    return jsonify(resultado)


@bp.post("/atenciones/<int:id_atencion>/finalizar")
@rol_requerido("consultante")
def finalizar(id_atencion):
    if not es_propia(id_atencion):
        return _ajena()
    try:
        resultado = servicio("diagnostico").finalizar(id_atencion)
    except ERRORES_USUARIO as exc:
        return _error(exc)
    return jsonify({"resultado": presentar_resultado(resultado)})


@bp.post("/atenciones/<int:id_atencion>/confirmar")
@rol_requerido("consultante")
def confirmar(id_atencion):
    if not es_propia(id_atencion):
        return _ajena()
    datos = request.get_json(silent=True) or {}
    try:
        id_hipotesis = int(datos["id_hipotesis"])
    except (KeyError, TypeError, ValueError):
        return _error("Debe indicar la hipótesis confirmada.")
    observacion = (datos.get("observacion") or "").strip() or None
    try:
        servicio("diagnostico").confirmar_falla(id_atencion, id_hipotesis, observacion=observacion)
    except ERRORES_USUARIO as exc:
        return _error(exc)
    return jsonify({"estado": "confirmado"})
