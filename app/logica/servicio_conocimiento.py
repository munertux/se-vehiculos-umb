# -*- coding: utf-8 -*-
"""ServicioConocimiento: mantenimiento de la base de conocimiento por el
ingeniero del conocimiento (CU-05). Cada creacion o cambio queda en
bitacora_conocimiento dentro de la misma transaccion."""
from app.datos.dao.area_dao import AreaDAO
from app.datos.dao.atencion_dao import AtencionDAO
from app.datos.dao.bitacora_dao import BitacoraDAO
from app.datos.dao.hipotesis_dao import HipotesisDAO
from app.datos.dao.pregunta_dao import PreguntaDAO
from app.datos.dao.regla_dao import ReglaDAO
from app.datos.repositorio_conocimiento import RepositorioConocimiento
from app.logica.entidades import NIVELES_ATENCION, a_dict
from app.logica.errores import ErrorNegocio

GRAVEDAD_POR_NIVEL = {
    "Atencion preventiva": 1,
    "Revision proxima": 2,
    "Revision prioritaria": 3,
    "No debe seguir usandose sin evaluacion": 4,
    "No debe seguir usandose": 4,
}


def peso_por_gravedad(gravedad: int) -> float:
    """Convencion de la base actual: peso = 0.8 + 0.1 * gravedad."""
    return round(0.8 + 0.1 * int(gravedad), 2)


def _cambios(antes: dict, despues: dict) -> str:
    partes = []
    for clave, nuevo in despues.items():
        viejo = antes.get(clave)
        if viejo != nuevo:
            partes.append(f"{clave}: {viejo!r} -> {nuevo!r}")
    return "; ".join(partes) or "sin cambios"


class ServicioConocimiento:
    def __init__(self, conexion):
        self._db = conexion
        self._areas = AreaDAO(conexion)
        self._preguntas = PreguntaDAO(conexion)
        self._hipotesis = HipotesisDAO(conexion)
        self._reglas = ReglaDAO(conexion)
        self._bitacora = BitacoraDAO(conexion)
        self._atenciones = AtencionDAO(conexion)
        self._repo_c = RepositorioConocimiento(conexion)

    # ------------------------------------------------------------- resumen
    def resumen(self) -> dict:
        return {
            "areas": self._areas.contar(),
            "preguntas": self._preguntas.contar(),
            "preguntas_activas": self._preguntas.contar(solo_activas=True),
            "hipotesis": self._hipotesis.contar(),
            "reglas": self._reglas.contar(),
            "reglas_activas": self._reglas.contar(solo_activas=True),
            "atenciones": self._atenciones.contar(),
            "problemas": len(self.validar()),
        }

    @staticmethod
    def opciones_regla() -> dict:
        return {"niveles_atencion": list(NIVELES_ATENCION), "gravedades": [1, 2, 3, 4],
                "gravedad_por_nivel": dict(GRAVEDAD_POR_NIVEL)}

    # --------------------------------------------------------------- areas
    def listar_areas(self) -> list:
        return self._areas.listar_con_conteos()

    def obtener_area(self, id_area: int) -> dict:
        return a_dict(self._area(id_area))

    def crear_area(self, datos: dict, id_empleado: int) -> int:
        limpios = self._validar_area(datos)
        with self._db.transaccion() as tx:
            id_area = self._areas.crear(limpios["nombre"], limpios["descripcion"], tx=tx)
            self._bitacora.registrar("area", id_area, "crear", id_empleado,
                                     detalle=f"Area '{limpios['nombre']}'", tx=tx)
        return id_area

    def actualizar_area(self, id_area: int, datos: dict, id_empleado: int):
        antes = a_dict(self._area(id_area))
        limpios = self._validar_area(datos, excluir_id=id_area)
        with self._db.transaccion() as tx:
            self._areas.actualizar(id_area, limpios, tx=tx)
            self._bitacora.registrar("area", id_area, "modificar", id_empleado,
                                     detalle=_cambios(antes, limpios), tx=tx)

    # ----------------------------------------------------------- preguntas
    def listar_preguntas(self, id_area: int = None) -> list:
        return self._preguntas.listar(id_area)

    def obtener_pregunta(self, id_pregunta: int) -> dict:
        return a_dict(self._pregunta(id_pregunta))

    def crear_pregunta(self, datos: dict, id_empleado: int) -> int:
        limpios = self._validar_pregunta(datos)
        limpios["activa"] = True
        if limpios["es_entrada"] and self._preguntas.entrada_del_area(limpios["id_area"]):
            raise ErrorNegocio("El area ya tiene una pregunta de entrada activa.")
        with self._db.transaccion() as tx:
            id_pregunta = self._preguntas.crear(limpios, tx=tx)
            tipo = "de entrada" if limpios["es_entrada"] else "especifica"
            self._bitacora.registrar("pregunta", id_pregunta, "crear", id_empleado,
                                     detalle=f"Pregunta {tipo} del area {limpios['id_area']}: {limpios['enunciado']}",
                                     tx=tx)
        return id_pregunta

    def actualizar_pregunta(self, id_pregunta: int, datos: dict, id_empleado: int):
        actual = self._pregunta(id_pregunta)
        limpios = self._validar_pregunta(datos)
        reglas = [r for r in self._reglas.listar() if r["id_pregunta"] == id_pregunta]
        if limpios["id_area"] != actual.id_area and reglas:
            raise ErrorNegocio("No se puede cambiar el area de una pregunta que tiene reglas asociadas.")
        if limpios["es_entrada"] and not actual.es_entrada:
            if any(r["activa"] for r in reglas):
                raise ErrorNegocio("Una pregunta con reglas activas no puede ser de entrada.")
            if self._preguntas.entrada_del_area(limpios["id_area"], excluir_id=id_pregunta):
                raise ErrorNegocio("El area ya tiene una pregunta de entrada activa.")
        if actual.es_entrada and not limpios["es_entrada"] and actual.activa:
            raise ErrorNegocio("Cree o marque otra pregunta de entrada antes de quitarle ese papel a esta.")
        with self._db.transaccion() as tx:
            self._preguntas.actualizar(id_pregunta, limpios, tx=tx)
            self._bitacora.registrar("pregunta", id_pregunta, "modificar", id_empleado,
                                     detalle=_cambios(a_dict(actual), limpios), tx=tx)

    def cambiar_estado_pregunta(self, id_pregunta: int, activa: bool, id_empleado: int):
        actual = self._pregunta(id_pregunta)
        activa = bool(activa)
        if actual.activa == activa:
            return
        if activa and actual.es_entrada and self._preguntas.entrada_del_area(actual.id_area, excluir_id=id_pregunta):
            raise ErrorNegocio("El area ya tiene otra pregunta de entrada activa.")
        if not activa and actual.es_entrada:
            raise ErrorNegocio("No se puede desactivar la pregunta de entrada del area: "
                               "sin ella el area no se puede consultar.")
        with self._db.transaccion() as tx:
            self._preguntas.cambiar_activa(id_pregunta, activa, tx=tx)
            self._bitacora.registrar("pregunta", id_pregunta, "activar" if activa else "desactivar", id_empleado,
                                     detalle=actual.enunciado, tx=tx)

    # ----------------------------------------------------------- hipotesis
    def listar_hipotesis(self) -> list:
        return self._hipotesis.listar()

    def obtener_hipotesis(self, id_hipotesis: int) -> dict:
        return a_dict(self._hipotesis_o_error(id_hipotesis))

    def crear_hipotesis(self, datos: dict, id_empleado: int) -> int:
        limpios = self._validar_hipotesis(datos)
        with self._db.transaccion() as tx:
            id_h = self._hipotesis.crear(limpios["nombre"], limpios["descripcion"], tx=tx)
            self._bitacora.registrar("hipotesis", id_h, "crear", id_empleado, detalle=limpios["nombre"], tx=tx)
        return id_h

    def actualizar_hipotesis(self, id_hipotesis: int, datos: dict, id_empleado: int):
        antes = a_dict(self._hipotesis_o_error(id_hipotesis))
        limpios = self._validar_hipotesis(datos, excluir_id=id_hipotesis)
        with self._db.transaccion() as tx:
            self._hipotesis.actualizar(id_hipotesis, limpios, tx=tx)
            self._bitacora.registrar("hipotesis", id_hipotesis, "modificar", id_empleado,
                                     detalle=_cambios(antes, limpios), tx=tx)

    # -------------------------------------------------------------- reglas
    def listar_reglas(self, id_area: int = None) -> list:
        return self._reglas.listar(id_area)

    def obtener_regla(self, id_regla: int) -> dict:
        regla = self._reglas.obtener_detalle(int(id_regla))
        if regla is None:
            raise ErrorNegocio("La regla no existe.")
        return regla

    def crear_regla(self, datos: dict, id_empleado: int) -> int:
        limpios = self._validar_regla(datos)
        if self._reglas.existe_activa(limpios["id_pregunta"], limpios["id_hipotesis"]):
            raise ErrorNegocio("Ya existe una regla activa que une esa pregunta con esa hipotesis.")
        if limpios.get("codigo") and self._reglas.existe_codigo(limpios["codigo"]):
            raise ErrorNegocio(f"El codigo {limpios['codigo']} ya existe.")
        limpios["activa"] = True
        with self._db.transaccion() as tx:
            id_regla = self._reglas.crear(limpios, tx=tx)
            regla = self._reglas.obtener(id_regla, tx=tx)
            self._bitacora.registrar("regla", id_regla, "crear", id_empleado, id_regla=id_regla,
                                     detalle=f"{regla.codigo}: pregunta {regla.id_pregunta} -> hipotesis "
                                             f"{regla.id_hipotesis} ({regla.nivel_atencion}, peso {regla.peso})",
                                     tx=tx)
        return id_regla

    def actualizar_regla(self, id_regla: int, datos: dict, id_empleado: int):
        """Actualiza la regla y sube su version."""
        actual = self._reglas.obtener(int(id_regla))
        if actual is None:
            raise ErrorNegocio("La regla no existe.")
        base = a_dict(actual)
        base.update({k: v for k, v in datos.items() if v is not None})
        limpios = self._validar_regla(base)
        if actual.activa and self._reglas.existe_activa(limpios["id_pregunta"], limpios["id_hipotesis"],
                                                        excluir_id=id_regla):
            raise ErrorNegocio("Ya existe otra regla activa que une esa pregunta con esa hipotesis.")
        if limpios.get("codigo") and self._reglas.existe_codigo(limpios["codigo"], excluir_id=id_regla):
            raise ErrorNegocio(f"El codigo {limpios['codigo']} ya existe.")
        if not limpios.get("codigo"):
            limpios.pop("codigo", None)
        with self._db.transaccion() as tx:
            self._reglas.actualizar(id_regla, limpios, tx=tx)
            self._bitacora.registrar("regla", id_regla, "modificar", id_empleado, id_regla=id_regla,
                                     detalle=f"{actual.codigo} v{actual.version + 1}: " + _cambios(a_dict(actual), limpios),
                                     tx=tx)

    def cambiar_estado_regla(self, id_regla: int, activa: bool, id_empleado: int):
        actual = self._reglas.obtener(int(id_regla))
        if actual is None:
            raise ErrorNegocio("La regla no existe.")
        activa = bool(activa)
        if actual.activa == activa:
            return
        if activa and self._reglas.existe_activa(actual.id_pregunta, actual.id_hipotesis, excluir_id=id_regla):
            raise ErrorNegocio("Ya existe otra regla activa que une esa pregunta con esa hipotesis.")
        with self._db.transaccion() as tx:
            self._reglas.cambiar_activa(id_regla, activa, tx=tx)
            self._bitacora.registrar("regla", id_regla, "activar" if activa else "desactivar", id_empleado,
                                     id_regla=id_regla, detalle=actual.codigo, tx=tx)

    # ------------------------------------------------------------ granulos
    def granulos_por_hipotesis(self, id_hipotesis: int) -> dict:
        """Granulos de conocimiento que aportan evidencia a la hipotesis:
        directos (sus reglas, peso de la regla) y de rama (pregunta de
        entrada de cada area de esas reglas, peso = peso_entrada)."""
        hip = self._hipotesis_o_error(id_hipotesis)
        reglas = self._reglas.listar_por_hipotesis(hip.id_hipotesis)
        peso_entrada = self._repo_c.parametros().get("peso_entrada", 0.4)
        granulos = []
        areas = []
        for r in reglas:
            pregunta = self._preguntas.obtener(r.id_pregunta)
            granulos.append({
                "tipo": "directo",
                "id_pregunta": r.id_pregunta,
                "enunciado": pregunta.enunciado if pregunta else "",
                "codigo_regla": r.codigo,
                "peso": float(r.peso),
                "nivel_atencion": r.nivel_atencion,
                "recomendacion": r.recomendacion,
                "activa": bool(r.activa and pregunta and pregunta.activa),
            })
            if r.activa and r.id_area not in areas:
                areas.append(r.id_area)
        for id_area in areas:
            entrada = self._preguntas.entrada_del_area(id_area)
            if entrada:
                granulos.insert(0, {
                    "tipo": "rama",
                    "id_pregunta": entrada.id_pregunta,
                    "enunciado": entrada.enunciado,
                    "codigo_regla": None,
                    "peso": float(peso_entrada),
                    "nivel_atencion": None,
                    "recomendacion": None,
                    "activa": True,
                })
        area = self._areas.obtener(areas[0]) if areas else (
            self._areas.obtener(reglas[0].id_area) if reglas else None)
        return {
            "hipotesis": a_dict(hip),
            "area": a_dict(area) if area else None,
            "granulos": granulos,
        }

    # ------------------------------------------------------------ validar
    def validar(self) -> list:
        """Problemas de consistencia de la base de conocimiento."""
        problemas = []
        for r in self._reglas.activas_con_pregunta_inactiva():
            problemas.append({"tipo": "regla_sin_pregunta_activa", "entidad": "regla", "id": r["id_regla"],
                              "mensaje": f"La regla {r['codigo']} esta activa pero su pregunta "
                                         f"{r['id_pregunta']} esta inactiva."})
        for r in self._reglas.activas_sobre_pregunta_de_entrada():
            problemas.append({"tipo": "regla_sobre_pregunta_de_entrada", "entidad": "regla", "id": r["id_regla"],
                              "mensaje": f"La regla {r['codigo']} usa la pregunta de entrada {r['id_pregunta']}; "
                                         "el motor no la aplica como granulo directo."})
        for h in self._hipotesis.sin_regla_activa():
            problemas.append({"tipo": "hipotesis_sin_regla", "entidad": "hipotesis", "id": h.id_hipotesis,
                              "mensaje": f"La hipotesis '{h.nombre}' no tiene ninguna regla activa."})
        for d in self._reglas.duplicadas():
            problemas.append({"tipo": "regla_duplicada", "entidad": "regla", "id": None,
                              "mensaje": f"Las reglas {', '.join(d['codigos'])} unen la misma pregunta "
                                         f"{d['id_pregunta']} con la hipotesis {d['id_hipotesis']}."})
        for a in self._areas.sin_pregunta_de_entrada():
            problemas.append({"tipo": "area_sin_entrada", "entidad": "area", "id": a.id_area,
                              "mensaje": f"El area '{a.nombre}' no tiene pregunta de entrada activa."})
        for r in self._reglas.area_distinta_a_pregunta():
            problemas.append({"tipo": "regla_area_inconsistente", "entidad": "regla", "id": r["id_regla"],
                              "mensaje": f"La regla {r['codigo']} tiene un area distinta a la de su pregunta."})
        return problemas

    # ------------------------------------------------------------ internos
    def _area(self, id_area):
        a = self._areas.obtener(int(id_area))
        if a is None:
            raise ErrorNegocio("El area no existe.")
        return a

    def _pregunta(self, id_pregunta):
        p = self._preguntas.obtener(int(id_pregunta))
        if p is None:
            raise ErrorNegocio("La pregunta no existe.")
        return p

    def _hipotesis_o_error(self, id_hipotesis):
        h = self._hipotesis.obtener(int(id_hipotesis))
        if h is None:
            raise ErrorNegocio("La hipotesis no existe.")
        return h

    def _validar_area(self, datos, excluir_id=None) -> dict:
        nombre = str(datos.get("nombre") or "").strip()
        if not nombre:
            raise ErrorNegocio("El nombre del area es obligatorio.")
        if len(nombre) > 100:
            raise ErrorNegocio("El nombre del area admite maximo 100 caracteres.")
        if self._areas.existe_nombre(nombre, excluir_id):
            raise ErrorNegocio("Ya existe un area con ese nombre.")
        return {"nombre": nombre, "descripcion": str(datos.get("descripcion") or "").strip()}

    def _validar_pregunta(self, datos) -> dict:
        try:
            id_area = int(datos.get("id_area"))
        except (TypeError, ValueError):
            raise ErrorNegocio("Seleccione el area de la pregunta.")
        self._area(id_area)
        enunciado = str(datos.get("enunciado") or "").strip()
        sintoma = str(datos.get("sintoma_evaluado") or "").strip()
        if len(enunciado) < 5:
            raise ErrorNegocio("El enunciado de la pregunta es obligatorio.")
        if not sintoma:
            raise ErrorNegocio("Indique el sintoma que evalua la pregunta.")
        return {"id_area": id_area, "enunciado": enunciado, "sintoma_evaluado": sintoma,
                "es_entrada": _a_bool(datos.get("es_entrada"))}

    def _validar_hipotesis(self, datos, excluir_id=None) -> dict:
        nombre = str(datos.get("nombre") or "").strip()
        if not nombre:
            raise ErrorNegocio("El nombre de la hipotesis es obligatorio.")
        if len(nombre) > 200:
            raise ErrorNegocio("El nombre de la hipotesis admite maximo 200 caracteres.")
        if self._hipotesis.existe_nombre(nombre, excluir_id):
            raise ErrorNegocio("Ya existe una hipotesis con ese nombre.")
        return {"nombre": nombre, "descripcion": str(datos.get("descripcion") or "").strip()}

    def _validar_regla(self, datos) -> dict:
        try:
            id_pregunta = int(datos.get("id_pregunta"))
            id_hipotesis = int(datos.get("id_hipotesis"))
        except (TypeError, ValueError):
            raise ErrorNegocio("Seleccione la pregunta y la hipotesis de la regla.")
        pregunta = self._pregunta(id_pregunta)
        if pregunta.es_entrada:
            raise ErrorNegocio("Las reglas se asocian a preguntas especificas, no a la pregunta de entrada.")
        self._hipotesis_o_error(id_hipotesis)
        nivel = str(datos.get("nivel_atencion") or "").strip()
        if nivel not in NIVELES_ATENCION:
            raise ErrorNegocio("Seleccione un nivel de atencion valido.")
        gravedad = datos.get("gravedad")
        gravedad = GRAVEDAD_POR_NIVEL[nivel] if gravedad in (None, "") else int(gravedad)
        if gravedad not in (1, 2, 3, 4):
            raise ErrorNegocio("La gravedad debe estar entre 1 y 4.")
        recomendacion = str(datos.get("recomendacion") or "").strip()
        if not recomendacion:
            raise ErrorNegocio("La recomendacion es obligatoria.")
        peso = datos.get("peso")
        try:
            peso = peso_por_gravedad(gravedad) if peso in (None, "") else round(float(peso), 2)
        except (TypeError, ValueError):
            raise ErrorNegocio("El peso debe ser un numero.")
        if not 0 < peso <= 2:
            raise ErrorNegocio("El peso debe ser mayor que 0 y maximo 2.")
        codigo = str(datos.get("codigo") or "").strip().upper()
        if codigo and (len(codigo) > 10 or not codigo.startswith("R")):
            raise ErrorNegocio("El codigo de la regla debe empezar por R y tener maximo 10 caracteres.")
        return {"codigo": codigo or None, "id_pregunta": id_pregunta, "id_hipotesis": id_hipotesis,
                "id_area": pregunta.id_area, "nivel_atencion": nivel, "gravedad": gravedad,
                "recomendacion": recomendacion, "peso": peso}


def _a_bool(valor) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() in ("1", "true", "si", "on", "yes")
    return bool(valor)
