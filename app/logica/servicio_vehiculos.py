# -*- coding: utf-8 -*-
"""ServicioVehiculos: los vehiculos del consultante (CU-02)."""
import re
from datetime import date

from app.datos.dao.consultante_dao import ConsultanteDAO
from app.datos.dao.vehiculo_dao import VehiculoDAO
from app.logica.entidades import (COMBUSTIBLES, TRANSMISIONES, ETIQUETAS_COMBUSTIBLE,
                                  ETIQUETAS_TRANSMISION, a_dict)
from app.logica.errores import ErrorNegocio

# Placas colombianas: carro ABC123, moto ABC12D; se admiten tambien formatos de 5 a 7 caracteres.
PATRON_PLACA = re.compile(r"^[A-Z0-9]{5,7}$")


class ServicioVehiculos:
    def __init__(self, conexion):
        self._vehiculos = VehiculoDAO(conexion)
        self._consultantes = ConsultanteDAO(conexion)

    @staticmethod
    def opciones() -> dict:
        """Valores validos (en minusculas, como se guardan). Las etiquetas
        para mostrar estan en opciones_etiquetadas()."""
        return {"combustible": list(COMBUSTIBLES), "transmision": list(TRANSMISIONES)}

    @staticmethod
    def opciones_etiquetadas() -> dict:
        return {
            "combustible": [{"valor": c, "etiqueta": ETIQUETAS_COMBUSTIBLE[c]} for c in COMBUSTIBLES],
            "transmision": [{"valor": t, "etiqueta": ETIQUETAS_TRANSMISION[t]} for t in TRANSMISIONES],
        }

    def listar(self, id_consultante: int, incluir_inactivos: bool = False) -> list:
        return [self._a_dict(v) for v in self._vehiculos.listar_por_consultante(id_consultante, incluir_inactivos)]

    def obtener(self, id_consultante: int, id_vehiculo: int) -> dict:
        return self._a_dict(self._propio(id_consultante, id_vehiculo))

    def crear(self, id_consultante: int, datos: dict) -> int:
        if self._consultantes.obtener(id_consultante) is None:
            raise ErrorNegocio("El consultante no existe.")
        limpios = self._validar(datos)
        if self._vehiculos.buscar_placa_activa(limpios["placa"]):
            raise ErrorNegocio(f"Ya existe un vehiculo activo con la placa {limpios['placa']}.")
        return self._vehiculos.crear(id_consultante, limpios)

    def actualizar(self, id_consultante: int, id_vehiculo: int, datos: dict):
        self._propio(id_consultante, id_vehiculo)
        limpios = self._validar(datos)
        if self._vehiculos.buscar_placa_activa(limpios["placa"], excluir_id=id_vehiculo):
            raise ErrorNegocio(f"Ya existe un vehiculo activo con la placa {limpios['placa']}.")
        self._vehiculos.actualizar(id_vehiculo, limpios)

    def desactivar(self, id_consultante: int, id_vehiculo: int):
        self._propio(id_consultante, id_vehiculo)
        self._vehiculos.cambiar_activo(id_vehiculo, False)

    def reactivar(self, id_consultante: int, id_vehiculo: int):
        v = self._propio(id_consultante, id_vehiculo)
        if self._vehiculos.buscar_placa_activa(v.placa, excluir_id=id_vehiculo):
            raise ErrorNegocio(f"Ya existe un vehiculo activo con la placa {v.placa}.")
        self._vehiculos.cambiar_activo(id_vehiculo, True)

    # ------------------------------------------------------------ internos
    def _propio(self, id_consultante: int, id_vehiculo: int):
        v = self._vehiculos.obtener(int(id_vehiculo))
        if v is None or v.id_consultante != int(id_consultante):
            raise ErrorNegocio("El vehiculo no existe o no pertenece al consultante.")
        return v

    @staticmethod
    def _validar(datos: dict) -> dict:
        def texto(clave, nombre, maximo):
            valor = str(datos.get(clave) or "").strip()
            if not valor:
                raise ErrorNegocio(f"El campo {nombre} es obligatorio.")
            if len(valor) > maximo:
                raise ErrorNegocio(f"El campo {nombre} admite maximo {maximo} caracteres.")
            return valor

        placa = re.sub(r"[\s-]", "", str(datos.get("placa") or "")).upper()
        if not PATRON_PLACA.match(placa):
            raise ErrorNegocio("La placa no es valida (ejemplo: ABC123).")
        combustible = str(datos.get("combustible") or "").strip().lower()
        if combustible not in COMBUSTIBLES:
            raise ErrorNegocio("Seleccione un tipo de combustible valido.")
        transmision = str(datos.get("transmision") or "").strip().lower()
        if transmision not in TRANSMISIONES:
            raise ErrorNegocio("Seleccione un tipo de transmision valido.")

        anio = datos.get("anio")
        if anio in (None, ""):
            anio = None
        else:
            try:
                anio = int(anio)
            except (TypeError, ValueError):
                raise ErrorNegocio("El anio debe ser un numero.")
            if not 1950 <= anio <= date.today().year + 1:
                raise ErrorNegocio(f"El anio debe estar entre 1950 y {date.today().year + 1}.")

        km = datos.get("kilometraje")
        if km in (None, ""):
            km = None
        else:
            try:
                km = int(str(km).replace(".", "").replace(",", ""))
            except (TypeError, ValueError):
                raise ErrorNegocio("El kilometraje debe ser un numero entero.")
            if not 0 <= km <= 3_000_000:
                raise ErrorNegocio("El kilometraje no es valido.")

        return {"placa": placa, "marca": texto("marca", "marca", 40), "modelo": texto("modelo", "modelo", 60),
                "combustible": combustible, "transmision": transmision, "anio": anio, "kilometraje": km}

    @staticmethod
    def _a_dict(v) -> dict:
        d = a_dict(v)
        d["descripcion"] = v.descripcion
        d["combustible_etiqueta"] = ETIQUETAS_COMBUSTIBLE.get(v.combustible, v.combustible)
        d["transmision_etiqueta"] = ETIQUETAS_TRANSMISION.get(v.transmision, v.transmision)
        return d
