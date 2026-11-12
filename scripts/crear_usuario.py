# -*- coding: utf-8 -*-
"""Crea un usuario del sistema con su perfil (consultante o empleado).

Uso:
    python scripts/crear_usuario.py <usuario> <consultante|ingeniero|administrador> "<nombres>" [--clave X]
           [--correo C] [--telefono T] [--cargo K]

Si no se da --clave se genera una aleatoria y se imprime UNA sola vez.
La contrasena se guarda solo como hash (werkzeug.security)."""
import argparse
import os
import secrets
import string
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app.datos.conexion import Conexion  # noqa: E402
from app.datos.entorno import cargar_env  # noqa: E402
from app.logica.errores import ErrorNegocio  # noqa: E402
from app.logica.servicio_administracion import ServicioAdministracion  # noqa: E402


def clave_aleatoria(longitud: int = 14) -> str:
    alfabeto = string.ascii_letters + string.digits
    while True:
        clave = "".join(secrets.choice(alfabeto) for _ in range(longitud))
        if any(c.isdigit() for c in clave) and any(c.isalpha() for c in clave):
            return clave


def main():
    parser = argparse.ArgumentParser(description="Crea un usuario del sistema experto.")
    parser.add_argument("usuario")
    parser.add_argument("rol", choices=["consultante", "ingeniero", "administrador"])
    parser.add_argument("nombres")
    parser.add_argument("--clave", help="Contrasena (si se omite se genera una aleatoria)")
    parser.add_argument("--correo")
    parser.add_argument("--telefono")
    parser.add_argument("--cargo")
    args = parser.parse_args()

    cargar_env()
    generada = args.clave is None
    clave = args.clave or clave_aleatoria()
    try:
        id_usuario = ServicioAdministracion(Conexion()).crear_usuario(
            args.usuario, clave, args.rol, args.nombres, correo=args.correo, telefono=args.telefono, cargo=args.cargo)
    except ErrorNegocio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Usuario creado: {args.usuario} (id {id_usuario}, rol {args.rol})")
    if generada:
        print(f"Contrasena generada (se muestra una sola vez): {clave}")


if __name__ == "__main__":
    main()
