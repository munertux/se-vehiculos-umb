# -*- coding: utf-8 -*-
"""Vehiculos, consulta (diagnostico con vehiculo, testigos y OBD) e historial."""
import pytest

from apoyo_bd import conexion_prueba, unico, placa_unica  # noqa: F401 (fixture)
from app.datos.dao.atencion_dao import AtencionDAO
from app.logica import servicio_diagnostico as modulo_diag
from app.logica.errores import ErrorNegocio
from app.logica.servicio_administracion import ServicioAdministracion
from app.logica.servicio_autenticacion import ServicioAutenticacion
from app.logica.servicio_diagnostico import ServicioDiagnostico
from app.logica.servicio_historial import ServicioHistorial
from app.logica.servicio_vehiculos import ServicioVehiculos


def nuevo_consultante(conexion):
    nombre = unico("cons")
    ServicioAdministracion(conexion).crear_usuario(nombre, "Clave2026z", "consultante", "Consultante Prueba")
    return ServicioAutenticacion(conexion).autenticar(nombre, "Clave2026z")["id_consultante"]


def datos_vehiculo(**extra):
    d = {"placa": placa_unica(), "marca": "Chevrolet", "modelo": "Spark", "combustible": "gasolina",
         "transmision": "manual", "anio": 2018, "kilometraje": "45.000"}
    d.update(extra)
    return d


@pytest.fixture
def ctx(conexion_prueba):
    id_c = nuevo_consultante(conexion_prueba)
    sv = ServicioVehiculos(conexion_prueba)
    id_v = sv.crear(id_c, datos_vehiculo())
    return {"id_c": id_c, "id_v": id_v, "sv": sv, "diag": ServicioDiagnostico(conexion_prueba),
            "hist": ServicioHistorial(conexion_prueba)}


# ------------------------------------------------------------ vehiculos
def test_vehiculos_crud(ctx):
    sv, id_c, id_v = ctx["sv"], ctx["id_c"], ctx["id_v"]
    v = sv.obtener(id_c, id_v)
    assert v["kilometraje"] == 45000 and v["combustible_etiqueta"] == "Gasolina"
    sv.actualizar(id_c, id_v, dict(v, kilometraje=50000, placa=v["placa"].lower()))
    assert sv.obtener(id_c, id_v)["kilometraje"] == 50000
    assert [x["id_vehiculo"] for x in sv.listar(id_c)] == [id_v]
    sv.desactivar(id_c, id_v)
    assert sv.listar(id_c) == [] and len(sv.listar(id_c, incluir_inactivos=True)) == 1


def test_vehiculos_validaciones(conexion_prueba, ctx):
    sv, id_c, id_v = ctx["sv"], ctx["id_c"], ctx["id_v"]
    assert sv.opciones() == {"combustible": ["gasolina", "diesel", "gas", "hibrido", "electrico"],
                             "transmision": ["manual", "automatica", "cvt"]}
    with pytest.raises(ErrorNegocio, match="placa"):
        sv.crear(id_c, datos_vehiculo(placa="A-1"))
    with pytest.raises(ErrorNegocio, match="combustible"):
        sv.crear(id_c, datos_vehiculo(combustible="carbon"))
    with pytest.raises(ErrorNegocio, match="anio"):
        sv.crear(id_c, datos_vehiculo(anio=1900))
    with pytest.raises(ErrorNegocio, match="marca"):
        sv.crear(id_c, datos_vehiculo(marca=" "))
    placa = sv.obtener(id_c, id_v)["placa"]
    with pytest.raises(ErrorNegocio, match="Ya existe"):
        sv.crear(id_c, datos_vehiculo(placa=placa))
    otro = nuevo_consultante(conexion_prueba)
    with pytest.raises(ErrorNegocio, match="no pertenece"):
        sv.obtener(otro, id_v)
    with pytest.raises(ErrorNegocio, match="no pertenece"):
        sv.desactivar(otro, id_v)


# ------------------------------------------------------------ consulta
def responder_hasta_el_final(diag, id_atencion, pregunta, afirmar):
    while True:
        r = diag.responder(id_atencion, pregunta["id_pregunta"], "si" if pregunta["id_pregunta"] in afirmar else "no")
        if r["estado"] == "finalizado":
            return r["resultado"]
        pregunta = r["pregunta"]


def test_consulta_completa_guarda_vehiculo_testigos_obd_y_reglas(conexion_prueba, ctx):
    diag = ctx["diag"]
    id_at, pregunta = diag.iniciar(9, id_vehiculo=ctx["id_v"], testigos=["Bateria o sistema de carga", "ABS"],
                                   codigos_obd="p0562; U0100", id_consultante=ctx["id_c"])
    assert pregunta["es_entrada"] and pregunta["id_area"] == 9
    resultado = responder_hasta_el_final(diag, id_at, pregunta, {9, 26})
    lider = resultado[0]
    assert lider["nombre"] == "Conexiones de bateria flojas, sulfatadas o corroidas"
    assert lider["reglas_activadas"] == ["R02"] and lider["posicion"] == 1

    dao = AtencionDAO(conexion_prueba)
    a = dao.obtener(id_at)
    assert a.estado == "finalizada" and a.id_vehiculo == ctx["id_v"] and a.id_consultante == ctx["id_c"]
    assert a.testigos_tablero == "Bateria o sistema de carga, ABS" and a.codigos_obd == "P0562, U0100"
    assert dao.diagnostico(id_at)[0]["reglas_activadas"] == "R02"

    # finalizar de nuevo devuelve lo guardado
    assert diag.finalizar(id_at)[0]["reglas_activadas"] == ["R02"]

    diag.confirmar_falla(id_at, lider["id_hipotesis"], "Se cambiaron los bornes")
    with pytest.raises(ErrorNegocio):
        diag.confirmar_falla(id_at, 999999)
    assert diag.pertenece(id_at, ctx["id_c"]) and not diag.pertenece(id_at, -1)

    # historial y detalle
    h = ctx["hist"].historial(ctx["id_c"])
    assert h[0]["id_atencion"] == id_at and h[0]["hipotesis_principal"] == lider["nombre"]
    assert h[0]["probabilidad"] == lider["probabilidad"] and h[0]["estado"] == "finalizada"
    d = ctx["hist"].detalle(ctx["id_c"], id_at)
    assert d["vehiculo"]["id_vehiculo"] == ctx["id_v"] and d["area"] == "Arranque del vehiculo"
    assert d["testigos"] == ["Bateria o sistema de carga", "ABS"] and d["codigos_obd"] == ["P0562", "U0100"]
    assert [r["orden"] for r in d["respuestas"]] == list(range(1, len(d["respuestas"]) + 1))
    assert d["respuestas"][0]["respuesta_etiqueta"] == "Si"
    assert 1 <= len(d["hipotesis"]) <= 5 and d["hipotesis"][0]["nivel_atencion"]
    assert d["reglas"][0]["codigo"] == "R02" and d["recomendacion"]
    assert d["falla_confirmada"]["id_hipotesis"] == lider["id_hipotesis"]
    assert d["falla_confirmada"]["observacion"] == "Se cambiaron los bornes"
    with pytest.raises(ErrorNegocio):
        ctx["hist"].detalle(nuevo_consultante(conexion_prueba), id_at)


def test_iniciar_validaciones(conexion_prueba, ctx):
    diag = ctx["diag"]
    with pytest.raises(ErrorNegocio, match="OBD"):
        diag.iniciar(9, codigos_obd="XYZ")
    with pytest.raises(ErrorNegocio, match="area"):
        diag.iniciar(99999)
    with pytest.raises(ErrorNegocio, match="no pertenece"):
        diag.iniciar(9, id_vehiculo=ctx["id_v"], id_consultante=nuevo_consultante(conexion_prueba))
    with pytest.raises(ErrorNegocio, match="no valida"):
        id_at, p = diag.iniciar(9)
        diag.responder(id_at, p["id_pregunta"], "tal_vez")


def test_compatibilidad_constructor_antiguo(conexion_prueba):
    from app.datos.repositorio_atencion import RepositorioAtencion
    from app.datos.repositorio_conocimiento import RepositorioConocimiento
    diag = ServicioDiagnostico(RepositorioConocimiento(conexion_prueba), RepositorioAtencion(conexion_prueba))
    id_at, pregunta = diag.iniciar(9)
    assert pregunta["id_pregunta"] == 9
    assert diag.responder(id_at, 9, "si")["estado"] in ("en_curso", "finalizado")


def test_reconstruye_la_sesion_si_se_pierde_la_memoria(conexion_prueba, ctx):
    diag = ctx["diag"]
    id_at, p = diag.iniciar(9, id_vehiculo=ctx["id_v"])
    r = diag.responder(id_at, p["id_pregunta"], "si")
    esperado = r["pregunta"]["id_pregunta"]
    modulo_diag._SESIONES.clear()                       # simula reinicio del servidor
    otro = ServicioDiagnostico(conexion_prueba)
    assert otro.estado(id_at)["pregunta"]["id_pregunta"] == esperado
    resultado = responder_hasta_el_final(otro, id_at, r["pregunta"], {26})
    assert resultado[0]["reglas_activadas"] == ["R02"]
    assert otro.estado(id_at)["estado"] == "finalizado"


def test_testigos_disponibles():
    assert "ABS" in ServicioDiagnostico.testigos_disponibles()
