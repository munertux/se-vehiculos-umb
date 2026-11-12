# -*- coding: utf-8 -*-
"""Conexion a PostgreSQL (capa de datos). Unico punto del programa que
ejecuta SQL directo, tal como exige la arquitectura en tres capas del
manual (Figura 4 y Figura 23)."""
import os
import psycopg2
import psycopg2.extras


def _dsn_desde_env():
    """Azure App Service expone la cadena de conexion en una variable de
    entorno (ver appsettings). Tambien se admite AZURE_POSTGRESQL_CONNECTIONSTRING
    o variables sueltas PGHOST/PGUSER/PGPASSWORD/PGDATABASE/PGPORT."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("AZURE_POSTGRESQL_CONNECTIONSTRING")
    if dsn:
        return dsn
    host = os.environ.get("PGHOST", "localhost")
    db = os.environ.get("PGDATABASE", "sistema_experto_vehiculos")
    user = os.environ.get("PGUSER", "postgres")
    pwd = os.environ.get("PGPASSWORD", "")
    port = os.environ.get("PGPORT", "5432")
    sslmode = os.environ.get("PGSSLMODE", "require")
    return f"host={host} port={port} dbname={db} user={user} password={pwd} sslmode={sslmode}"


class Conexion:
    """Envoltorio minimo sobre psycopg2 con consultas granulares."""

    def __init__(self, dsn: str = None):
        self._dsn = dsn or _dsn_desde_env()

    def _conectar(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    def consultar(self, sql: str, parametros: tuple = ()):
        with self._conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, parametros)
                return cur.fetchall()

    def ejecutar(self, sql: str, parametros: tuple = ()):
        with self._conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, parametros)
                conn.commit()
                return cur.rowcount

    def ejecutar_retornando(self, sql: str, parametros: tuple = ()):
        with self._conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, parametros)
                fila = cur.fetchone()
                conn.commit()
                return fila
