# -*- coding: utf-8 -*-
"""RespaldoDAO: genera sentencias INSERT con el contenido de las tablas
(respaldo logico en SQL plano) y ejecuta un lote de sentencias en una
sola transaccion (restauracion)."""
from datetime import date, datetime
from decimal import Decimal

from app.datos.dao.base_dao import BaseDAO

# Orden compatible con las llaves foraneas.
TABLAS_CONOCIMIENTO = ("areas", "hipotesis", "preguntas", "reglas", "parametros_inferencia")
TABLAS_TRANSACCIONALES = ("rol", "usuario", "consultante", "empleado", "vehiculo",
                          "atencion", "atencion_respuesta", "atencion_diagnostico", "bitacora_conocimiento")
ORDEN_RESPALDO = ("rol", "usuario", "consultante", "empleado", "vehiculo",
                  "areas", "hipotesis", "preguntas", "reglas", "parametros_inferencia",
                  "atencion", "atencion_respuesta", "atencion_diagnostico", "bitacora_conocimiento")


def literal_sql(valor) -> str:
    """Valor de Python -> literal SQL en una sola linea."""
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, (int, float, Decimal)):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return "'" + valor.isoformat(sep=" ") + "'" if isinstance(valor, datetime) else "'" + valor.isoformat() + "'"
    texto = str(valor)
    if any(c in texto for c in ("\\", "\n", "\r", "\t")):
        texto = (texto.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                 .replace("\r", "\\r").replace("\t", "\\t"))
        return "E'" + texto + "'"
    return "'" + texto.replace("'", "''") + "'"


class RespaldoDAO(BaseDAO):
    def tablas_existentes(self, tx=None) -> set:
        return {f["table_name"] for f in self._filas(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()", tx=tx)}

    def columnas(self, tabla: str, tx=None) -> list:
        return [f["column_name"] for f in self._filas(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position", (tabla,), tx)]

    def llave_primaria(self, tabla: str, tx=None) -> list:
        return [f["attname"] for f in self._filas(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = (quote_ident(current_schema()) || '.' || quote_ident(%s))::regclass "
            "AND i.indisprimary ORDER BY array_position(i.indkey, a.attnum)", (tabla,), tx)]

    def columnas_serial(self, tabla: str, tx=None) -> list:
        return [f["column_name"] for f in self._filas(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND table_name = %s AND column_default LIKE 'nextval(%%'", (tabla,), tx)]

    def filas(self, tabla: str, columnas: list, orden: list, tx=None) -> list:
        # tabla y columnas vienen del catalogo, no del usuario
        cols = ", ".join(columnas)
        orden_sql = ", ".join(orden) if orden else "1"
        return self._filas(f"SELECT {cols} FROM {tabla} ORDER BY {orden_sql}", tx=tx)

    def sentencias_insert(self, tabla: str, actualizar_si_existe: bool = False, tx=None) -> list:
        """Lista de INSERT ... ON CONFLICT para todas las filas de la tabla."""
        columnas = self.columnas(tabla, tx)
        pk = self.llave_primaria(tabla, tx)
        if actualizar_si_existe and pk:
            resto = [c for c in columnas if c not in pk]
            conflicto = (f" ON CONFLICT ({', '.join(pk)}) DO UPDATE SET "
                         + ", ".join(f"{c} = EXCLUDED.{c}" for c in resto)) if resto else \
                f" ON CONFLICT ({', '.join(pk)}) DO NOTHING"
        else:
            conflicto = " ON CONFLICT DO NOTHING"
        lista_cols = ", ".join(columnas)
        salida = []
        for fila in self.filas(tabla, columnas, pk, tx):
            valores = ", ".join(literal_sql(fila[c]) for c in columnas)
            salida.append(f"INSERT INTO {tabla} ({lista_cols}) VALUES ({valores}){conflicto};")
        return salida

    def sentencias_secuencias(self, tabla: str, tx=None) -> list:
        return [f"SELECT setval(pg_get_serial_sequence('{tabla}', '{c}'), COALESCE((SELECT MAX({c}) FROM {tabla}), 0) + 1, false);"
                for c in self.columnas_serial(tabla, tx)]

    def ejecutar_lote(self, sentencias: list) -> int:
        """Ejecuta todas las sentencias en una sola transaccion."""
        with self._db.transaccion() as cur:
            for s in sentencias:
                cur.execute(s)
        return len(sentencias)
