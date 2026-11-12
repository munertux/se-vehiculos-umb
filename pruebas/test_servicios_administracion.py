# -*- coding: utf-8 -*-
"""Administracion de usuarios, auditoria y respaldo/restauracion."""
import pytest

from apoyo_bd import conexion_prueba, unico  # noqa: F401 (fixture)
from app.datos.dao.area_dao import AreaDAO
from app.logica.errores import ErrorNegocio
from app.logica.servicio_administracion import ServicioAdministracion
from app.logica.servicio_autenticacion import ServicioAutenticacion

CLAVE = "Clave2026z"


@pytest.fixture
def adm(conexion_prueba):
    return ServicioAdministracion(conexion_prueba)


def test_crear_y_listar_usuarios(adm):
    nombre = unico("adm")
    id_u = adm.crear_usuario(nombre, CLAVE, "consultante", "Ana Perez", correo="ana@example.com", telefono="300")
    u = adm.obtener_usuario(id_u)
    assert u["rol"] == "consultante" and u["nombres"] == "Ana Perez" and u["id_consultante"]
    assert "contrasena_hash" not in u
    with pytest.raises(ErrorNegocio, match="ya existe"):
        adm.crear_usuario(nombre.upper(), CLAVE, "consultante", "Otra")
    with pytest.raises(ErrorNegocio, match="rol"):
        adm.crear_usuario(unico("x"), CLAVE, "jefe", "Otra")
    with pytest.raises(ErrorNegocio, match="correo"):
        adm.crear_usuario(unico("x"), CLAVE, "consultante", "Otra", correo="malo")
    with pytest.raises(ErrorNegocio, match="usuario"):
        adm.crear_usuario("a b", CLAVE, "consultante", "Otra")


def test_cambiar_rol_crea_perfil(conexion_prueba, adm):
    nombre = unico("rol")
    id_u = adm.crear_usuario(nombre, CLAVE, "consultante", "Pedro Rol")
    adm.cambiar_rol(id_u, "ingeniero")
    s = ServicioAutenticacion(conexion_prueba).autenticar(nombre, CLAVE)
    assert s["rol"] == "ingeniero" and s["id_empleado"] and s["id_consultante"] is None and s["nombres"] == "Pedro Rol"
    adm.cambiar_rol(id_u, "consultante")
    s = ServicioAutenticacion(conexion_prueba).autenticar(nombre, CLAVE)
    assert s["rol"] == "consultante" and s["id_consultante"]


def test_no_se_queda_sin_administrador(conexion_prueba, adm):
    admins = [u for u in adm.listar_usuarios() if u["rol"] == "administrador" and u["estado"] == "activo"]
    if not admins:
        adm.crear_usuario(unico("adm"), CLAVE, "administrador", "Admin Unico")
        admins = [u for u in adm.listar_usuarios() if u["rol"] == "administrador" and u["estado"] == "activo"]
    # inactiva a todos menos uno y comprueba que el ultimo no se puede quitar
    for u in admins[1:]:
        adm.activar(u["id_usuario"], False)
    ultimo = admins[0]["id_usuario"]
    with pytest.raises(ErrorNegocio, match="unico administrador"):
        adm.activar(ultimo, False)
    with pytest.raises(ErrorNegocio, match="unico administrador"):
        adm.cambiar_rol(ultimo, "consultante")
    for u in admins[1:]:
        adm.activar(u["id_usuario"], True)


def test_auditoria_registra_acciones_de_usuarios(adm):
    id_u = adm.crear_usuario(unico("aud"), CLAVE, "consultante", "Auditado")
    adm.bloquear(id_u)
    adm.desbloquear(id_u)
    registros = [r for r in adm.auditoria(50) if r["entidad"] == "usuario" and r["id_registro"] == id_u]
    assert [r["accion"] for r in registros] == ["activar", "desactivar", "crear"]


def test_respaldo_sql_completo(adm):
    sql = adm.respaldo_sql()
    assert sql.startswith("-- Respaldo") and "BEGIN;" in sql and sql.rstrip().endswith("COMMIT;")
    for tabla in ("rol", "usuario", "consultante", "areas", "preguntas", "reglas", "parametros_inferencia",
                  "bitacora_conocimiento"):
        assert f"INSERT INTO {tabla} (" in sql, tabla
    assert "Clave2026z" not in sql                 # nunca claves en claro
    assert "contrasena_hash" in sql                # los hash si van
    assert "setval(pg_get_serial_sequence('usuario'" in sql


def test_restaurar_conocimiento_roundtrip(conexion_prueba, adm):
    respaldo = adm.respaldo_sql()
    original = AreaDAO(conexion_prueba).obtener(1).nombre
    AreaDAO(conexion_prueba).actualizar(1, {"nombre": "Nombre alterado"})
    aplicadas = adm.restaurar_conocimiento(respaldo)
    assert aplicadas >= 24 + 68 + 92 + 68
    assert AreaDAO(conexion_prueba).obtener(1).nombre == original


@pytest.mark.parametrize("malicioso", [
    "DROP TABLE areas;",
    "INSERT INTO areas (id_area, nombre) VALUES (500, 'x') ON CONFLICT DO NOTHING; DROP TABLE reglas;",
    "INSERT INTO areas (id_area, nombre) VALUES (500, (SELECT current_user)) ON CONFLICT DO NOTHING;",
    "INSERT INTO areas (id_area, nombre) VALUES (500, pg_sleep(1)) ON CONFLICT DO NOTHING;",
    "UPDATE usuario SET id_rol = 3;",
    "",
])
def test_restaurar_rechaza_sentencias_no_permitidas(adm, malicioso):
    with pytest.raises(ErrorNegocio):
        adm.restaurar_conocimiento(malicioso)


def test_restaurar_admite_texto_con_punto_y_coma(conexion_prueba, adm):
    sql = ("INSERT INTO areas (id_area, nombre, descripcion) VALUES (1, 'Instrumentacion y tablero', "
           "'Uno; dos'' tres') ON CONFLICT (id_area) DO UPDATE SET nombre = EXCLUDED.nombre, "
           "descripcion = EXCLUDED.descripcion;")
    assert adm.restaurar_conocimiento(sql) == 1
    assert AreaDAO(conexion_prueba).obtener(1).descripcion == "Uno; dos' tres"
