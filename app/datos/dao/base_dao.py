# -*- coding: utf-8 -*-
"""BaseDAO: clase base de todos los DAO. Guarda la Conexion y ofrece
utilidades para consultar dentro o fuera de una transaccion.

Cada metodo publico de los DAO acepta un argumento opcional `tx` (cursor
entregado por Conexion.transaccion()) para que el servicio agrupe varias
operaciones en una sola transaccion. Sin `tx`, cada sentencia se confirma
por separado."""


class BaseDAO:
    def __init__(self, conexion):
        self._db = conexion

    @property
    def conexion(self):
        return self._db

    def _filas(self, sql: str, parametros: tuple = (), tx=None) -> list:
        if tx is not None:
            tx.execute(sql, parametros)
            return list(tx.fetchall())
        return list(self._db.consultar(sql, parametros))

    def _fila(self, sql: str, parametros: tuple = (), tx=None):
        if tx is not None:
            tx.execute(sql, parametros)
            return tx.fetchone()
        filas = self._db.consultar(sql, parametros)
        return filas[0] if filas else None

    def _ejecutar(self, sql: str, parametros: tuple = (), tx=None) -> int:
        if tx is not None:
            tx.execute(sql, parametros)
            return tx.rowcount
        return self._db.ejecutar(sql, parametros)

    def _retornando(self, sql: str, parametros: tuple = (), tx=None):
        if tx is not None:
            tx.execute(sql, parametros)
            return tx.fetchone()
        return self._db.ejecutar_retornando(sql, parametros)

    def _escalar(self, sql: str, parametros: tuple = (), tx=None):
        fila = self._fila(sql, parametros, tx)
        if not fila:
            return None
        return next(iter(fila.values()))

    @staticmethod
    def _set_dinamico(datos: dict, permitidas) -> tuple:
        """Arma 'col1 = %s, col2 = %s' solo con columnas permitidas."""
        columnas = [c for c in permitidas if c in datos]
        sql = ", ".join(f"{c} = %s" for c in columnas)
        return sql, tuple(datos[c] for c in columnas)
