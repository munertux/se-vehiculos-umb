# -*- coding: utf-8 -*-
"""Blueprint del ingeniero del conocimiento: resumen y validacion de la
base de conocimiento, mantenimiento de areas, preguntas, hipotesis y
reglas, y vista de granulos por hipotesis."""
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)

from app.web.presentacion import tildes
from app.web.seguridad import rol_requerido
from app.web.servicios import ERRORES_USUARIO, mensaje, servicio

bp = Blueprint("conocimiento", __name__, url_prefix="/conocimiento")

NIVELES_RESPALDO = ["Atencion preventiva", "Revision proxima", "Revision prioritaria",
                    "No debe seguir usandose sin evaluacion", "No debe seguir usandose"]

# Definicion declarativa de cada entidad editable. La plantilla
# conocimiento/crud.html dibuja la tabla y el formulario a partir de ella.
# Formatos de columna: tildes, num, decimal, booleano, nivel, regla, conteo:<clave_activas>.
ENTIDADES = {
    "areas": {
        "titulo": "Áreas", "singular": "área", "id": "id_area", "filtro_area": False, "estado": None,
        "listar": "listar_areas", "crear": "crear_area", "actualizar": "actualizar_area",
        "columnas": [("id_area", "ID", "num"), ("nombre", "Nombre", "tildes"),
                     ("descripcion", "Descripción", "tildes"),
                     ("preguntas", "Preguntas activas", "conteo:preguntas_activas"),
                     ("reglas", "Reglas activas", "conteo:reglas_activas"),
                     ("tiene_entrada", "Pregunta de entrada", "booleano")],
        "campos": [
            {"nombre": "nombre", "etiqueta": "Nombre del área", "tipo": "texto", "requerido": True, "max": 100},
            {"nombre": "descripcion", "etiqueta": "Descripción", "tipo": "area_texto", "ancho": True},
        ],
    },
    "preguntas": {
        "titulo": "Preguntas", "singular": "pregunta", "id": "id_pregunta", "filtro_area": True,
        "estado": "cambiar_estado_pregunta",
        "listar": "listar_preguntas", "crear": "crear_pregunta", "actualizar": "actualizar_pregunta",
        "columnas": [("id_pregunta", "ID", "num"), ("area", "Área", "tildes"),
                     ("enunciado", "Enunciado", "tildes"), ("sintoma_evaluado", "Síntoma evaluado", "tildes"),
                     ("es_entrada", "Entrada", "booleano"), ("reglas", "Reglas", "num")],
        "campos": [
            {"nombre": "id_area", "etiqueta": "Área", "tipo": "seleccion", "opciones": "areas", "requerido": True},
            {"nombre": "sintoma_evaluado", "etiqueta": "Síntoma evaluado", "tipo": "texto", "requerido": True},
            {"nombre": "enunciado", "etiqueta": "Enunciado de la pregunta", "tipo": "area_texto",
             "requerido": True, "ancho": True},
            {"nombre": "es_entrada", "etiqueta": "Es la pregunta de entrada del área", "tipo": "casilla"},
        ],
    },
    "hipotesis": {
        "titulo": "Hipótesis", "singular": "hipótesis", "id": "id_hipotesis", "filtro_area": False, "estado": None,
        "listar": "listar_hipotesis", "crear": "crear_hipotesis", "actualizar": "actualizar_hipotesis",
        "columnas": [("id_hipotesis", "ID", "num"), ("nombre", "Nombre", "tildes"),
                     ("descripcion", "Descripción", "tildes"), ("area", "Área", "tildes"),
                     ("reglas", "Reglas activas", "conteo:reglas_activas")],
        "campos": [
            {"nombre": "nombre", "etiqueta": "Nombre de la hipótesis de falla", "tipo": "texto",
             "requerido": True, "max": 200, "ancho": True},
            {"nombre": "descripcion", "etiqueta": "Descripción", "tipo": "area_texto", "ancho": True},
        ],
    },
    "reglas": {
        "titulo": "Reglas", "singular": "regla", "id": "id_regla", "filtro_area": True,
        "estado": "cambiar_estado_regla",
        "listar": "listar_reglas", "crear": "crear_regla", "actualizar": "actualizar_regla",
        "columnas": [("codigo", "Código", "regla"), ("area", "Área", "tildes"),
                     ("enunciado", "SI (pregunta)", "tildes"), ("hipotesis", "ENTONCES (hipótesis)", "tildes"),
                     ("nivel_atencion", "Nivel de atención", "nivel"), ("gravedad", "Grav.", "num"),
                     ("peso", "Peso", "decimal"), ("version", "Versión", "num")],
        "campos": [
            {"nombre": "codigo", "etiqueta": "Código", "tipo": "texto", "max": 10,
             "ayuda": "Si se deja vacío se asigna el siguiente código."},
            {"nombre": "nivel_atencion", "etiqueta": "Nivel de atención", "tipo": "seleccion",
             "opciones": "niveles", "requerido": True},
            {"nombre": "gravedad", "etiqueta": "Gravedad (1 a 4)", "tipo": "seleccion", "opciones": "gravedades",
             "ayuda": "Vacío: se deduce del nivel de atención."},
            {"nombre": "peso", "etiqueta": "Peso del gránulo", "tipo": "numero", "paso": "0.05", "min": "0.05",
             "max": "2", "ayuda": "Vacío: 0,8 + 0,1 × gravedad."},
            {"nombre": "id_pregunta", "etiqueta": "SI: pregunta (condición)", "tipo": "seleccion",
             "opciones": "preguntas", "requerido": True, "ancho": True},
            {"nombre": "id_hipotesis", "etiqueta": "ENTONCES: hipótesis (conclusión)", "tipo": "seleccion",
             "opciones": "hipotesis", "requerido": True, "ancho": True},
            {"nombre": "recomendacion", "etiqueta": "Recomendación", "tipo": "area_texto",
             "requerido": True, "ancho": True},
        ],
    },
}
_ENTEROS = {"id_area", "id_pregunta", "id_hipotesis", "gravedad"}


def _svc():
    return servicio("conocimiento")


def _catalogos(entidad):
    """Opciones de las listas desplegables que necesita la entidad. Cada
    catalogo es una lista de grupos (etiqueta_grupo | None, [(valor, texto)])."""
    svc = _svc()
    cat = {"areas": [(None, [(a["id_area"], tildes(a["nombre"])) for a in svc.listar_areas()])]}
    if entidad == "reglas":
        opciones = svc.opciones_regla() if hasattr(svc, "opciones_regla") else {}
        grupos = {}
        for p in svc.listar_preguntas():
            if p.get("es_entrada"):
                continue
            texto = f"P{p['id_pregunta']} · {tildes(p['enunciado'])}" + ("" if p.get("activa", True) else " (inactiva)")
            grupos.setdefault(tildes(p.get("area", "")), []).append((p["id_pregunta"], texto))
        cat["preguntas"] = list(grupos.items())
        cat["hipotesis"] = [(None, [(h["id_hipotesis"], f"H{h['id_hipotesis']} · {tildes(h['nombre'])}")
                                    for h in svc.listar_hipotesis()])]
        cat["niveles"] = [(None, [(n, tildes(n)) for n in opciones.get("niveles_atencion", NIVELES_RESPALDO)])]
        cat["gravedades"] = [(None, [(g, str(g)) for g in opciones.get("gravedades", [1, 2, 3, 4])])]
    return cat


def _datos_formulario(spec, form):
    datos = {}
    for campo in spec["campos"]:
        nombre, tipo = campo["nombre"], campo["tipo"]
        if tipo == "casilla":
            datos[nombre] = form.get(nombre) == "1"
            continue
        valor = (form.get(nombre) or "").strip()
        if campo.get("requerido") and not valor:
            raise ValueError(f"El campo «{campo['etiqueta']}» es obligatorio.")
        if not valor:
            datos[nombre] = None
        elif nombre in _ENTEROS:
            datos[nombre] = int(valor)
        elif tipo == "numero":
            try:
                datos[nombre] = float(valor.replace(",", "."))
            except ValueError:
                raise ValueError(f"El campo «{campo['etiqueta']}» debe ser un número.")
        else:
            datos[nombre] = valor
    return datos


def _listar(spec, id_area):
    metodo = getattr(_svc(), spec["listar"])
    return metodo(id_area=id_area) if spec["filtro_area"] and id_area else metodo()


def _pantalla(entidad, form_valores=None, editar_id=None, estado_http=200):
    spec = ENTIDADES[entidad]
    id_area = request.args.get("area", type=int) if spec["filtro_area"] else None
    filas = _listar(spec, id_area)
    if editar_id is None:
        editar_id = request.args.get("editar", type=int)
    if form_valores is None and editar_id:
        form_valores = next((f for f in filas if f.get(spec["id"]) == editar_id), None)
        if form_valores is None and id_area:
            form_valores = next((f for f in _listar(spec, None) if f.get(spec["id"]) == editar_id), None)
        if form_valores is None:
            abort(404)
    if form_valores is None and id_area:
        form_valores = {"id_area": id_area}
    activas = sum(1 for f in filas if f.get("activa", True))
    abierto = bool(editar_id) or estado_http != 200 or request.args.get("nuevo") == "1"
    return render_template("conocimiento/crud.html", entidad=entidad, spec=spec, filas=filas,
                           catalogos=_catalogos(entidad), valores=form_valores or {},
                           editar_id=editar_id, id_area=id_area, activas=activas,
                           abierto=abierto), estado_http


def _volver(entidad):
    area = request.args.get("area", type=int)
    return redirect(url_for("conocimiento.lista", entidad=entidad, area=area))


# ------------------------------------------------------------------ rutas
@bp.get("/")
@bp.get("")
@rol_requerido("ingeniero")
def resumen():
    try:
        conteos = _svc().resumen()
        hallazgos = _svc().validar()
        areas = _svc().listar_areas()
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
        conteos, hallazgos, areas = {}, [], []
    return render_template("conocimiento/resumen.html", conteos=conteos, hallazgos=hallazgos, areas=areas)


@bp.get("/<any(areas, preguntas, hipotesis, reglas):entidad>")
@rol_requerido("ingeniero")
def lista(entidad):
    return _pantalla(entidad)


@bp.post("/<any(areas, preguntas, hipotesis, reglas):entidad>")
@rol_requerido("ingeniero")
def crear(entidad):
    spec = ENTIDADES[entidad]
    try:
        datos = _datos_formulario(spec, request.form)
        nuevo_id = getattr(_svc(), spec["crear"])(datos, session.get("id_empleado"))
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
        return _pantalla(entidad, form_valores=request.form.to_dict(), estado_http=400)
    flash(f"{spec['singular'].capitalize()} creada correctamente (ID {nuevo_id}).", "exito")
    return _volver(entidad)


@bp.post("/<any(areas, preguntas, hipotesis, reglas):entidad>/<int:id_registro>")
@rol_requerido("ingeniero")
def actualizar(entidad, id_registro):
    spec = ENTIDADES[entidad]
    try:
        datos = _datos_formulario(spec, request.form)
        getattr(_svc(), spec["actualizar"])(id_registro, datos, session.get("id_empleado"))
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
        return _pantalla(entidad, form_valores=request.form.to_dict(), editar_id=id_registro,
                         estado_http=400)
    extra = " La versión de la regla se incrementó." if entidad == "reglas" else ""
    flash(f"Cambios guardados.{extra}", "exito")
    return _volver(entidad)


@bp.post("/<any(preguntas, reglas):entidad>/<int:id_registro>/estado")
@rol_requerido("ingeniero")
def cambiar_estado(entidad, id_registro):
    spec = ENTIDADES[entidad]
    activa = request.form.get("activa") == "1"
    try:
        getattr(_svc(), spec["estado"])(id_registro, activa, session.get("id_empleado"))
        flash(f"{spec['singular'].capitalize()} {'activada' if activa else 'desactivada'}.", "exito")
    except ERRORES_USUARIO as exc:
        flash(mensaje(exc), "error")
    return _volver(entidad)


@bp.get("/granulos")
@rol_requerido("ingeniero")
def granulos_inicio():
    hipotesis = _svc().listar_hipotesis()
    if not hipotesis:
        flash("Aún no hay hipótesis registradas.", "info")
        return redirect(url_for("conocimiento.lista", entidad="hipotesis"))
    return redirect(url_for("conocimiento.granulos", id_hipotesis=hipotesis[0]["id_hipotesis"]))


@bp.get("/hipotesis/<int:id_hipotesis>/granulos")
@rol_requerido("ingeniero")
def granulos(id_hipotesis):
    try:
        datos = _svc().granulos_por_hipotesis(id_hipotesis)
    except ERRORES_USUARIO:
        abort(404)
    return render_template("conocimiento/granulos.html", datos=datos, id_hipotesis=id_hipotesis,
                           hipotesis=_svc().listar_hipotesis())
