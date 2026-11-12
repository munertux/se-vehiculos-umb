# -*- coding: utf-8 -*-
"""Punto de arranque: ensambla las tres capas y expone el Sistema Experto
de Diagnostico de Fallas en Vehiculos como un servicio web (API REST +
interfaz HTML) protegido con autenticacion, para Azure App Service.

Importante: ninguna consulta a la base de datos se ejecuta al importar el
modulo. El ServicioDiagnostico (que consulta los parametros de inferencia)
se construye de forma perezosa en la primera peticion, de modo que el
servidor siempre arranca aunque la base no responda en ese instante.
"""
import os
import secrets
from functools import wraps

from flask import (Flask, jsonify, request, render_template, session,
                   redirect, url_for)
from werkzeug.security import check_password_hash

from app.datos.conexion import Conexion
from app.datos.repositorio_conocimiento import RepositorioConocimiento
from app.datos.repositorio_atencion import RepositorioAtencion
from app.logica.servicio_diagnostico import ServicioDiagnostico

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SEGURA", "1") == "1",
)

USUARIO = os.environ.get("SE_USUARIO", "admin")
CLAVE_HASH = os.environ.get("SE_CLAVE_HASH", "")

# --- Capas de datos: construirlas no abre ninguna conexion todavia ---
_conexion = Conexion()
_repo_conocimiento = RepositorioConocimiento(_conexion)
_repo_atencion = RepositorioAtencion(_conexion)
_servicio_cache = None


def servicio():
    """ServicioDiagnostico perezoso: su constructor consulta la tabla de
    parametros, asi que solo se crea cuando llega la primera peticion."""
    global _servicio_cache
    if _servicio_cache is None:
        _servicio_cache = ServicioDiagnostico(_repo_conocimiento, _repo_atencion)
    return _servicio_cache


def login_requerido(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        if not session.get("usuario"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "No autenticado"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return envoltura


@app.after_request
def cabeceras_seguridad(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


# ------------------------------------------------------------ autenticacion
@app.get("/login")
def login():
    if session.get("usuario"):
        return redirect(url_for("index"))
    return render_template("login.html", error=None)


@app.post("/login")
def login_post():
    usuario = (request.form.get("usuario") or "").strip()
    clave = request.form.get("clave") or ""
    if usuario == USUARIO and CLAVE_HASH and check_password_hash(CLAVE_HASH, clave):
        session.clear()
        session["usuario"] = usuario
        return redirect(url_for("index"))
    return render_template("login.html", error="Usuario o contrasena incorrectos."), 401


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ interfaz
@app.get("/")
@login_requerido
def index():
    return render_template("index.html", usuario=session.get("usuario"))


# ---------------------------------------------------------------------- API
@app.get("/api/salud")
def salud():
    """Sonda publica: no exige sesion para poder verificar el despliegue."""
    try:
        conteos = {f["conocimiento"]: f["cantidad"] for f in _repo_conocimiento.conteos()}
        return jsonify({"estado": "ok", "base_de_conocimiento": conteos})
    except Exception as exc:  # pragma: no cover
        return jsonify({"estado": "error", "detalle": str(exc)}), 500


@app.get("/api/areas")
@login_requerido
def listar_areas():
    areas = servicio().areas()
    return jsonify([{"id_area": a.id_area, "nombre": a.nombre, "descripcion": a.descripcion} for a in areas])


@app.post("/api/atenciones")
@login_requerido
def iniciar_atencion():
    datos = request.get_json(force=True)
    id_area = int(datos["id_area"])
    id_atencion, pregunta = servicio().iniciar(id_area)
    return jsonify({"id_atencion": id_atencion, "pregunta": pregunta})


@app.post("/api/atenciones/<int:id_atencion>/respuestas")
@login_requerido
def responder(id_atencion):
    datos = request.get_json(force=True)
    try:
        resultado = servicio().responder(id_atencion, int(datos["id_pregunta"]), datos["respuesta"])
        return jsonify(resultado)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/atenciones/<int:id_atencion>/finalizar")
@login_requerido
def finalizar(id_atencion):
    try:
        resultado = servicio().finalizar(id_atencion)
        return jsonify({"resultado": resultado})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/atenciones/<int:id_atencion>/confirmar")
@login_requerido
def confirmar(id_atencion):
    datos = request.get_json(force=True)
    servicio().confirmar_falla(id_atencion, int(datos["id_hipotesis"]))
    return jsonify({"estado": "confirmado"})


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=puerto, debug=True)
