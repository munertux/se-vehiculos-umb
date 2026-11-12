# -*- coding: utf-8 -*-
"""Blueprint del rol consultante: panel, vehiculos, consultas al sistema
experto, historial, detalle y reporte imprimible."""
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)

from app.web.api import es_propia, presentar_pregunta, presentar_resultado
from app.web.seguridad import rol_requerido
from app.web.servicios import ERRORES_USUARIO, mensaje, servicio

bp = Blueprint("consultante", __name__)

CAMPOS_VEHICULO = ("placa", "marca", "modelo", "combustible", "transmision", "anio", "kilometraje")


def _id_consultante():
    id_c = session.get("id_consultante")
    if not id_c:
        abort(403)
    return id_c


def _areas():
    areas = []
    for a in servicio("diagnostico").areas():
        if isinstance(a, dict):
            areas.append({"id_area": a["id_area"], "nombre": a["nombre"]})
        else:
            areas.append({"id_area": a.id_area, "nombre": a.nombre})
    return areas


def _testigos():
    svc = servicio("diagnostico")
    return list(svc.testigos_disponibles()) if hasattr(svc, "testigos_disponibles") else []


def _opciones_vehiculo():
    svc = servicio("vehiculos")
    if hasattr(svc, "opciones_etiquetadas"):
        return svc.opciones_etiquetadas()
    return {k: [{"valor": v, "etiqueta": v.capitalize()} for v in lista]
            for k, lista in svc.opciones().items()}


# ------------------------------------------------------------------ panel
@bp.get("/panel")
@rol_requerido("consultante")
def panel():
    id_c = _id_consultante()
    vehiculos, historial = [], []
    try:
        vehiculos = servicio("vehiculos").listar(id_c)
        historial = servicio("historial").historial(id_c)
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
    finalizadas = [h for h in historial if h.get("estado") == "finalizada"]
    confirmadas = [h for h in historial if h.get("falla_confirmada")]
    return render_template("consultante/panel.html", vehiculos=vehiculos,
                           historial=historial[:6], total_consultas=len(historial),
                           total_finalizadas=len(finalizadas), total_confirmadas=len(confirmadas))


# -------------------------------------------------------------- vehiculos
@bp.get("/vehiculos")
@rol_requerido("consultante")
def vehiculos():
    incluir = request.args.get("inactivos") == "1"
    lista = servicio("vehiculos").listar(_id_consultante(), incluir_inactivos=incluir)
    return render_template("consultante/vehiculos.html", vehiculos=lista, incluir_inactivos=incluir)


def _formulario_vehiculo(vehiculo, id_vehiculo=None, estado_http=200):
    return render_template("consultante/vehiculo_form.html", vehiculo=vehiculo, id_vehiculo=id_vehiculo,
                           editando=id_vehiculo is not None, opciones=_opciones_vehiculo()), estado_http


def _datos_vehiculo(form):
    return {c: (form.get(c) or "").strip() for c in CAMPOS_VEHICULO}


@bp.route("/vehiculos/nuevo", methods=["GET", "POST"])
@rol_requerido("consultante")
def vehiculo_nuevo():
    if request.method == "POST":
        datos = _datos_vehiculo(request.form)
        try:
            servicio("vehiculos").crear(_id_consultante(), datos)
        except ERRORES_USUARIO as exc:
            flash(mensaje(exc), "error")
            return _formulario_vehiculo(datos, estado_http=400)
        flash(f"Vehículo {datos['placa'].upper()} registrado.", "exito")
        if request.args.get("volver") == "consulta":
            return redirect(url_for("consultante.consulta_nueva"))
        return redirect(url_for("consultante.vehiculos"))
    return _formulario_vehiculo({})


@bp.route("/vehiculos/<int:id_vehiculo>/editar", methods=["GET", "POST"])
@rol_requerido("consultante")
def vehiculo_editar(id_vehiculo):
    id_c = _id_consultante()
    try:
        vehiculo = servicio("vehiculos").obtener(id_c, id_vehiculo)
    except ERRORES_USUARIO:
        abort(404)
    if request.method == "POST":
        datos = _datos_vehiculo(request.form)
        try:
            servicio("vehiculos").actualizar(id_c, id_vehiculo, datos)
        except ERRORES_USUARIO as exc:
            flash(mensaje(exc), "error")
            return _formulario_vehiculo(datos, id_vehiculo, 400)
        flash(f"Vehículo {datos['placa'].upper()} actualizado.", "exito")
        return redirect(url_for("consultante.vehiculos"))
    return _formulario_vehiculo(vehiculo, id_vehiculo)


@bp.post("/vehiculos/<int:id_vehiculo>/<any(desactivar, reactivar):accion>")
@rol_requerido("consultante")
def vehiculo_estado(id_vehiculo, accion):
    try:
        getattr(servicio("vehiculos"), accion)(_id_consultante(), id_vehiculo)
        flash("El vehículo se retiró de la lista de vehículos activos." if accion == "desactivar"
              else "El vehículo volvió a la lista de vehículos activos.", "exito")
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
    return redirect(url_for("consultante.vehiculos", inactivos=1 if accion == "reactivar" else None))


# --------------------------------------------------------------- consulta
@bp.route("/consulta/nueva", methods=["GET", "POST"])
@rol_requerido("consultante")
def consulta_nueva():
    id_c = _id_consultante()
    vehiculos_activos = servicio("vehiculos").listar(id_c)
    areas = _areas()
    testigos = _testigos()
    seleccion = {"id_vehiculo": request.args.get("vehiculo", type=int), "id_area": None,
                 "testigos": [], "codigos_obd": ""}

    if request.method == "POST":
        seleccion = {
            "id_vehiculo": request.form.get("id_vehiculo", type=int),
            "id_area": request.form.get("id_area", type=int),
            "testigos": [t for t in request.form.getlist("testigos") if t in testigos],
            "codigos_obd": (request.form.get("codigos_obd") or "").strip(),
        }
        try:
            if not seleccion["id_vehiculo"]:
                raise ValueError("Seleccione el vehículo que presenta la falla.")
            if not seleccion["id_area"]:
                raise ValueError("Seleccione el área donde nota el problema.")
            id_atencion, _pregunta = servicio("diagnostico").iniciar(
                seleccion["id_area"], id_vehiculo=seleccion["id_vehiculo"],
                testigos=seleccion["testigos"] or None, codigos_obd=seleccion["codigos_obd"] or None,
                id_consultante=id_c)
        except ERRORES_USUARIO as exc:
            flash(mensaje(exc), "error")
            return render_template("consultante/consulta_nueva.html", vehiculos=vehiculos_activos,
                                   areas=areas, testigos=testigos, seleccion=seleccion), 400
        return redirect(url_for("consultante.consulta", id_atencion=id_atencion))

    return render_template("consultante/consulta_nueva.html", vehiculos=vehiculos_activos,
                           areas=areas, testigos=testigos, seleccion=seleccion)


@bp.get("/consulta/<int:id_atencion>")
@rol_requerido("consultante")
def consulta(id_atencion):
    if not es_propia(id_atencion):
        abort(404)
    try:
        estado = servicio("diagnostico").estado(id_atencion)
        detalle = servicio("historial").detalle(_id_consultante(), id_atencion)
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
        return redirect(url_for("consultante.historial"))
    if estado.get("estado") == "finalizado":
        return redirect(url_for("consultante.detalle", id_atencion=id_atencion))
    datos = {
        "id_atencion": id_atencion,
        "pregunta": presentar_pregunta(estado.get("pregunta")),
        "n": len(detalle.get("respuestas") or []) + 1,
    }
    return render_template("consultante/consulta.html", d=detalle, datos=datos)


# -------------------------------------------------------------- historial
@bp.get("/historial")
@rol_requerido("consultante")
def historial():
    filas = servicio("historial").historial(_id_consultante())
    return render_template("consultante/historial.html", historial=filas)


def _detalle(id_atencion):
    try:
        d = servicio("historial").detalle(_id_consultante(), id_atencion)
    except ERRORES_USUARIO:
        abort(404)
    d = dict(d)
    d["hipotesis"] = presentar_resultado(d.get("hipotesis"))
    return d


@bp.get("/historial/<int:id_atencion>")
@rol_requerido("consultante")
def detalle(id_atencion):
    d = _detalle(id_atencion)
    if d.get("estado") == "en_curso":
        flash("Esta consulta sigue en curso: puede continuarla donde la dejó.", "info")
    return render_template("consultante/detalle.html", d=d)


@bp.post("/historial/<int:id_atencion>/confirmar")
@rol_requerido("consultante")
def confirmar(id_atencion):
    _detalle(id_atencion)  # verifica que la atencion sea del consultante
    id_hipotesis = request.form.get("id_hipotesis", type=int)
    observacion = (request.form.get("observacion") or "").strip() or None
    if not id_hipotesis:
        flash("Seleccione la hipótesis que corresponde a la falla real.", "error")
    else:
        try:
            servicio("diagnostico").confirmar_falla(id_atencion, id_hipotesis, observacion=observacion)
            flash("Falla real confirmada. Esta información retroalimenta la base de conocimiento.", "exito")
        except ERRORES_USUARIO as exc:
            flash(mensaje(exc), "error")
    return redirect(url_for("consultante.detalle", id_atencion=id_atencion))


@bp.get("/historial/<int:id_atencion>/reporte")
@rol_requerido("consultante")
def reporte(id_atencion):
    return render_template("consultante/reporte.html", d=_detalle(id_atencion))
