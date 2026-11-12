# -*- coding: utf-8 -*-
"""Pruebas de los DAO contra PostgreSQL (esquema aislado se_pruebas)."""
from datetime import datetime
from decimal import Decimal

import pytest

from apoyo_bd import conexion_prueba, unico, placa_unica  # noqa: F401 (fixture)
from app.datos.dao import (AreaDAO, AtencionDAO, BitacoraDAO, ConsultanteDAO, EmpleadoDAO, HipotesisDAO,
                           PreguntaDAO, ReglaDAO, RespaldoDAO, RolDAO, UsuarioDAO, VehiculoDAO)
from app.datos.dao.respaldo_dao import literal_sql
from app.logica.entidades import Usuario, Vehiculo, Regla


@pytest.fixture
def consultante(conexion_prueba):
    id_u = UsuarioDAO(conexion_prueba).crear(1, unico("dao"), "hash-x")
    id_c = ConsultanteDAO(conexion_prueba).crear(id_u, "Persona de prueba", "p@x.co", "300")
    return id_u, id_c


def test_roles_semilla(conexion_prueba):
    roles = RolDAO(conexion_prueba).listar()
    assert [(r.id_rol, r.clave) for r in roles] == [(1, "consultante"), (2, "ingeniero"), (3, "administrador")]


def test_usuario_crud_y_bloqueo(conexion_prueba):
    dao = UsuarioDAO(conexion_prueba)
    nombre = unico("usr")
    id_u = dao.crear(2, nombre, "hash-1")
    u = dao.obtener_por_nombre(nombre.upper())   # sin distinguir mayusculas
    assert isinstance(u, Usuario) and u.id_usuario == id_u and u.rol == "ingeniero"
    assert u.estado == "activo" and u.intentos_fallidos == 0 and not u.bloqueo_vigente

    for i in range(1, 3):
        r = dao.registrar_intento_fallido(id_u, 3, 15)
        assert r["intentos_fallidos"] == i and r["estado"] == "activo"
    r = dao.registrar_intento_fallido(id_u, 3, 15)
    assert r["estado"] == "bloqueado" and r["bloqueado_hasta"] is not None
    u = dao.obtener(id_u)
    assert u.bloqueo_vigente and 14 <= u.minutos_restantes <= 15

    assert dao.liberar_bloqueo_vencido(id_u) == 0      # aun vigente
    dao.fijar_bloqueo_hasta(id_u, -1)
    assert dao.liberar_bloqueo_vencido(id_u) == 1
    u = dao.obtener(id_u)
    assert u.estado == "activo" and u.intentos_fallidos == 0 and u.bloqueado_hasta is None

    dao.registrar_acceso(id_u)
    assert dao.obtener(id_u).ultimo_acceso is not None
    dao.cambiar_hash(id_u, "hash-2")
    assert dao.obtener(id_u).contrasena_hash == "hash-2"
    assert dao.eliminar(id_u) == 1 and dao.obtener(id_u) is None


def test_perfiles_y_listado(conexion_prueba, consultante):
    id_u, id_c = consultante
    assert ConsultanteDAO(conexion_prueba).obtener_por_usuario(id_u).id_consultante == id_c
    id_ue = UsuarioDAO(conexion_prueba).crear(3, unico("emp"), "h")
    id_e = EmpleadoDAO(conexion_prueba).crear(id_ue, "Empleado", "Administrador")
    EmpleadoDAO(conexion_prueba).actualizar(id_e, {"cargo": "Jefe", "otro": 1})
    assert EmpleadoDAO(conexion_prueba).obtener(id_e).cargo == "Jefe"
    filas = {f["id_usuario"]: f for f in UsuarioDAO(conexion_prueba).listar_detallado()}
    assert filas[id_u]["id_consultante"] == id_c and filas[id_ue]["id_empleado"] == id_e


def test_vehiculo_crud(conexion_prueba, consultante):
    _, id_c = consultante
    dao = VehiculoDAO(conexion_prueba)
    placa = placa_unica()
    id_v = dao.crear(id_c, {"placa": placa, "marca": "Mazda", "modelo": "2", "combustible": "gasolina",
                            "transmision": "manual", "anio": 2019, "kilometraje": 1000})
    v = dao.obtener(id_v)
    assert isinstance(v, Vehiculo) and v.activo and v.descripcion == f"{placa} - Mazda 2"
    assert dao.buscar_placa_activa(placa.lower()).id_vehiculo == id_v
    assert dao.buscar_placa_activa(placa, excluir_id=id_v) is None
    dao.actualizar(id_v, {"kilometraje": 2000})
    assert dao.obtener(id_v).kilometraje == 2000
    dao.cambiar_activo(id_v, False)
    assert dao.listar_por_consultante(id_c) == []
    assert len(dao.listar_por_consultante(id_c, incluir_inactivos=True)) == 1


def test_check_de_combustible(conexion_prueba, consultante):
    _, id_c = consultante
    with pytest.raises(Exception):
        VehiculoDAO(conexion_prueba).crear(id_c, {"placa": "AAA111", "marca": "x", "modelo": "y",
                                                  "combustible": "carbon", "transmision": "manual"})


def test_transaccion_revierte_todo(conexion_prueba):
    nombre = unico("tx")
    with pytest.raises(RuntimeError):
        with conexion_prueba.transaccion() as tx:
            UsuarioDAO(conexion_prueba).crear(1, nombre, "h", tx=tx)
            raise RuntimeError("falla simulada")
    assert UsuarioDAO(conexion_prueba).obtener_por_nombre(nombre) is None


def test_conocimiento_dao(conexion_prueba):
    areas, preguntas, hipotesis, reglas = (AreaDAO(conexion_prueba), PreguntaDAO(conexion_prueba),
                                           HipotesisDAO(conexion_prueba), ReglaDAO(conexion_prueba))
    assert len(areas.listar()) >= 24
    con = {a["id_area"]: a for a in areas.listar_con_conteos()}
    assert con[9]["tiene_entrada"] and con[9]["reglas"] >= 1
    assert preguntas.entrada_del_area(9).es_entrada
    assert all(p["id_area"] == 9 for p in preguntas.listar(9))
    r2 = reglas.obtener_por_codigo("r02")
    assert isinstance(r2, Regla) and r2.codigo == "R02" and isinstance(r2.peso, float)
    assert reglas.codigos([r2.id_regla]) == {r2.id_regla: "R02"}
    assert reglas.siguiente_codigo().startswith("R")
    assert reglas.existe_activa(r2.id_pregunta, r2.id_hipotesis)
    assert hipotesis.areas_de(r2.id_hipotesis) == [r2.id_area]
    assert reglas.obtener_detalle(r2.id_regla)["hipotesis"] == hipotesis.obtener(r2.id_hipotesis).nombre

    id_a = areas.crear(unico("Area "), "desc")
    assert areas.obtener(id_a).id_area == id_a
    assert id_a in [a.id_area for a in areas.sin_pregunta_de_entrada()]
    id_p = preguntas.crear({"id_area": id_a, "enunciado": "Entrada?", "sintoma_evaluado": "s", "es_entrada": True})
    assert id_a not in [a.id_area for a in areas.sin_pregunta_de_entrada()]
    id_p2 = preguntas.crear({"id_area": id_a, "enunciado": "Especifica?", "sintoma_evaluado": "s"})
    id_h = hipotesis.crear(unico("Hip "), "")
    codigo = reglas.siguiente_codigo()
    id_r = reglas.crear({"id_pregunta": id_p2, "id_hipotesis": id_h, "id_area": id_a,
                         "nivel_atencion": "Revision proxima", "gravedad": 2, "recomendacion": "x", "peso": 1.0})
    r = reglas.obtener(id_r)
    assert r.codigo == codigo and r.version == 1
    reglas.actualizar(id_r, {"recomendacion": "y"})
    assert reglas.obtener(id_r).version == 2
    reglas.cambiar_activa(id_r, False)
    assert id_h in [h.id_hipotesis for h in hipotesis.sin_regla_activa()]
    assert preguntas.obtener(id_p).id_pregunta == id_p


def test_atencion_y_bitacora(conexion_prueba, consultante):
    _, id_c = consultante
    dao = AtencionDAO(conexion_prueba)
    id_a = dao.abrir(9, testigos="ABS", codigos_obd="P0300", id_consultante=id_c)
    a = dao.obtener(id_a)
    assert a.estado == "en_curso" and a.codigos_obd == "P0300"
    assert dao.propietario(id_a) == id_c
    dao.guardar_respuesta(id_a, 9, "si", 1.0, 1)
    dao.guardar_respuesta(id_a, 26, "no", 0.0, 2)
    assert [r["id_pregunta"] for r in dao.respuestas(id_a)] == [9, 26]
    assert dao.historial_por_consultante(id_c)[0]["id_atencion"] == id_a

    b = BitacoraDAO(conexion_prueba)
    id_b = b.registrar("regla", 1, "modificar", None, id_regla=1, detalle="prueba")
    ultimo = b.listar(5)[0]
    assert ultimo["id_bitacora"] == id_b and ultimo["codigo_regla"] == "R01"
    assert b.por_registro("regla", 1)[-1].detalle == "prueba"
    with pytest.raises(Exception):
        b.registrar("regla", 1, "borrar")      # CHECK de accion


def test_literal_sql():
    assert literal_sql(None) == "NULL"
    assert literal_sql(True) == "TRUE"
    assert literal_sql(Decimal("1.20")) == "1.20"
    assert literal_sql("O'Brien") == "'O''Brien'"
    assert literal_sql("a\nb") == "E'a\\nb'"
    assert literal_sql(datetime(2026, 1, 2, 3, 4, 5)) == "'2026-01-02 03:04:05'"


def test_respaldo_dao(conexion_prueba):
    dao = RespaldoDAO(conexion_prueba)
    assert {"areas", "reglas", "usuario", "bitacora_conocimiento"} <= dao.tablas_existentes()
    assert dao.llave_primaria("atencion_respuesta") == ["id_atencion", "id_pregunta"]
    assert dao.columnas_serial("usuario") == ["id_usuario"]
    sentencias = dao.sentencias_insert("areas", actualizar_si_existe=True)
    assert len(sentencias) >= 24 and all("ON CONFLICT (id_area) DO UPDATE" in s for s in sentencias)
