# -*- coding: utf-8 -*-
"""Apoyo comun de las pruebas de datos y logica (no es un archivo de pruebas).

Las pruebas NO tocan el esquema public: cada sesion de pytest recrea dos
esquemas aislados en la BD de DATABASE_URL y carga en ellos sql/01, 02, 05
y 06. Asi se prueba contra PostgreSQL real con las 68 reglas sin modificar
los datos de desarrollo.
  - se_pruebas_motor: conocimiento intacto (solo lectura por las pruebas del motor)
  - se_pruebas: lo usan las pruebas de DAO y servicios (se modifica)

Uso en un archivo de pruebas:
    from apoyo_bd import conexion_prueba, conexion_motor  # noqa: F401 (fixtures)
"""
import os
import sys
import uuid

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import psycopg2  # noqa: E402
from psycopg2.extensions import make_dsn  # noqa: E402

from app.datos.conexion import Conexion, _dsn_desde_env  # noqa: E402
from app.datos.entorno import cargar_env  # noqa: E402

ARCHIVOS = ["sql/01_esquema.sql", "sql/02_conocimiento.sql", "sql/05_transaccional.sql", "sql/06_semillas.sql"]
_CACHE = {}


def _crear_esquema(esquema: str) -> Conexion:
    if esquema in _CACHE:
        return _CACHE[esquema]
    cargar_env()
    base = _dsn_desde_env()
    try:
        conn = psycopg2.connect(base, connect_timeout=5)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {esquema} CASCADE")
            cur.execute(f"CREATE SCHEMA {esquema}")
            cur.execute(f"SET search_path TO {esquema}")
            for ruta in ARCHIVOS:
                with open(os.path.join(RAIZ, ruta), encoding="utf-8") as f:
                    cur.execute(f.read())
        conn.commit()
    finally:
        conn.close()
    conexion = Conexion(make_dsn(base, options=f"-c search_path={esquema}"))
    _CACHE[esquema] = conexion
    return conexion


@pytest.fixture(scope="session")
def conexion_motor():
    return _crear_esquema("se_pruebas_motor")


@pytest.fixture(scope="session")
def conexion_prueba():
    return _crear_esquema("se_pruebas")


def unico(prefijo: str = "u") -> str:
    """Nombre unico para no chocar entre pruebas."""
    return f"{prefijo}{uuid.uuid4().hex[:8]}"


def placa_unica() -> str:
    h = uuid.uuid4().hex.upper()
    letras = "".join(chr(65 + int(c, 16) % 26) for c in h[:3])
    return letras + str(int(h[3:8], 16) % 1000).zfill(3)
