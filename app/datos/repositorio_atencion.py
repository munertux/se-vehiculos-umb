# -*- coding: utf-8 -*-
"""RepositorioAtencion: persistencia de la base transaccional (RNF-11:
cada diagnostico guarda el 100% de las reglas activadas y su version).
Se conserva por compatibilidad; delega todo en AtencionDAO."""
from app.datos.dao.atencion_dao import AtencionDAO


class RepositorioAtencion(AtencionDAO):
    """Mismos metodos de siempre (abrir, guardar_respuesta,
    guardar_diagnostico, confirmar_falla) heredados del DAO."""
