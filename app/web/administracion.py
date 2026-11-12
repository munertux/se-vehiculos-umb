# -*- coding: utf-8 -*-
"""Blueprint del administrador: usuarios, auditoria y respaldos."""
from datetime import datetime

from flask import (Blueprint, Response, flash, redirect, render_template, request,
                   session, url_for)

from app.web.seguridad import NOMBRE_ROL, ROLES, rol_requerido
from app.web.servicios import ERRORES_USUARIO, mensaje, servicio

bp = Blueprint("administracion", __name__, url_prefix="/admin")


def _svc():
    return servicio("administracion")


@bp.get("/")
@bp.get("")
@rol_requerido("administrador")
def inicio():
    return redirect(url_for("administracion.usuarios"))


@bp.get("/usuarios")
@rol_requerido("administrador")
def usuarios():
    return render_template("admin/usuarios.html", usuarios=_svc().listar_usuarios(),
                           roles=[(r, NOMBRE_ROL[r]) for r in ROLES], valores={},
                           abierto=request.args.get("nuevo") == "1")


@bp.post("/usuarios")
@rol_requerido("administrador")
def crear_usuario():
    f = request.form
    valores = f.to_dict()
    valores.pop("clave", None)
    try:
        nombre_usuario = (f.get("nombre_usuario") or "").strip()
        clave = f.get("clave") or ""
        rol = f.get("rol") or ""
        nombres = (f.get("nombres") or "").strip()
        if not nombre_usuario or not clave or not nombres or rol not in ROLES:
            raise ValueError("Complete usuario, nombres, rol y contraseña inicial.")
        if clave != (f.get("clave_confirmacion") or ""):
            raise ValueError("La confirmación no coincide con la contraseña inicial.")
        _svc().crear_usuario(
            nombre_usuario, clave, rol, nombres,
            correo=(f.get("correo") or "").strip() or None,
            telefono=(f.get("telefono") or "").strip() or None,
            cargo=(f.get("cargo") or "").strip() or None,
            id_empleado=session.get("id_empleado"),
        )
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
        return render_template("admin/usuarios.html", usuarios=_svc().listar_usuarios(),
                               roles=[(r, NOMBRE_ROL[r]) for r in ROLES], valores=valores,
                               abierto=True), 400
    flash(f"Usuario {nombre_usuario} creado como {NOMBRE_ROL[rol].lower()}.", "exito")
    return redirect(url_for("administracion.usuarios"))


def _accion_usuario(id_usuario, accion):
    if id_usuario == session.get("id_usuario") and accion in ("rol", "bloquear", "inactivar"):
        raise ValueError("No puede cambiar el rol, bloquear ni inactivar su propia cuenta.")
    svc = _svc()
    quien = {"id_empleado": session.get("id_empleado")}
    if accion == "rol":
        rol = request.form.get("rol")
        if rol not in ROLES:
            raise ValueError("Rol no válido.")
        svc.cambiar_rol(id_usuario, rol, **quien)
        return f"Rol actualizado a {NOMBRE_ROL[rol].lower()}."
    if accion == "bloquear":
        svc.bloquear(id_usuario, **quien)
        return "Usuario bloqueado."
    if accion == "desbloquear":
        svc.desbloquear(id_usuario, **quien)
        return "Usuario desbloqueado."
    if accion == "activar":
        svc.activar(id_usuario, True, **quien)
        return "Usuario activado."
    if accion == "inactivar":
        svc.activar(id_usuario, False, **quien)
        return "Usuario inactivado."
    if accion == "clave":
        clave = request.form.get("clave") or ""
        if clave != (request.form.get("clave_confirmacion") or ""):
            raise ValueError("La confirmación no coincide con la contraseña nueva.")
        svc.restablecer_clave(id_usuario, clave, **quien)
        return "Contraseña restablecida. Comuníquela al usuario por un canal seguro."
    raise ValueError("Acción no válida.")


@bp.post("/usuarios/<int:id_usuario>/<any(rol, bloquear, desbloquear, activar, inactivar, clave):accion>")
@rol_requerido("administrador")
def accion_usuario(id_usuario, accion):
    try:
        flash(_accion_usuario(id_usuario, accion), "exito")
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
    return redirect(url_for("administracion.usuarios"))


@bp.get("/auditoria")
@rol_requerido("administrador")
def auditoria():
    limite = min(max(request.args.get("limite", 200, type=int), 10), 1000)
    registros = _svc().auditoria(limite=limite)
    entidad = (request.args.get("entidad") or "").strip()
    entidades = sorted({str(r.get("entidad")) for r in registros if r.get("entidad")})
    if entidad:
        registros = [r for r in registros if str(r.get("entidad")) == entidad]
    return render_template("admin/auditoria.html", registros=registros, limite=limite,
                           entidad=entidad, entidades=entidades)


@bp.get("/respaldos")
@rol_requerido("administrador")
def respaldos():
    return render_template("admin/respaldos.html",
                           puede_restaurar=hasattr(_svc(), "restaurar_conocimiento"))


@bp.post("/respaldos/descargar")
@rol_requerido("administrador")
def descargar_respaldo():
    alcance = request.form.get("alcance")
    if alcance == "conocimiento" and hasattr(_svc(), "respaldo_conocimiento_sql"):
        sql = _svc().respaldo_conocimiento_sql()
        nombre = datetime.now().strftime("conocimiento_se_vehiculos_%Y%m%d_%H%M.sql")
    else:
        sql = _svc().respaldo_sql()
        nombre = datetime.now().strftime("respaldo_se_vehiculos_%Y%m%d_%H%M.sql")
    return Response(sql, mimetype="application/sql",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@bp.post("/respaldos/restaurar")
@rol_requerido("administrador")
def restaurar_respaldo():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename.lower().endswith(".sql"):
        flash("Seleccione un archivo .sql generado por el sistema.", "error")
        return redirect(url_for("administracion.respaldos"))
    if request.form.get("confirmar") != "1":
        flash("Marque la casilla de confirmación antes de restaurar.", "error")
        return redirect(url_for("administracion.respaldos"))
    try:
        contenido = archivo.read().decode("utf-8")
        aplicadas = _svc().restaurar_conocimiento(contenido, id_empleado=session.get("id_empleado"))
        flash(f"Base de conocimiento restaurada: {aplicadas} registros aplicados.", "exito")
    except UnicodeDecodeError:
        flash("El archivo no está codificado en UTF-8.", "error")
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
    return redirect(url_for("administracion.respaldos"))
