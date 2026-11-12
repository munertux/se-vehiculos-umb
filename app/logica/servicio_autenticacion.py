# -*- coding: utf-8 -*-
"""ServicioAutenticacion: inicio de sesion (CU-01) y cambio de clave.
RNF-03: bloqueo temporal de 15 minutos tras 5 intentos fallidos."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

from app.datos.dao.consultante_dao import ConsultanteDAO
from app.datos.dao.empleado_dao import EmpleadoDAO
from app.datos.dao.usuario_dao import UsuarioDAO
from app.logica.errores import ErrorNegocio

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15
LONGITUD_MINIMA_CLAVE = 8
MENSAJE_CREDENCIALES = "Usuario o contrasena incorrectos."
# Hash ficticio para que un usuario inexistente tarde lo mismo que uno real.
_HASH_FICTICIO = generate_password_hash("clave-ficticia-para-tiempo-constante")


def validar_clave(clave: str):
    """Politica minima: 8 caracteres con letras y numeros."""
    if not clave or len(clave) < LONGITUD_MINIMA_CLAVE:
        raise ErrorNegocio(f"La contrasena debe tener al menos {LONGITUD_MINIMA_CLAVE} caracteres.")
    if not re.search(r"[A-Za-z]", clave) or not re.search(r"\d", clave):
        raise ErrorNegocio("La contrasena debe combinar letras y numeros.")


def hashear_clave(clave: str) -> str:
    return generate_password_hash(clave)


class ServicioAutenticacion:
    def __init__(self, conexion):
        self._usuarios = UsuarioDAO(conexion)
        self._consultantes = ConsultanteDAO(conexion)
        self._empleados = EmpleadoDAO(conexion)

    def autenticar(self, nombre_usuario: str, clave: str) -> dict:
        """Devuelve el diccionario de sesion o lanza ErrorNegocio."""
        nombre_usuario = (nombre_usuario or "").strip()
        clave = clave or ""
        if not nombre_usuario or not clave:
            raise ErrorNegocio("Ingrese el usuario y la contrasena.")

        usuario = self._usuarios.obtener_por_nombre(nombre_usuario)
        if usuario is None:
            check_password_hash(_HASH_FICTICIO, clave)
            raise ErrorNegocio(MENSAJE_CREDENCIALES)

        if usuario.estado == "inactivo":
            raise ErrorNegocio("El usuario esta inactivo. Comuniquese con el administrador.")
        if usuario.estado == "bloqueado":
            if usuario.bloqueado_hasta is None:
                raise ErrorNegocio("El usuario esta bloqueado por el administrador.")
            if usuario.bloqueo_vigente:
                raise ErrorNegocio(
                    f"El usuario esta bloqueado temporalmente por {MAX_INTENTOS} intentos fallidos. "
                    f"Intente de nuevo en {max(1, usuario.minutos_restantes or 1)} minuto(s).")
            self._usuarios.liberar_bloqueo_vencido(usuario.id_usuario)

        if not check_password_hash(usuario.contrasena_hash, clave):
            r = self._usuarios.registrar_intento_fallido(usuario.id_usuario, MAX_INTENTOS, MINUTOS_BLOQUEO)
            if r["estado"] == "bloqueado":
                raise ErrorNegocio(
                    f"Contrasena incorrecta. El usuario quedo bloqueado {MINUTOS_BLOQUEO} minutos "
                    f"por {MAX_INTENTOS} intentos fallidos.")
            restantes = MAX_INTENTOS - r["intentos_fallidos"]
            raise ErrorNegocio(f"{MENSAJE_CREDENCIALES} Le quedan {restantes} intento(s).")

        self._usuarios.registrar_acceso(usuario.id_usuario)
        return self.sesion_de(usuario.id_usuario)

    def sesion_de(self, id_usuario: int) -> dict:
        """Diccionario de sesion acordado con la presentacion."""
        usuario = self._usuarios.obtener(id_usuario)
        if usuario is None:
            raise ErrorNegocio("El usuario no existe.")
        consultante = self._consultantes.obtener_por_usuario(id_usuario)
        empleado = self._empleados.obtener_por_usuario(id_usuario)
        rol = usuario.rol
        nombres = (consultante.nombres if consultante and rol == "consultante"
                   else empleado.nombres if empleado else consultante.nombres if consultante
                   else usuario.nombre_usuario)
        return {
            "id_usuario": usuario.id_usuario,
            "nombre_usuario": usuario.nombre_usuario,
            "rol": rol,
            "nombres": nombres,
            "id_consultante": consultante.id_consultante if consultante and rol == "consultante" else None,
            "id_empleado": empleado.id_empleado if empleado and rol != "consultante" else None,
        }

    def cambiar_clave(self, id_usuario: int, clave_actual: str, clave_nueva: str):
        usuario = self._usuarios.obtener(id_usuario)
        if usuario is None:
            raise ErrorNegocio("El usuario no existe.")
        if not check_password_hash(usuario.contrasena_hash, clave_actual or ""):
            raise ErrorNegocio("La contrasena actual no es correcta.")
        if clave_nueva == clave_actual:
            raise ErrorNegocio("La nueva contrasena debe ser distinta de la actual.")
        validar_clave(clave_nueva)
        self._usuarios.cambiar_hash(id_usuario, hashear_clave(clave_nueva))
