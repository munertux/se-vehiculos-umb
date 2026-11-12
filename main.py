# -*- coding: utf-8 -*-
"""Punto de arranque del Sistema Experto de Diagnostico de Fallas en
Vehiculos. Ensambla la capa de presentacion (blueprints de app/web) y
expone ``main:app`` para gunicorn en Azure App Service.

Ninguna consulta a la base de datos se ejecuta al importar el modulo:
los servicios de la capa de logica se construyen de forma perezosa en la
primera peticion que los necesita (ver app/web/servicios.py).
"""
import os
import secrets
from datetime import datetime

from flask import Flask, redirect, render_template, session, url_for

from app.web import presentacion, seguridad
from app.web.administracion import bp as bp_administracion
from app.web.api import bp as bp_api
from app.web.autenticacion import bp as bp_autenticacion
from app.web.conocimiento import bp as bp_conocimiento
from app.web.consultante import bp as bp_consultante

NOMBRE_SISTEMA = "Sistema experto de diagnóstico de fallas en vehículos"


def crear_app(config=None, servicios=None):
    """Fabrica de la aplicacion.

    ``config``: valores que sobrescriben la configuracion (pruebas).
    ``servicios``: dict nombre -> instancia para inyectar dobles de prueba.
    """
    app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SEGURA", "1") == "1",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        NOMBRE_SISTEMA=NOMBRE_SISTEMA,
    )
    if config:
        app.config.update(config)
    if servicios:
        app.extensions.setdefault("se_servicios", {}).update(servicios)

    seguridad.instalar(app)
    presentacion.instalar(app)

    for bp in (bp_autenticacion, bp_consultante, bp_conocimiento, bp_administracion, bp_api):
        app.register_blueprint(bp)

    @app.context_processor
    def contexto_general():
        return {"nombre_sistema": app.config["NOMBRE_SISTEMA"], "ahora": datetime.now()}

    @app.get("/")
    @seguridad.login_requerido
    def inicio():
        return redirect(url_for(seguridad.PANEL_ROL[session["rol"]]))

    @app.errorhandler(403)
    def prohibido(_e):
        return render_template("error.html", codigo=403, titulo="Acceso no permitido",
                               mensaje="Su rol no tiene permiso para abrir esta página."), 403

    @app.errorhandler(404)
    def no_encontrado(_e):
        return render_template("error.html", codigo=404, titulo="Página no encontrada",
                               mensaje="La dirección solicitada no existe o el registro ya no está disponible."), 404

    @app.errorhandler(500)
    def error_interno(_e):
        return render_template("error.html", codigo=500, titulo="Error interno",
                               mensaje="Ocurrió un error inesperado. Inténtelo de nuevo en unos minutos."), 500

    return app


app = crear_app()


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=puerto, debug=os.environ.get("FLASK_DEBUG") == "1")
