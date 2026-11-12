# -*- coding: utf-8 -*-
"""Seguridad de la capa web: sesion con expiracion por inactividad,
control de acceso por rol, proteccion CSRF y cabeceras HTTP."""
import hmac
import secrets
import time
from datetime import timedelta
from functools import wraps

from flask import (abort, flash, jsonify, redirect, render_template, request,
                   session, url_for)

MINUTOS_INACTIVIDAD = 15
ROLES = ("consultante", "ingeniero", "administrador")
NOMBRE_ROL = {
    "consultante": "Consultante",
    "ingeniero": "Ingeniero del conocimiento",
    "administrador": "Administrador",
}
# Panel de inicio de cada rol (destino de "/").
PANEL_ROL = {
    "consultante": "consultante.panel",
    "ingeniero": "conocimiento.resumen",
    "administrador": "administracion.usuarios",
}
METODOS_INSEGUROS = {"POST", "PUT", "PATCH", "DELETE"}
CLAVES_SESION = ("id_usuario", "nombre_usuario", "rol", "nombres",
                 "id_consultante", "id_empleado")


def _es_api():
    return request.path.startswith("/api/")


def autenticado():
    return bool(session.get("id_usuario")) and session.get("rol") in ROLES


def iniciar_sesion(datos):
    """Guarda en la sesion exactamente el diccionario del contrato."""
    session.clear()
    for clave in CLAVES_SESION:
        session[clave] = datos.get(clave)
    session.permanent = True
    session["ultimo_uso"] = int(time.time())
    session["csrf"] = secrets.token_urlsafe(32)


def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def _no_autenticado():
    if _es_api():
        return jsonify({"error": "No autenticado"}), 401
    return redirect(url_for("autenticacion.login", siguiente=request.full_path.rstrip("?")))


def login_requerido(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        if not autenticado():
            return _no_autenticado()
        return f(*args, **kwargs)
    return envoltura


def rol_requerido(*roles):
    """Permite la vista solo a los roles indicados (403 para los demas)."""
    def decorador(f):
        @wraps(f)
        def envoltura(*args, **kwargs):
            if not autenticado():
                return _no_autenticado()
            if session.get("rol") not in roles:
                if _es_api():
                    return jsonify({"error": "No autorizado para este rol"}), 403
                abort(403)
            return f(*args, **kwargs)
        return envoltura
    return decorador


def instalar(app):
    """Registra en la aplicacion los ganchos de seguridad."""
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=MINUTOS_INACTIVIDAD)
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True

    @app.before_request
    def controlar_inactividad():
        if request.endpoint == "static" or not session.get("id_usuario"):
            return None
        ahora = int(time.time())
        ultimo = session.get("ultimo_uso", 0)
        if ahora - ultimo > MINUTOS_INACTIVIDAD * 60:
            session.clear()
            if _es_api():
                return jsonify({"error": "La sesión expiró por inactividad"}), 401
            flash("Su sesión expiró por inactividad. Ingrese de nuevo.", "info")
            return redirect(url_for("autenticacion.login"))
        session["ultimo_uso"] = ahora
        session.permanent = True
        return None

    @app.before_request
    def verificar_csrf():
        if request.method not in METODOS_INSEGUROS or app.config.get("CSRF_DESACTIVADO"):
            return None
        esperado = session.get("csrf")
        recibido = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if not esperado or not recibido or not hmac.compare_digest(str(esperado), str(recibido)):
            if _es_api():
                return jsonify({"error": "Token CSRF inválido o ausente"}), 400
            if request.endpoint == "autenticacion.login":
                flash("El formulario caducó. Intente ingresar de nuevo.", "error")
                return redirect(url_for("autenticacion.login"))
            return render_template("error.html", codigo=400,
                                   titulo="Solicitud no válida",
                                   mensaje="El formulario caducó o no es válido. "
                                           "Vuelva a la página anterior, recárguela e inténtelo de nuevo."), 400
        return None

    @app.after_request
    def cabeceras_seguridad(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        if session.get("id_usuario") and request.endpoint != "static":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.context_processor
    def contexto_seguridad():
        return {
            "csrf_token": token_csrf,
            "usuario_actual": {
                "nombre_usuario": session.get("nombre_usuario"),
                "nombres": session.get("nombres"),
                "rol": session.get("rol"),
                "nombre_rol": NOMBRE_ROL.get(session.get("rol"), ""),
            } if autenticado() else None,
        }
