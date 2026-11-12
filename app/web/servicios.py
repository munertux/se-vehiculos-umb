# -*- coding: utf-8 -*-
"""Acceso de la capa de presentacion a los servicios de la capa de logica.

La presentacion nunca toca DAO ni SQL: solo pide servicios por nombre.
Cada servicio se construye de forma perezosa (en la primera peticion que
lo necesita) para que el servidor arranque aunque la base de datos no
responda en ese instante. Las pruebas pueden inyectar dobles con
``crear_app(servicios={...})``.
"""
import importlib
import re

from flask import current_app

try:  # A1 define la excepcion de negocio en app/logica/errores.py
    from app.logica.errores import ErrorNegocio
except ImportError:  # pragma: no cover - solo mientras A1 no la publique
    class ErrorNegocio(Exception):
        """Respaldo temporal con la misma semantica que la de A1."""

# Errores que se muestran al usuario como mensaje (no como error 500).
ERRORES_USUARIO = (ErrorNegocio, ValueError)

_FABRICAS = {
    "autenticacion": ("app.logica.servicio_autenticacion", "ServicioAutenticacion"),
    "vehiculos": ("app.logica.servicio_vehiculos", "ServicioVehiculos"),
    "diagnostico": ("app.logica.servicio_diagnostico", "ServicioDiagnostico"),
    "historial": ("app.logica.servicio_historial", "ServicioHistorial"),
    "conocimiento": ("app.logica.servicio_conocimiento", "ServicioConocimiento"),
    "administracion": ("app.logica.servicio_administracion", "ServicioAdministracion"),
}


def _conexion():
    ext = current_app.extensions.setdefault("se_servicios", {})
    if "_conexion" not in ext:
        from app.datos.conexion import Conexion
        ext["_conexion"] = Conexion()
    return ext["_conexion"]


def _construir(nombre):
    modulo, clase = _FABRICAS[nombre]
    cls = getattr(importlib.import_module(modulo), clase)
    return cls(_conexion())


def mensaje(exc):
    """Texto del error de negocio listo para mostrar (con tildes)."""
    from app.web.presentacion import tildes
    texto = getattr(exc, "mensaje", None) or str(exc)
    texto = re.sub(r"\b([Ee])sta (activ|inactiv|bloquead|en curso|cerrad)", r"\1stá \2", texto)
    return tildes(texto)


def servicio(nombre):
    """Devuelve (y memoriza en la aplicacion) el servicio pedido."""
    ext = current_app.extensions.setdefault("se_servicios", {})
    if nombre not in ext:
        ext[nombre] = _construir(nombre)
    return ext[nombre]
