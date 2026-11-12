# -*- coding: utf-8 -*-
"""Errores de la capa de logica de negocio."""


class ErrorNegocio(ValueError):
    """Regla de negocio incumplida o dato no valido. El mensaje se puede
    mostrar tal cual al usuario. Hereda de ValueError para que las rutas
    /api/* existentes (que capturan ValueError) sigan funcionando."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje
