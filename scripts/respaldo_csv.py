# -*- coding: utf-8 -*-
"""Respaldo rápido de todas las tablas del esquema public a CSV (sin pg_dump).

Uso: python scripts/respaldo_csv.py /home/respaldos
Usa DATABASE_URL (o las variables PG*) igual que la aplicación.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2  # noqa: E402

from app.datos.conexion import _dsn_desde_env  # noqa: E402


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "respaldos"
    destino = os.path.join(base, datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(destino, exist_ok=True)
    with psycopg2.connect(_dsn_desde_env()) as conn, conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
        for (tabla,) in cur.fetchall():
            with open(os.path.join(destino, tabla + ".csv"), "w", encoding="utf-8") as f:
                cur.copy_expert(f'COPY public."{tabla}" TO STDOUT WITH CSV HEADER', f)
            print("ok", tabla)
    print("Respaldo en", destino)


if __name__ == "__main__":
    main()
