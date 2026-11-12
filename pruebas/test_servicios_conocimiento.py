# -*- coding: utf-8 -*-
"""Mantenimiento del conocimiento con bitacora, granulos y validacion."""
import pytest

from apoyo_bd import conexion_prueba, unico  # noqa: F401 (fixture)
from app.datos.dao.bitacora_dao import BitacoraDAO
from app.logica.errores import ErrorNegocio
from app.logica.servicio_administracion import ServicioAdministracion
from app.logica.servicio_autenticacion import ServicioAutenticacion
from app.logica.servicio_conocimiento import ServicioConocimiento


@pytest.fixture
def ing(conexion_prueba):
    nombre = unico("ing")
    ServicioAdministracion(conexion_prueba).crear_usuario(nombre, "Clave2026z", "ingeniero", "Ingeniera Prueba")
    return ServicioAutenticacion(conexion_prueba).autenticar(nombre, "Clave2026z")["id_empleado"]


@pytest.fixture
def sc(conexion_prueba):
    return ServicioConocimiento(conexion_prueba)


def bitacora(conexion, entidad, id_registro):
    return [(b.accion, b.id_empleado) for b in BitacoraDAO(conexion).por_registro(entidad, id_registro)]


def test_resumen_y_listados(sc):
    r = sc.resumen()
    assert r["areas"] >= 24 and r["reglas"] >= 68 and r["hipotesis"] >= 68
    assert len(sc.listar_areas()) == r["areas"]
    assert all(p["id_area"] == 2 for p in sc.listar_preguntas(2))
    assert all(x["id_area"] == 9 for x in sc.listar_reglas(9))
    assert sc.obtener_regla(sc.listar_reglas(9)[0]["id_regla"])["area"] == "Arranque del vehiculo"
    assert "Revision prioritaria" in sc.opciones_regla()["niveles_atencion"]


def test_granulos_directo_y_de_rama(sc):
    g = sc.granulos_por_hipotesis(2)    # R02, area 9
    assert g["hipotesis"]["id_hipotesis"] == 2 and g["area"]["id_area"] == 9
    tipos = {x["tipo"]: x for x in g["granulos"]}
    assert tipos["rama"]["id_pregunta"] == 9 and tipos["rama"]["peso"] == 0.4
    assert tipos["rama"]["codigo_regla"] is None
    assert tipos["directo"]["codigo_regla"] == "R02" and tipos["directo"]["id_pregunta"] == 26
    assert tipos["directo"]["peso"] == 1.0 and tipos["directo"]["nivel_atencion"] and tipos["directo"]["recomendacion"]
    claves = {"tipo", "id_pregunta", "enunciado", "codigo_regla", "peso", "nivel_atencion", "recomendacion"}
    assert all(claves <= set(x) for x in g["granulos"])
    with pytest.raises(ErrorNegocio):
        sc.granulos_por_hipotesis(999999)


def test_ciclo_completo_con_bitacora(conexion_prueba, sc, ing):
    id_a = sc.crear_area({"nombre": unico("Area "), "descripcion": "Nueva"}, ing)
    assert bitacora(conexion_prueba, "area", id_a) == [("crear", ing)]
    assert any(p["tipo"] == "area_sin_entrada" and p["id"] == id_a for p in sc.validar())
    sc.actualizar_area(id_a, {"nombre": unico("Area "), "descripcion": "Cambiada"}, ing)

    id_e = sc.crear_pregunta({"id_area": id_a, "enunciado": "Hay un problema nuevo?", "sintoma_evaluado": "general",
                              "es_entrada": "on"}, ing)
    assert not any(p["tipo"] == "area_sin_entrada" and p["id"] == id_a for p in sc.validar())
    with pytest.raises(ErrorNegocio, match="entrada activa"):
        sc.crear_pregunta({"id_area": id_a, "enunciado": "Otra entrada?", "sintoma_evaluado": "g",
                           "es_entrada": True}, ing)
    with pytest.raises(ErrorNegocio, match="entrada"):
        sc.cambiar_estado_pregunta(id_e, False, ing)
    id_p = sc.crear_pregunta({"id_area": id_a, "enunciado": "Suena un pito al frenar?", "sintoma_evaluado": "pito"},
                             ing)

    id_h = sc.crear_hipotesis({"nombre": unico("Hipotesis "), "descripcion": "x"}, ing)
    assert any(p["tipo"] == "hipotesis_sin_regla" and p["id"] == id_h for p in sc.validar())
    with pytest.raises(ErrorNegocio, match="especificas"):
        sc.crear_regla({"id_pregunta": id_e, "id_hipotesis": id_h, "nivel_atencion": "Revision proxima",
                        "recomendacion": "x"}, ing)
    with pytest.raises(ErrorNegocio, match="nivel"):
        sc.crear_regla({"id_pregunta": id_p, "id_hipotesis": id_h, "nivel_atencion": "Urgente",
                        "recomendacion": "x"}, ing)
    id_r = sc.crear_regla({"id_pregunta": id_p, "id_hipotesis": id_h, "nivel_atencion": "Revision prioritaria",
                           "recomendacion": "Revisar pastillas"}, ing)
    regla = sc.obtener_regla(id_r)
    assert regla["gravedad"] == 3 and regla["peso"] == 1.1 and regla["version"] == 1 and regla["id_area"] == id_a
    assert regla["codigo"].startswith("R")
    with pytest.raises(ErrorNegocio, match="Ya existe"):
        sc.crear_regla({"id_pregunta": id_p, "id_hipotesis": id_h, "nivel_atencion": "Revision proxima",
                        "recomendacion": "dup"}, ing)

    sc.actualizar_regla(id_r, {"recomendacion": "Cambiar pastillas", "peso": "1.3"}, ing)
    regla = sc.obtener_regla(id_r)
    assert regla["version"] == 2 and regla["peso"] == 1.3 and regla["recomendacion"] == "Cambiar pastillas"

    g = sc.granulos_por_hipotesis(id_h)
    assert [(x["tipo"], x["id_pregunta"]) for x in g["granulos"]] == [("rama", id_e), ("directo", id_p)]

    sc.cambiar_estado_regla(id_r, False, ing)
    assert sc.obtener_regla(id_r)["activa"] is False
    sc.cambiar_estado_regla(id_r, True, ing)
    sc.cambiar_estado_pregunta(id_p, False, ing)
    assert any(p["tipo"] == "regla_sin_pregunta_activa" and p["id"] == id_r for p in sc.validar())
    sc.cambiar_estado_pregunta(id_p, True, ing)
    sc.actualizar_hipotesis(id_h, {"nombre": unico("Hipotesis "), "descripcion": "y"}, ing)

    assert bitacora(conexion_prueba, "regla", id_r) == [("crear", ing), ("modificar", ing), ("desactivar", ing),
                                                         ("activar", ing)]
    assert [a for a, _ in bitacora(conexion_prueba, "pregunta", id_p)] == ["crear", "desactivar", "activar"]
    assert [a for a, _ in bitacora(conexion_prueba, "hipotesis", id_h)] == ["crear", "modificar"]
    assert [a for a, _ in bitacora(conexion_prueba, "area", id_a)] == ["crear", "modificar"]
    auditoria = ServicioAdministracion(conexion_prueba).auditoria(10)
    assert auditoria[0]["empleado"] == "Ingeniera Prueba"


def test_validaciones_de_datos(sc, ing):
    with pytest.raises(ErrorNegocio):
        sc.crear_area({"nombre": ""}, ing)
    with pytest.raises(ErrorNegocio, match="Ya existe"):
        sc.crear_area({"nombre": "Frenos"}, ing)
    with pytest.raises(ErrorNegocio):
        sc.crear_pregunta({"id_area": 999999, "enunciado": "Algo raro?", "sintoma_evaluado": "x"}, ing)
    with pytest.raises(ErrorNegocio):
        sc.crear_hipotesis({"nombre": "Pastillas de freno desgastadas"}, ing)
    with pytest.raises(ErrorNegocio):
        sc.actualizar_regla(999999, {"recomendacion": "x"}, ing)
