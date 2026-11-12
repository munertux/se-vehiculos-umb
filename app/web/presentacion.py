# -*- coding: utf-8 -*-
"""Utilidades de formato para la interfaz (solo presentacion).

La base de conocimiento se cargo sin tildes ("Revision proxima",
"diagnostico"...). ``tildes`` restituye la ortografia al mostrar el
texto, sin modificar los datos almacenados.
"""
import re
import unicodedata
from datetime import date, datetime

_PALABRAS = {
    "acompanada": "acompañada", "algun": "algún", "anomalia": "anomalía",
    "angulo": "ángulo", "area": "área", "areas": "áreas", "asi": "así",
    "automatica": "automática", "automatico": "automático", "bateria": "batería",
    "bujias": "bujías", "capo": "capó", "carroceria": "carrocería", "carter": "cárter",
    "ciguenal": "cigüeñal", "cinturon": "cinturón", "codigo": "código", "codigos": "códigos",
    "collarin": "collarín", "conexion": "conexión", "danado": "dañado", "danar": "dañar",
    "dano": "daño", "deposito": "depósito", "desempeno": "desempeño", "despues": "después",
    "desvia": "desvía", "diagnostico": "diagnóstico", "diagnosticos": "diagnósticos",
    "electrica": "eléctrica", "electricas": "eléctricas", "electrico": "eléctrico",
    "electricos": "eléctricos", "electronica": "electrónica", "electronicas": "electrónicas",
    "electronico": "electrónico", "electronicos": "electrónicos", "enfria": "enfría",
    "escaner": "escáner", "facil": "fácil", "habitaculo": "habitáculo",
    "hidraulica": "hidráulica", "hidraulico": "hidráulico", "hipotesis": "hipótesis",
    "homocinetica": "homocinética", "homocineticas": "homocinéticas", "kilometros": "kilómetros",
    "lineas": "líneas", "liquido": "líquido", "liquidos": "líquidos", "mas": "más",
    "maximo": "máximo", "mecanica": "mecánica", "mecanico": "mecánico", "metalico": "metálico",
    "modulo": "módulo", "multiple": "múltiple", "neumaticos": "neumáticos", "ningun": "ningún",
    "numero": "número", "parasita": "parásita", "perdida": "pérdida", "proxima": "próxima",
    "ralenti": "ralentí", "rapido": "rápido", "razon": "razón", "rele": "relé",
    "rotulas": "rótulas", "segun": "según", "senal": "señal", "simultaneamente": "simultáneamente",
    "simultaneas": "simultáneas", "sintoma": "síntoma", "sintomas": "síntomas",
    "tambien": "también", "tecnica": "técnica", "tecnico": "técnico", "toxicos": "tóxicos",
    "tuberia": "tubería", "tuberias": "tuberías", "usandose": "usándose", "vacio": "vacío",
    "valvula": "válvula", "vehiculo": "vehículo", "vehiculos": "vehículos", "via": "vía",
    "transmision": "transmisión", "presion": "presión", "suspension": "suspensión",
    "tension": "tensión", "compresion": "compresión", "contrapresion": "contrapresión",
    "admision": "admisión", "revision": "revisión", "diesel": "diésel", "hibrido": "híbrido",
    "contrasena": "contraseña", "contrasenas": "contraseñas", "anio": "año", "valido": "válido",
    "valida": "válida", "validos": "válidos", "numeros": "números", "unico": "único",
    "especifica": "específica", "especificas": "específicas", "comuniquese": "comuníquese",
    "guion": "guion", "evalua": "evalúa", "quedo": "quedó", "automaticamente": "automáticamente",
    "granulo": "gránulo", "granulos": "gránulos", "informacion": "información",
}
_ETIQUETAS = {"si": "Sí", "probablemente si": "Probablemente sí", "no se": "No sé"}
_PALABRA = re.compile(r"[A-Za-z]+")


def _restituir(m):
    palabra = m.group(0)
    baja = palabra.lower()
    nueva = _PALABRAS.get(baja)
    if nueva is None and len(baja) > 4 and baja.endswith("cion"):
        nueva = baja[:-4] + "ción"
    if nueva is None:
        return palabra
    if palabra.isupper() and len(palabra) > 1:
        return nueva.upper()
    if palabra[0].isupper():
        return nueva[0].upper() + nueva[1:]
    return nueva


def tildes(texto):
    if texto is None:
        return ""
    texto = str(texto)
    etiqueta = _ETIQUETAS.get(texto.strip().lower())
    if etiqueta:
        return etiqueta
    return _PALABRA.sub(_restituir, texto)


def clase_nivel(nivel):
    """'No debe seguir usandose' -> 'nivel-no-debe-seguir-usandose'."""
    base = unicodedata.normalize("NFD", str(nivel or "")).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    if base.startswith("no-debe-seguir-usandose"):
        base = "no-debe-seguir-usandose"
    return "nivel-" + base if base else ""


def es_critico(nivel):
    return clase_nivel(nivel) == "nivel-no-debe-seguir-usandose"


def fecha(valor, con_hora=True):
    if not valor:
        return "—"
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor)
        except ValueError:
            return valor
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def porcentaje(valor, fraccion=False):
    """Recibe la probabilidad en escala 0-100 (como la entrega el servicio
    de diagnostico) o 0-1 con ``fraccion=True``; devuelve '45,3 %'."""
    if valor is None or valor == "":
        return "—"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if fraccion:
        v *= 100
    return f"{v:.1f}".replace(".", ",") + " %"


def decimal(valor, cifras=2):
    """1.1 -> '1,10' (coma decimal, como se escribe en Colombia)."""
    try:
        return f"{float(valor):.{cifras}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def numero(valor):
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return valor if valor not in (None, "") else "—"


def lista(valor):
    """Normaliza texto separado por comas o listas a lista de cadenas."""
    if not valor:
        return []
    if isinstance(valor, (list, tuple, set)):
        return [str(v) for v in valor if str(v).strip()]
    return [p.strip() for p in re.split(r"[,;\n]", str(valor)) if p.strip()]


def instalar(app):
    app.jinja_env.filters.update(tildes=tildes, clase_nivel=clase_nivel, fecha=fecha,
                                 porcentaje=porcentaje, numero=numero, lista=lista,
                                 decimal=decimal)
    app.jinja_env.tests["critico"] = es_critico
