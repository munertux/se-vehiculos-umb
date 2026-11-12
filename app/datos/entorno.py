# -*- coding: utf-8 -*-
"""Lectura minima de un archivo .env (sin dependencias externas). Solo
se usa en scripts y pruebas locales; en Azure las variables ya vienen
definidas por App Service."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cargar_env(ruta: str = None, sobrescribir: bool = False):
    ruta = ruta or os.path.join(RAIZ, ".env")
    if not os.path.isfile(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            if sobrescribir or clave not in os.environ:
                os.environ[clave] = valor
