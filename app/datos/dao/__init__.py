# -*- coding: utf-8 -*-
"""Objetos de acceso a datos (patron DAO). Unicas clases, junto con los
repositorios del motor, que ejecutan SQL por medio de Conexion."""
from app.datos.dao.base_dao import BaseDAO
from app.datos.dao.rol_dao import RolDAO
from app.datos.dao.usuario_dao import UsuarioDAO
from app.datos.dao.consultante_dao import ConsultanteDAO
from app.datos.dao.empleado_dao import EmpleadoDAO
from app.datos.dao.vehiculo_dao import VehiculoDAO
from app.datos.dao.area_dao import AreaDAO
from app.datos.dao.pregunta_dao import PreguntaDAO
from app.datos.dao.hipotesis_dao import HipotesisDAO
from app.datos.dao.regla_dao import ReglaDAO
from app.datos.dao.atencion_dao import AtencionDAO
from app.datos.dao.bitacora_dao import BitacoraDAO
from app.datos.dao.respaldo_dao import RespaldoDAO

__all__ = ["BaseDAO", "RolDAO", "UsuarioDAO", "ConsultanteDAO", "EmpleadoDAO", "VehiculoDAO",
           "AreaDAO", "PreguntaDAO", "HipotesisDAO", "ReglaDAO", "AtencionDAO", "BitacoraDAO",
           "RespaldoDAO"]
