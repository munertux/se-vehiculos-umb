# -*- coding: utf-8 -*-
"""Entidades de la base transaccional (usuarios, vehiculos, atenciones y
bitacora). Las entidades de conocimiento (Area, Pregunta, Hipotesis,
Regla) estan en modelos.py y se reexportan aqui para tener un solo punto
de importacion para los DAO."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from app.logica.modelos import Area, Pregunta, Hipotesis, Regla  # noqa: F401

# id_rol -> clave usada en la sesion web
ROL_CONSULTANTE = 1
ROL_INGENIERO = 2
ROL_ADMINISTRADOR = 3
CLAVES_ROL = {ROL_CONSULTANTE: "consultante", ROL_INGENIERO: "ingeniero", ROL_ADMINISTRADOR: "administrador"}
IDS_ROL = {v: k for k, v in CLAVES_ROL.items()}

ESTADOS_USUARIO = ("activo", "inactivo", "bloqueado")
COMBUSTIBLES = ("gasolina", "diesel", "gas", "hibrido", "electrico")
TRANSMISIONES = ("manual", "automatica", "cvt")
ETIQUETAS_COMBUSTIBLE = {"gasolina": "Gasolina", "diesel": "Diesel", "gas": "Gas natural",
                         "hibrido": "Hibrido", "electrico": "Electrico"}
ETIQUETAS_TRANSMISION = {"manual": "Manual", "automatica": "Automatica", "cvt": "CVT"}
NIVELES_ATENCION = (
    "Atencion preventiva",
    "Revision proxima",
    "Revision prioritaria",
    "No debe seguir usandose sin evaluacion",
    "No debe seguir usandose",
)
ACCIONES_BITACORA = ("crear", "modificar", "activar", "desactivar")


@dataclass
class Rol:
    id_rol: int
    nombre: str

    @property
    def clave(self) -> str:
        return CLAVES_ROL.get(self.id_rol, "")


@dataclass
class Usuario:
    id_usuario: int
    id_rol: int
    nombre_usuario: str
    contrasena_hash: str
    estado: str = "activo"
    intentos_fallidos: int = 0
    bloqueado_hasta: Optional[datetime] = None
    ultimo_acceso: Optional[datetime] = None
    creado: Optional[datetime] = None
    bloqueo_vigente: bool = False   # calculado en SQL: bloqueado_hasta > now()
    minutos_restantes: Optional[int] = None   # minutos que faltan para el desbloqueo

    @property
    def rol(self) -> str:
        return CLAVES_ROL.get(self.id_rol, "")


@dataclass
class Consultante:
    id_consultante: int
    id_usuario: int
    nombres: str
    correo: Optional[str] = None
    telefono: Optional[str] = None


@dataclass
class Empleado:
    id_empleado: int
    id_usuario: int
    nombres: str
    cargo: Optional[str] = None


@dataclass
class Vehiculo:
    id_vehiculo: int
    id_consultante: int
    placa: str
    marca: str
    modelo: str
    combustible: str
    transmision: str
    anio: Optional[int] = None
    kilometraje: Optional[int] = None
    activo: bool = True
    creado: Optional[datetime] = None

    @property
    def descripcion(self) -> str:
        return f"{self.placa} - {self.marca} {self.modelo}"


@dataclass
class Atencion:
    id_atencion: int
    id_area: int
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    estado: str = "en_curso"
    id_vehiculo: Optional[int] = None
    id_consultante: Optional[int] = None
    testigos_tablero: Optional[str] = None
    codigos_obd: Optional[str] = None


@dataclass
class RespuestaAtencion:
    id_atencion: int
    id_pregunta: int
    respuesta: str
    certeza: float
    orden: int


@dataclass
class DiagnosticoAtencion:
    id_atencion: int
    id_hipotesis: int
    puntaje: float
    probabilidad: float
    posicion: int
    falla_confirmada: bool = False
    reglas_activadas: Optional[str] = None
    observacion: Optional[str] = None


@dataclass
class RegistroBitacora:
    id_bitacora: int
    entidad: str
    accion: str
    fecha: datetime
    id_empleado: Optional[int] = None
    id_registro: Optional[int] = None
    id_regla: Optional[int] = None
    detalle: Optional[str] = None


def a_dict(entidad) -> dict:
    """Convierte una entidad (dataclass) en diccionario."""
    return asdict(entidad)


def lista_texto(valor) -> list:
    """'A, B' o ['A','B'] -> ['A','B'] sin vacios."""
    if not valor:
        return []
    if isinstance(valor, str):
        valor = valor.split(",")
    return [str(v).strip() for v in valor if str(v).strip()]
