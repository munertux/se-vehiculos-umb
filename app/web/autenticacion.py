# -*- coding: utf-8 -*-
"""Blueprint de autenticacion: ingreso, salida y cambio de contrasena."""
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from app.web.seguridad import PANEL_ROL, autenticado, iniciar_sesion, login_requerido
from app.web.servicios import ERRORES_USUARIO, mensaje, servicio

bp = Blueprint("autenticacion", __name__)


def _destino_seguro(siguiente):
    """Solo se permiten rutas internas para evitar redirecciones abiertas."""
    if siguiente and siguiente.startswith("/") and not siguiente.startswith("//") \
            and not siguiente.startswith("/login"):
        return siguiente
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if autenticado():
            return redirect(url_for(PANEL_ROL[session["rol"]]))
        return render_template("login.html", error=None, usuario="")

    nombre_usuario = (request.form.get("usuario") or "").strip()
    clave = request.form.get("clave") or ""
    if not nombre_usuario or not clave:
        return render_template("login.html", error="Ingrese el usuario y la contraseña.",
                               usuario=nombre_usuario), 400
    try:
        datos = servicio("autenticacion").autenticar(nombre_usuario, clave)
    except ERRORES_USUARIO as exc:
        return render_template("login.html", error=mensaje(exc), usuario=nombre_usuario), 401
    iniciar_sesion(datos)
    destino = _destino_seguro(request.args.get("siguiente"))
    return redirect(destino or url_for(PANEL_ROL[session["rol"]]))


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("autenticacion.login"))


@bp.route("/cuenta/clave", methods=["GET", "POST"])
@login_requerido
def cambiar_clave():
    if request.method == "POST":
        actual = request.form.get("clave_actual") or ""
        nueva = request.form.get("clave_nueva") or ""
        confirmacion = request.form.get("clave_confirmacion") or ""
        if nueva != confirmacion:
            flash("La confirmación no coincide con la contraseña nueva.", "error")
        else:
            try:
                servicio("autenticacion").cambiar_clave(session["id_usuario"], actual, nueva)
                flash("La contraseña se cambió correctamente.", "exito")
                return redirect(url_for("inicio"))
            except ERRORES_USUARIO as exc:
                flash(mensaje(exc), "error")
    return render_template("cuenta_clave.html")
