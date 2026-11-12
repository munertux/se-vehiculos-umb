# -*- coding: utf-8 -*-
"""Objetos del dominio (capa de logica de negocio) y escala de certeza.
Corresponde a logica/modelos.py en la Tabla 21 del manual tecnico.
"""
from dataclasses import dataclass, field
from typing import Optional

# Tabla 18 del manual: escala de respuesta, certeza y evidencia (e = 2c - 1)
ESCALA_CERTEZA = {
    "si": 1.00,
    "probablemente_si": 0.75,
    "no_se": 0.50,
    "probablemente_no": 0.25,
    "no": 0.00,
}

ETIQUETAS_RESPUESTA = {
    "si": "Si",
    "probablemente_si": "Probablemente si",
    "no_se": "No se",
    "probablemente_no": "Probablemente no",
    "no": "No",
}


def certeza_a_evidencia(certeza: float) -> float:
    """e = 2c - 1 (pagina 44 del manual)."""
    return 2 * certeza - 1


@dataclass
class Area:
    id_area: int
    nombre: str
    descripcion: str = ""


@dataclass
class Pregunta:
    id_pregunta: int
    id_area: int
    enunciado: str
    sintoma_evaluado: str
    es_entrada: bool = False
    activa: bool = True


@dataclass
class Hipotesis:
    id_hipotesis: int
    nombre: str
    descripcion: str = ""


@dataclass
class Regla:
    id_regla: int
    codigo: str
    id_pregunta: int
    id_hipotesis: int
    id_area: int
    nivel_atencion: str
    gravedad: int
    recomendacion: str
    peso: float = 1.0


@dataclass
class Granulo:
    """Minima unidad de conocimiento: une una pregunta con una hipotesis
    y el peso de la evidencia que aporta (1.0 directo, 0.4 de entrada)."""
    id_hipotesis: int
    peso: float
    id_regla: Optional[int] = None
    nivel_atencion: Optional[str] = None
    gravedad: int = 0
    recomendacion: Optional[str] = None


@dataclass
class HipotesisPonderada:
    hipotesis: Hipotesis
    puntaje: float
    probabilidad: float
    posicion: int
    id_area: int
    nivel_atencion: str
    recomendacion: str
    sintoma_confirmado: bool
    reglas_activadas: list = field(default_factory=list)
