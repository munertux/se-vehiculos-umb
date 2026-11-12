# -*- coding: utf-8 -*-
"""Conexion a PostgreSQL (capa de datos). Unico punto del programa que
ejecuta SQL directo, tal como exige la arquitectura en tres capas del
manual (Figura 4 y Figura 23)."""
import os
import threading
from contextlib import contextmanager

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
    """Envoltorio minimo sobre psycopg2 con consultas granulares.

    Reutiliza una conexion por hilo (abrir una conexion por consulta es
    lento, sobre todo con TLS en Azure). Si la conexion del hilo esta
    ocupada en una transaccion, se abre una temporal. Si la conexion
    reutilizada se cayo (reinicio del servidor, timeout), se reintenta
    una vez con una nueva."""

    def __init__(self, dsn: str = None):
        self._dsn = dsn or _dsn_desde_env()
        self._local = threading.local()

    def _conectar(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    def _ejecutar(self, sql, parametros, lector):
        for intento in (1, 2):
            try:
                with self.transaccion() as cur:
                    cur.execute(sql, parametros)
                    return lector(cur)
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                if intento == 2 or not getattr(self._local, "reutilizada", False):
                    raise

    def consultar(self, sql: str, parametros: tuple = ()):
        return self._ejecutar(sql, parametros, lambda cur: cur.fetchall())

    def ejecutar(self, sql: str, parametros: tuple = ()):
        return self._ejecutar(sql, parametros, lambda cur: cur.rowcount)

    def ejecutar_retornando(self, sql: str, parametros: tuple = ()):
        return self._ejecutar(sql, parametros, lambda cur: cur.fetchone())

    @contextmanager
    def transaccion(self):
        """Entrega un cursor para varias sentencias en una sola transaccion:
        confirma al salir sin errores y revierte si hay una excepcion."""
        local = self._local
        temporal = getattr(local, "ocupada", False)
        if temporal:
            conn = self._conectar()
        else:
            conn = getattr(local, "conn", None)
            local.reutilizada = conn is not None and not conn.closed
            if not local.reutilizada:
                conn = local.conn = self._conectar()
            local.ocupada = True
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # conexion caida: se descarta para que la siguiente sea nueva
            try:
                conn.close()
            except Exception:
                pass
            if not temporal:
                local.conn = None
            raise
        except BaseException:
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            if temporal:
                conn.close()
            else:
                local.ocupada = False

    def cerrar(self):
        """Cierra la conexion del hilo actual (si hay)."""
        conn = getattr(self._local, "conn", None)
        if conn is not None and not conn.closed:
            conn.close()
        self._local.conn = None
