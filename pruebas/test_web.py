# -*- coding: utf-8 -*-
"""Pruebas de la capa de presentacion (blueprints Flask) con el cliente de
pruebas y servicios simulados: no necesitan base de datos."""
import time
from datetime import datetime

import pytest

from app.logica.errores import ErrorNegocio
from app.web.presentacion import clase_nivel, porcentaje, tildes
from main import crear_app

CLAVE = "Clave123"
SESIONES = {
    "consultante1": {"id_usuario": 1, "nombre_usuario": "consultante1", "rol": "consultante",
                     "nombres": "Ana Pérez", "id_consultante": 10, "id_empleado": None},
    "ingeniero1": {"id_usuario": 2, "nombre_usuario": "ingeniero1", "rol": "ingeniero",
                   "nombres": "Iván Ríos", "id_consultante": None, "id_empleado": 20},
    "admin": {"id_usuario": 3, "nombre_usuario": "admin", "rol": "administrador",
              "nombres": "Administrador", "id_consultante": None, "id_empleado": 30},
}
HIPOTESIS = [
    {"posicion": 1, "id_hipotesis": 5, "nombre": "Falla de la bomba de agua", "descripcion": "",
     "puntaje": 2.1, "probabilidad": 61.3, "nivel_atencion": "No debe seguir usandose",
     "recomendacion": "Revisar el nivel de refrigerante", "advertencia": True, "sintoma_confirmado": True,
     "reglas_activadas": ["R10", "R11"], "falla_confirmada": False, "observacion": None},
    {"posicion": 2, "id_hipotesis": 6, "nombre": "Termostato pegado", "descripcion": "",
     "puntaje": 1.0, "probabilidad": 38.7, "nivel_atencion": "Revision proxima",
     "recomendacion": "Revisar el termostato", "advertencia": False, "sintoma_confirmado": False,
     "reglas_activadas": [], "falla_confirmada": False, "observacion": None},
]
PREGUNTA = {"id_pregunta": 7, "id_area": 1, "enunciado": "¿El motor se calienta?", "es_entrada": True,
            "opciones": [{"clave": k, "etiqueta": v} for k, v in
                         (("si", "Si"), ("probablemente_si", "Probablemente si"), ("no_se", "No se"),
                          ("probablemente_no", "Probablemente no"), ("no", "No"))]}


class Auth:
    def autenticar(self, usuario, clave):
        if usuario in SESIONES and clave == CLAVE:
            return dict(SESIONES[usuario])
        raise ErrorNegocio("Usuario o contrasena incorrectos.")

    def cambiar_clave(self, id_usuario, actual, nueva):
        if actual != CLAVE:
            raise ErrorNegocio("La contrasena actual no es correcta.")


class Vehiculos:
    def __init__(self):
        self.creados = []

    def _v(self):
        return {"id_vehiculo": 100, "id_consultante": 10, "placa": "ABC123", "marca": "Mazda", "modelo": "3",
                "combustible": "gasolina", "transmision": "manual", "anio": 2018, "kilometraje": 45000,
                "activo": True, "combustible_etiqueta": "Gasolina", "transmision_etiqueta": "Manual"}

    def listar(self, id_consultante, incluir_inactivos=False):
        return [self._v()]

    def obtener(self, id_consultante, id_vehiculo):
        if id_vehiculo != 100:
            raise ErrorNegocio("El vehiculo no existe o no pertenece al consultante.")
        return self._v()

    def crear(self, id_consultante, datos):
        if not datos.get("placa"):
            raise ErrorNegocio("La placa no es valida (ejemplo: ABC123).")
        self.creados.append(datos)
        return 101

    def actualizar(self, id_consultante, id_vehiculo, datos):
        pass

    def desactivar(self, id_consultante, id_vehiculo):
        pass

    def reactivar(self, id_consultante, id_vehiculo):
        pass

    def opciones_etiquetadas(self):
        return {"combustible": [{"valor": "gasolina", "etiqueta": "Gasolina"}],
                "transmision": [{"valor": "manual", "etiqueta": "Manual"}]}


class Diagnostico:
    def __init__(self):
        self.confirmadas = []

    def areas(self):
        return [{"id_area": 1, "nombre": "Refrigeracion del motor", "descripcion": ""}]

    def testigos_disponibles(self):
        return ["Temperatura del refrigerante", "ABS"]

    def iniciar(self, id_area, id_vehiculo=None, testigos=None, codigos_obd=None, id_consultante=None):
        return 500, dict(PREGUNTA)

    def pertenece(self, id_atencion, id_consultante):
        return id_atencion == 500 and id_consultante == 10

    def estado(self, id_atencion):
        return {"estado": "en_curso", "pregunta": dict(PREGUNTA)}

    def responder(self, id_atencion, id_pregunta, respuesta):
        return {"estado": "finalizado", "resultado": [dict(h) for h in HIPOTESIS]}

    def finalizar(self, id_atencion):
        return [dict(h) for h in HIPOTESIS]

    def confirmar_falla(self, id_atencion, id_hipotesis, observacion=None):
        self.confirmadas.append((id_atencion, id_hipotesis, observacion))


class Historial:
    def historial(self, id_consultante):
        return [{"id_atencion": 500, "fecha": datetime(2026, 11, 10, 9, 30), "fecha_fin": None,
                 "id_vehiculo": 100, "vehiculo": "ABC123 - Mazda 3", "placa": "ABC123", "id_area": 1,
                 "area": "Refrigeracion del motor", "estado": "finalizada", "estado_etiqueta": "Finalizada",
                 "id_hipotesis": 5, "hipotesis_principal": "Falla de la bomba de agua", "probabilidad": 61.3,
                 "falla_confirmada": False}]

    def detalle(self, id_consultante, id_atencion):
        if id_consultante != 10 or id_atencion != 500:
            raise ErrorNegocio("La consulta no existe o no pertenece al consultante.")
        return {"id_atencion": 500, "fecha_inicio": datetime(2026, 11, 10, 9, 30),
                "fecha_fin": datetime(2026, 11, 10, 9, 34), "estado": "finalizada",
                "vehiculo": Vehiculos()._v(), "id_area": 1, "area": "Refrigeracion del motor",
                "testigos": ["Temperatura del refrigerante"], "codigos_obd": ["P0217"],
                "respuestas": [{"orden": 1, "id_pregunta": 7, "enunciado": "¿El motor se calienta?",
                                "es_entrada": True, "respuesta": "si", "respuesta_etiqueta": "Si", "certeza": 1.0}],
                "hipotesis": [dict(h) for h in HIPOTESIS], "recomendacion": "", "nivel_atencion": "",
                "advertencia": True, "reglas": [{"codigo": "R10", "id_hipotesis": 5,
                                                 "hipotesis": "Falla de la bomba de agua", "version": 2,
                                                 "nivel_atencion": "No debe seguir usandose"}],
                "falla_confirmada": None}


class Conocimiento:
    def __init__(self):
        self.llamadas = []

    def resumen(self):
        return {"areas": 1, "preguntas": 2, "preguntas_activas": 2, "hipotesis": 2, "reglas": 1,
                "reglas_activas": 1, "atenciones": 1, "problemas": 1}

    def validar(self):
        return [{"tipo": "hipotesis_sin_regla", "entidad": "hipotesis", "id": 6,
                 "mensaje": "La hipotesis 'Termostato pegado' no tiene ninguna regla activa."}]

    def opciones_regla(self):
        return {"niveles_atencion": ["Atencion preventiva", "Revision proxima"], "gravedades": [1, 2, 3, 4]}

    def listar_areas(self):
        return [{"id_area": 1, "nombre": "Refrigeracion del motor", "descripcion": "", "preguntas": 2,
                 "preguntas_activas": 2, "reglas": 1, "reglas_activas": 1, "tiene_entrada": True}]

    def listar_preguntas(self, id_area=None):
        return [{"id_pregunta": 7, "id_area": 1, "area": "Refrigeracion del motor", "enunciado": "¿Se calienta?",
                 "sintoma_evaluado": "Temperatura", "es_entrada": True, "activa": True, "reglas": 0},
                {"id_pregunta": 8, "id_area": 1, "area": "Refrigeracion del motor", "enunciado": "¿Pierde liquido?",
                 "sintoma_evaluado": "Fuga", "es_entrada": False, "activa": True, "reglas": 1}]

    def listar_hipotesis(self):
        return [{"id_hipotesis": 5, "nombre": "Falla de la bomba de agua", "descripcion": "", "reglas": 1,
                 "reglas_activas": 1, "id_area": 1, "area": "Refrigeracion del motor"}]

    def listar_reglas(self, id_area=None):
        return [{"id_regla": 10, "codigo": "R10", "id_pregunta": 8, "enunciado": "¿Pierde liquido?",
                 "pregunta_activa": True, "id_hipotesis": 5, "hipotesis": "Falla de la bomba de agua",
                 "id_area": 1, "area": "Refrigeracion del motor", "nivel_atencion": "Revision prioritaria",
                 "gravedad": 3, "recomendacion": "Revisar", "peso": 1.1, "version": 2, "activa": True}]

    def granulos_por_hipotesis(self, id_hipotesis):
        if id_hipotesis != 5:
            raise ErrorNegocio("La hipotesis no existe.")
        return {"hipotesis": {"id_hipotesis": 5, "nombre": "Falla de la bomba de agua", "descripcion": ""},
                "area": {"id_area": 1, "nombre": "Refrigeracion del motor"},
                "granulos": [{"tipo": "rama", "id_pregunta": 7, "enunciado": "¿Se calienta?", "codigo_regla": None,
                              "peso": 0.4, "nivel_atencion": None, "recomendacion": None, "activa": True},
                             {"tipo": "directo", "id_pregunta": 8, "enunciado": "¿Pierde liquido?",
                              "codigo_regla": "R10", "peso": 1.1, "nivel_atencion": "Revision prioritaria",
                              "recomendacion": "Revisar", "activa": True}]}

    def __getattr__(self, nombre):  # crear_*, actualizar_*, cambiar_estado_*
        def metodo(*args, **kwargs):
            self.llamadas.append((nombre, args))
            if args and isinstance(args[0], dict) and args[0].get("nombre") == "duplicada":
                raise ErrorNegocio("Ya existe un area con ese nombre.")
            return 99
        return metodo


class Administracion:
    def __init__(self):
        self.llamadas = []

    def listar_usuarios(self):
        return [dict(SESIONES[u], estado="activo", intentos_fallidos=0, bloqueado_hasta=None,
                     bloqueo_vigente=False, ultimo_acceso=datetime(2026, 11, 11, 8, 0), correo=None, cargo=None)
                for u in SESIONES]

    def auditoria(self, limite=200):
        return [{"id_bitacora": 1, "fecha": datetime(2026, 11, 11, 8, 0), "entidad": "regla", "id_registro": 10,
                 "accion": "modificar", "detalle": "R10 v2", "empleado": "Iván Ríos",
                 "nombre_usuario": "ingeniero1", "codigo_regla": "R10"}]

    def respaldo_sql(self):
        return "BEGIN;\nCOMMIT;\n"

    def __getattr__(self, nombre):
        def metodo(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))
            return 1
        return metodo


@pytest.fixture
def servicios():
    return {"autenticacion": Auth(), "vehiculos": Vehiculos(), "diagnostico": Diagnostico(),
            "historial": Historial(), "conocimiento": Conocimiento(), "administracion": Administracion()}


@pytest.fixture
def app(servicios):
    return crear_app(config={"TESTING": True, "SECRET_KEY": "prueba", "SESSION_COOKIE_SECURE": False},
                     servicios=servicios)


@pytest.fixture
def cliente(app):
    return app.test_client()


def token(cliente):
    """Token CSRF de la sesion del cliente (lo crea visitando /login)."""
    with cliente.session_transaction() as s:
        if "csrf" in s:
            return s["csrf"]
    cliente.get("/login")
    with cliente.session_transaction() as s:
        return s["csrf"]


def ingresar(cliente, usuario, clave=CLAVE):
    cliente.get("/login")
    return cliente.post("/login", data={"usuario": usuario, "clave": clave, "csrf_token": token(cliente)})


# ------------------------------------------------------------ autenticacion
def test_login_muestra_formulario_con_csrf(cliente):
    r = cliente.get("/login")
    assert r.status_code == 200
    assert 'name="csrf_token"' in r.get_data(as_text=True)


def test_sin_sesion_redirige_al_login(cliente):
    r = cliente.get("/panel")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_api_sin_sesion_responde_401(cliente):
    assert cliente.get("/api/areas").status_code == 401


def test_login_incorrecto(cliente):
    r = ingresar(cliente, "consultante1", "malaclave")
    assert r.status_code == 401
    assert "contraseña incorrectos" in r.get_data(as_text=True)


def test_login_sin_token_csrf_se_rechaza(cliente):
    cliente.get("/login")
    r = cliente.post("/login", data={"usuario": "consultante1", "clave": CLAVE})
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    with cliente.session_transaction() as s:
        assert "id_usuario" not in s


@pytest.mark.parametrize("usuario,panel", [("consultante1", "/panel"), ("ingeniero1", "/conocimiento"),
                                           ("admin", "/admin/usuarios")])
def test_login_guarda_sesion_y_redirige_al_panel_del_rol(cliente, usuario, panel):
    r = ingresar(cliente, usuario)
    assert r.status_code == 302 and r.headers["Location"].endswith(panel)
    with cliente.session_transaction() as s:
        for clave in ("id_usuario", "nombre_usuario", "rol", "nombres", "id_consultante", "id_empleado"):
            assert s[clave] == SESIONES[usuario][clave]
    assert cliente.get("/").headers["Location"].endswith(panel)


def test_logout_limpia_la_sesion(cliente):
    ingresar(cliente, "consultante1")
    cliente.post("/logout", data={"csrf_token": token(cliente)})
    with cliente.session_transaction() as s:
        assert "id_usuario" not in s


def test_sesion_expira_por_inactividad(cliente):
    ingresar(cliente, "consultante1")
    with cliente.session_transaction() as s:
        s["ultimo_uso"] = int(time.time()) - 16 * 60
    r = cliente.get("/panel")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    with cliente.session_transaction() as s:
        assert "id_usuario" not in s


def test_sesion_activa_se_refresca(cliente, app):
    ingresar(cliente, "consultante1")
    with cliente.session_transaction() as s:
        s["ultimo_uso"] = int(time.time()) - 14 * 60
    assert cliente.get("/panel").status_code == 200
    assert app.permanent_session_lifetime.total_seconds() == 15 * 60


def test_cabeceras_de_seguridad(cliente):
    r = cliente.get("/login")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "same-origin"


def test_redireccion_abierta_bloqueada(cliente):
    cliente.get("/login")
    r = cliente.post("/login?siguiente=//malicioso.com", data={"usuario": "admin", "clave": CLAVE,
                                                               "csrf_token": token(cliente)})
    assert r.headers["Location"].endswith("/admin/usuarios")


# ------------------------------------------------------------------ permisos
@pytest.mark.parametrize("ruta", ["/admin", "/admin/usuarios", "/admin/auditoria", "/admin/respaldos",
                                  "/conocimiento", "/conocimiento/reglas", "/conocimiento/hipotesis/5/granulos"])
def test_consultante_no_entra_a_rutas_de_otros_roles(cliente, ruta):
    ingresar(cliente, "consultante1")
    r = cliente.get(ruta)
    assert r.status_code == 403
    assert "Acceso no permitido" in r.get_data(as_text=True)


@pytest.mark.parametrize("ruta", ["/admin/usuarios", "/panel", "/vehiculos", "/consulta/nueva", "/historial"])
def test_ingeniero_no_entra_a_admin_ni_a_consultante(cliente, ruta):
    ingresar(cliente, "ingeniero1")
    assert cliente.get(ruta).status_code == 403


@pytest.mark.parametrize("ruta", ["/conocimiento", "/vehiculos", "/historial/500"])
def test_administrador_no_entra_a_conocimiento_ni_consultante(cliente, ruta):
    ingresar(cliente, "admin")
    assert cliente.get(ruta).status_code == 403


def test_api_de_consulta_solo_para_consultante(cliente):
    ingresar(cliente, "ingeniero1")
    r = cliente.post("/api/atenciones", json={"id_area": 1}, headers={"X-CSRF-Token": token(cliente)})
    assert r.status_code == 403 and r.is_json


# ------------------------------------------------------------- pantallas
@pytest.mark.parametrize("usuario,rutas", [
    ("consultante1", ["/panel", "/vehiculos", "/vehiculos?inactivos=1", "/vehiculos/nuevo",
                      "/vehiculos/100/editar", "/consulta/nueva", "/consulta/nueva?vehiculo=100",
                      "/consulta/500", "/historial", "/historial/500", "/historial/500/reporte", "/cuenta/clave"]),
    ("ingeniero1", ["/conocimiento", "/conocimiento/areas", "/conocimiento/preguntas?area=1",
                    "/conocimiento/hipotesis", "/conocimiento/reglas", "/conocimiento/reglas?editar=10",
                    "/conocimiento/reglas?nuevo=1", "/conocimiento/preguntas?editar=8",
                    "/conocimiento/hipotesis/5/granulos", "/cuenta/clave"]),
    ("admin", ["/admin/usuarios", "/admin/auditoria", "/admin/auditoria?entidad=regla", "/admin/respaldos"]),
])
def test_pantallas_de_cada_rol_se_dibujan(cliente, usuario, rutas):
    ingresar(cliente, usuario)
    for ruta in rutas:
        r = cliente.get(ruta)
        assert r.status_code == 200, ruta
        html = r.get_data(as_text=True)
        assert SESIONES[usuario]["nombres"] in html, ruta


def test_menu_segun_rol(cliente):
    ingresar(cliente, "consultante1")
    html = cliente.get("/panel").get_data(as_text=True)
    assert "Nueva consulta" in html and "Auditoría" not in html and "Reglas" not in html


def test_otro_consultante_no_ve_detalle_ajeno(cliente):
    ingresar(cliente, "consultante1")
    assert cliente.get("/historial/999").status_code == 404
    assert cliente.get("/consulta/999").status_code == 404


def test_detalle_muestra_advertencia_y_tildes(cliente):
    ingresar(cliente, "consultante1")
    html = cliente.get("/historial/500").get_data(as_text=True)
    assert "no debe seguir usándose" in html
    assert "Refrigeración del motor" in html
    assert "nivel-no-debe-seguir-usandose" in html
    assert "R10" in html


def test_reporte_tiene_estilos_de_impresion(cliente):
    ingresar(cliente, "consultante1")
    html = cliente.get("/historial/500/reporte").get_data(as_text=True)
    assert "window.print()" in html and "Reporte de diagnóstico vehicular" in html


# ------------------------------------------------------------------ CSRF
def test_post_sin_csrf_se_rechaza(cliente, servicios):
    ingresar(cliente, "consultante1")
    r = cliente.post("/vehiculos/nuevo", data={"placa": "XYZ987"})
    assert r.status_code == 400
    assert servicios["vehiculos"].creados == []


def test_crear_vehiculo_con_csrf(cliente, servicios):
    ingresar(cliente, "consultante1")
    r = cliente.post("/vehiculos/nuevo", data={"placa": "xyz987", "marca": "Kia", "modelo": "Rio",
                                               "combustible": "gasolina", "transmision": "manual",
                                               "csrf_token": token(cliente)})
    assert r.status_code == 302
    assert servicios["vehiculos"].creados[0]["placa"] == "xyz987"


def test_error_de_negocio_se_muestra_en_el_formulario(cliente):
    ingresar(cliente, "consultante1")
    r = cliente.post("/vehiculos/nuevo", data={"placa": "", "csrf_token": token(cliente)})
    assert r.status_code == 400
    assert "La placa no es válida" in r.get_data(as_text=True)


def test_api_sin_cabecera_csrf_se_rechaza(cliente):
    ingresar(cliente, "consultante1")
    r = cliente.post("/api/atenciones/500/respuestas", json={"id_pregunta": 7, "respuesta": "si"})
    assert r.status_code == 400 and "CSRF" in r.get_json()["error"]


# --------------------------------------------------------------- consulta
def test_flujo_de_consulta_completo(cliente, servicios):
    ingresar(cliente, "consultante1")
    t = token(cliente)
    r = cliente.post("/consulta/nueva", data={"id_vehiculo": "100", "id_area": "1", "testigos": ["ABS"],
                                              "codigos_obd": "p0217", "csrf_token": t})
    assert r.status_code == 302 and r.headers["Location"].endswith("/consulta/500")
    html = cliente.get("/consulta/500").get_data(as_text=True)
    assert "¿El motor se calienta?" in html

    r = cliente.post("/api/atenciones/500/respuestas", json={"id_pregunta": 7, "respuesta": "si"},
                     headers={"X-CSRF-Token": t})
    datos = r.get_json()
    assert r.status_code == 200 and datos["estado"] == "finalizado"
    primera = datos["resultado"][0]
    assert primera["advertencia"] is True
    assert primera["nivel_texto"] == "No debe seguir usándose"
    assert primera["nivel_clase"] == "nivel-no-debe-seguir-usandose"
    assert primera["reglas_activadas"] == ["R10", "R11"]

    r = cliente.post("/api/atenciones/500/confirmar", json={"id_hipotesis": 5, "observacion": "Bomba"},
                     headers={"X-CSRF-Token": t})
    assert r.get_json() == {"estado": "confirmado"}
    assert servicios["diagnostico"].confirmadas == [(500, 5, "Bomba")]


def test_api_atencion_ajena(cliente):
    ingresar(cliente, "consultante1")
    r = cliente.post("/api/atenciones/999/respuestas", json={"id_pregunta": 7, "respuesta": "si"},
                     headers={"X-CSRF-Token": token(cliente)})
    assert r.status_code == 404


def test_confirmar_falla_desde_el_detalle(cliente, servicios):
    ingresar(cliente, "consultante1")
    r = cliente.post("/historial/500/confirmar", data={"id_hipotesis": "6", "observacion": "",
                                                       "csrf_token": token(cliente)})
    assert r.status_code == 302
    assert servicios["diagnostico"].confirmadas == [(500, 6, None)]


def test_api_salud_es_publica(cliente):
    r = cliente.get("/api/salud")
    assert r.status_code == 200 and r.get_json()["estado"] == "ok"


def test_api_areas_con_tildes(cliente):
    ingresar(cliente, "consultante1")
    assert cliente.get("/api/areas").get_json()[0]["nombre"] == "Refrigeración del motor"


# ------------------------------------------------------------ ingeniero
def test_ingeniero_crea_y_edita_regla(cliente, servicios):
    ingresar(cliente, "ingeniero1")
    t = token(cliente)
    r = cliente.post("/conocimiento/reglas", data={"id_pregunta": "8", "id_hipotesis": "5",
                                                   "nivel_atencion": "Revision proxima", "recomendacion": "Revisar",
                                                   "peso": "1,1", "csrf_token": t})
    assert r.status_code == 302
    nombre, args = servicios["conocimiento"].llamadas[-1]
    assert nombre == "crear_regla" and args[0]["peso"] == 1.1 and args[1] == 20

    r = cliente.post("/conocimiento/reglas/10?area=1", data={"id_pregunta": "8", "id_hipotesis": "5",
                                                             "nivel_atencion": "Revision proxima",
                                                             "recomendacion": "Otra", "csrf_token": t})
    assert r.status_code == 302 and r.headers["Location"].endswith("/conocimiento/reglas?area=1")
    assert servicios["conocimiento"].llamadas[-1][0] == "actualizar_regla"

    cliente.post("/conocimiento/reglas/10/estado", data={"activa": "0", "csrf_token": t})
    assert servicios["conocimiento"].llamadas[-1] == ("cambiar_estado_regla", (10, False, 20))


def test_ingeniero_ve_error_de_negocio(cliente):
    ingresar(cliente, "ingeniero1")
    r = cliente.post("/conocimiento/areas", data={"nombre": "duplicada", "csrf_token": token(cliente)})
    assert r.status_code == 400
    assert "Ya existe un área con ese nombre." in r.get_data(as_text=True)


# --------------------------------------------------------- administrador
def test_admin_descarga_respaldo_sql(cliente):
    ingresar(cliente, "admin")
    r = cliente.post("/admin/respaldos/descargar", data={"alcance": "completo", "csrf_token": token(cliente)})
    assert r.status_code == 200
    assert r.headers["Content-Disposition"].startswith("attachment;")
    assert ".sql" in r.headers["Content-Disposition"]
    assert r.get_data(as_text=True).startswith("BEGIN;")


def test_admin_gestiona_usuarios(cliente, servicios):
    ingresar(cliente, "admin")
    t = token(cliente)
    cliente.post("/admin/usuarios", data={"nombre_usuario": "nuevo", "nombres": "Nuevo Usuario",
                                          "rol": "consultante", "clave": "Clave123",
                                          "clave_confirmacion": "Clave123", "csrf_token": t})
    cliente.post("/admin/usuarios/1/rol", data={"rol": "ingeniero", "csrf_token": t})
    cliente.post("/admin/usuarios/1/bloquear", data={"csrf_token": t})
    cliente.post("/admin/usuarios/1/desbloquear", data={"csrf_token": t})
    cliente.post("/admin/usuarios/1/inactivar", data={"csrf_token": t})
    nombres = [n for n, _a, _k in servicios["administracion"].llamadas]
    assert nombres == ["crear_usuario", "cambiar_rol", "bloquear", "desbloquear", "activar"]
    assert servicios["administracion"].llamadas[-1][1] == (1, False)


def test_admin_no_puede_bloquearse_a_si_mismo(cliente, servicios):
    ingresar(cliente, "admin")
    cliente.post("/admin/usuarios/3/bloquear", data={"csrf_token": token(cliente)})
    assert servicios["administracion"].llamadas == []


# ------------------------------------------------------------ utilidades
def test_filtro_tildes():
    assert tildes("Revision proxima") == "Revisión próxima"
    assert tildes("No debe seguir usandose sin evaluacion") == "No debe seguir usándose sin evaluación"
    assert tildes("Si") == "Sí" and tildes("No se") == "No sé"
    assert tildes("Codigo OBD no valido") == "Código OBD no válido"
    assert tildes("Revisión ya acentuada") == "Revisión ya acentuada"


def test_clase_nivel_y_porcentaje():
    assert clase_nivel("No debe seguir usandose sin evaluacion") == "nivel-no-debe-seguir-usandose"
    assert clase_nivel("Revisión próxima") == "nivel-revision-proxima"
    assert porcentaje(61.3) == "61,3 %"
