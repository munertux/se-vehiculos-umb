# -*- coding: utf-8 -*-
"""Aplica archivos SQL en orden sobre la base indicada en DATABASE_URL.

Uso:
    python scripts/aplicar_sql.py                      # 05 y 06 (los idempotentes)
    python scripts/aplicar_sql.py sql/05_transaccional.sql sql/06_semillas.sql
    python scripts/aplicar_sql.py --todos              # 01, 02, 05, 06 (BORRA el conocimiento y las atenciones)
"""
import argparse
import glob
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import psycopg2  # noqa: E402

from app.datos.conexion import _dsn_desde_env  # noqa: E402
from app.datos.entorno import cargar_env  # noqa: E402

IDEMPOTENTES = ["sql/05_transaccional.sql", "sql/06_semillas.sql"]


def aplicar(dsn: str, archivos):
    conn = psycopg2.connect(dsn)
    try:
        for ruta in archivos:
            with open(ruta, encoding="utf-8") as f:
                sql = f.read()
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print(f"Aplicado: {os.path.relpath(ruta, RAIZ)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Aplica scripts SQL en orden.")
    parser.add_argument("archivos", nargs="*", help="Rutas de archivos .sql")
    parser.add_argument("--todos", action="store_true",
                        help="Aplica todos los sql/*.sql en orden (01 y 02 recrean el conocimiento).")
    args = parser.parse_args()

    cargar_env()
    if args.todos:
        archivos = sorted(glob.glob(os.path.join(RAIZ, "sql", "[0-9][0-9]_*.sql")))
    elif args.archivos:
        archivos = [os.path.abspath(a) for a in args.archivos]
    else:
        archivos = [os.path.join(RAIZ, a) for a in IDEMPOTENTES]
    aplicar(_dsn_desde_env(), archivos)


if __name__ == "__main__":
    main()
