# -*- coding: utf-8 -*-
"""Autenticacion, bloqueo de 15 minutos tras 5 intentos (RNF-03) y cambio de clave."""
import pytest

from apoyo_bd import conexion_prueba, unico  # noqa: F401 (fixture)
from app.datos.dao.usuario_dao import UsuarioDAO
from app.logica.errores import ErrorNegocio
from app.logica.servicio_administracion import ServicioAdministracion
from app.logica.servicio_autenticacion import ServicioAutenticacion, MAX_INTENTOS, MINUTOS_BLOQUEO

CLAVE = "Prueba2026x"


@pytest.fixture
def auth(conexion_prueba):
    return ServicioAutenticacion(conexion_prueba)


def crear(conexion, rol="consultante", nombres="Usuario Prueba"):
    nombre = unico("au")
    id_u = ServicioAdministracion(conexion).crear_usuario(nombre, CLAVE, rol, nombres)
    return nombre, id_u


def test_parametros_rnf03():
    assert MAX_INTENTOS == 5 and MINUTOS_BLOQUEO == 15


def test_login_consultante_devuelve_sesion(conexion_prueba, auth):
    nombre, id_u = crear(conexion_prueba, nombres="Carlos Prueba")
    sesion = auth.autenticar(nombre, CLAVE)
    assert set(sesion) == {"id_usuario", "nombre_usuario", "rol", "nombres", "id_consultante", "id_empleado"}
    assert sesion["id_usuario"] == id_u and sesion["rol"] == "consultante" and sesion["nombres"] == "Carlos Prueba"
    assert sesion["id_consultante"] is not None and sesion["id_empleado"] is None
    assert UsuarioDAO(conexion_prueba).obtener(id_u).ultimo_acceso is not None


@pytest.mark.parametrize("rol", ["ingeniero", "administrador"])
def test_login_empleado(conexion_prueba, auth, rol):
    nombre, _ = crear(conexion_prueba, rol)
    sesion = auth.autenticar(nombre.upper(), CLAVE)
    assert sesion["rol"] == rol and sesion["id_empleado"] is not None and sesion["id_consultante"] is None


def test_clave_incorrecta_y_usuario_inexistente(conexion_prueba, auth):
    nombre, _ = crear(conexion_prueba)
    with pytest.raises(ErrorNegocio, match="incorrectos.*4 intento"):
        auth.autenticar(nombre, "otra-clave1")
    with pytest.raises(ErrorNegocio, match="incorrectos"):
        auth.autenticar(unico("nadie"), CLAVE)
    with pytest.raises(ErrorNegocio):
        auth.autenticar("", "")


def test_bloqueo_tras_cinco_intentos(conexion_prueba, auth):
    nombre, id_u = crear(conexion_prueba)
    for _ in range(4):
        with pytest.raises(ErrorNegocio, match="incorrectos"):
            auth.autenticar(nombre, "mala-clave1")
    with pytest.raises(ErrorNegocio, match="bloqueado 15 minutos"):
        auth.autenticar(nombre, "mala-clave1")
    u = UsuarioDAO(conexion_prueba).obtener(id_u)
    assert u.estado == "bloqueado" and u.bloqueo_vigente
    # aun con la clave correcta sigue bloqueado
    with pytest.raises(ErrorNegocio, match="bloqueado temporalmente"):
        auth.autenticar(nombre, CLAVE)


def test_bloqueo_vencido_se_libera(conexion_prueba, auth):
    nombre, id_u = crear(conexion_prueba)
    for _ in range(5):
        with pytest.raises(ErrorNegocio):
            auth.autenticar(nombre, "mala-clave1")
    UsuarioDAO(conexion_prueba).fijar_bloqueo_hasta(id_u, -1)   # simula que pasaron 15 minutos
    assert auth.autenticar(nombre, CLAVE)["id_usuario"] == id_u
    u = UsuarioDAO(conexion_prueba).obtener(id_u)
    assert u.estado == "activo" and u.intentos_fallidos == 0


def test_login_exitoso_reinicia_intentos(conexion_prueba, auth):
    nombre, id_u = crear(conexion_prueba)
    for _ in range(3):
        with pytest.raises(ErrorNegocio):
            auth.autenticar(nombre, "mala-clave1")
    auth.autenticar(nombre, CLAVE)
    assert UsuarioDAO(conexion_prueba).obtener(id_u).intentos_fallidos == 0


def test_inactivo_y_bloqueo_administrativo(conexion_prueba, auth):
    admin = ServicioAdministracion(conexion_prueba)
    nombre, id_u = crear(conexion_prueba)
    admin.activar(id_u, False)
    with pytest.raises(ErrorNegocio, match="inactivo"):
        auth.autenticar(nombre, CLAVE)
    admin.activar(id_u, True)
    admin.bloquear(id_u)
    with pytest.raises(ErrorNegocio, match="bloqueado por el administrador"):
        auth.autenticar(nombre, CLAVE)
    admin.desbloquear(id_u)
    assert auth.autenticar(nombre, CLAVE)["id_usuario"] == id_u


def test_cambiar_clave(conexion_prueba, auth):
    nombre, id_u = crear(conexion_prueba)
    with pytest.raises(ErrorNegocio, match="actual"):
        auth.cambiar_clave(id_u, "equivocada1", "Nueva2026y")
    with pytest.raises(ErrorNegocio, match="8 caracteres"):
        auth.cambiar_clave(id_u, CLAVE, "corta1")
    with pytest.raises(ErrorNegocio, match="letras y numeros"):
        auth.cambiar_clave(id_u, CLAVE, "solamenteletras")
    auth.cambiar_clave(id_u, CLAVE, "Nueva2026y")
    assert auth.autenticar(nombre, "Nueva2026y")["id_usuario"] == id_u
    with pytest.raises(ErrorNegocio):
        auth.autenticar(nombre, CLAVE)


def test_hash_no_guarda_clave_en_claro(conexion_prueba):
    _, id_u = crear(conexion_prueba)
    h = UsuarioDAO(conexion_prueba).obtener(id_u).contrasena_hash
    assert CLAVE not in h and (h.startswith("scrypt:") or h.startswith("pbkdf2:"))
