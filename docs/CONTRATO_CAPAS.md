# Contrato entre capas (trabajo en paralelo)

Dos agentes trabajan al mismo tiempo sobre este repositorio y cada uno es dueño de archivos distintos. **Nadie edita archivos del otro**: si hace falta un cambio en un archivo ajeno, se anota en `docs/PENDIENTES_INTEGRACION.md`.

| Dueño | Archivos |
|---|---|
| **A1 – Datos y lógica** | `sql/05_transaccional.sql`, `sql/06_semillas.sql`, `scripts/*.py`, `app/datos/**`, `app/logica/**`, `pruebas/test_dao*.py`, `pruebas/test_servicios*.py`, `pruebas/test_motor*.py` |
| **A7 – Presentación** | `main.py`, `app/web/**` (blueprints Flask), `app/templates/**`, `app/static/**`, `pruebas/test_web*.py` |

Se mantienen las tres capas: la presentación solo llama a **servicios** de `app/logica`, los servicios usan **DAO** de `app/datos/dao`, y solo los DAO ejecutan SQL (por medio de `app/datos/conexion.Conexion`). El motor de inferencia actual (`motor_inferencia.py`, `memoria_trabajo.py`) **no se reescribe**.

## Modelo de datos nuevo (`sql/05_transaccional.sql`, idempotente con IF NOT EXISTS)
- `rol(id_rol PK, nombre UNIQUE)` → 1 Consultante, 2 Ingeniero del conocimiento, 3 Administrador
- `usuario(id_usuario PK, id_rol FK, nombre_usuario UNIQUE, contrasena_hash, estado CHECK in ('activo','inactivo','bloqueado'), intentos_fallidos INT default 0, bloqueado_hasta TIMESTAMP NULL, ultimo_acceso TIMESTAMP, creado TIMESTAMP default now())`
- `consultante(id_consultante PK, id_usuario FK UNIQUE, nombres, correo, telefono)`
- `empleado(id_empleado PK, id_usuario FK UNIQUE, nombres, cargo)`
- `vehiculo(id_vehiculo PK, id_consultante FK, placa, marca, modelo, combustible CHECK, transmision CHECK, anio, kilometraje, activo BOOL default true, creado)`
- `atencion` + columnas `id_vehiculo FK NULL`, `testigos_tablero TEXT`, `codigos_obd TEXT`
- `atencion_diagnostico` + columnas `reglas_activadas TEXT`, `observacion TEXT`
- `bitacora_conocimiento(id_bitacora PK, id_empleado FK NULL, entidad VARCHAR, id_registro INT, id_regla FK NULL, accion CHECK in ('crear','modificar','activar','desactivar'), fecha TIMESTAMP default now(), detalle TEXT)`
- `sql/06_semillas.sql`: inserta los 3 roles. Los usuarios de demostración se crean con `scripts/crear_usuario.py <usuario> <rol> <nombres> [--clave X]`, que hashea con `werkzeug.security.generate_password_hash`. **Nunca** se guarda una contraseña en el repositorio.

## Sesión web (lo que guarda la presentación en `flask.session`)
`{"id_usuario", "nombre_usuario", "rol": "consultante"|"ingeniero"|"administrador", "nombres", "id_consultante"|None, "id_empleado"|None}`. El servicio de autenticación devuelve exactamente ese diccionario.

## Servicios (firmas acordadas; A1 los implementa y A7 los consume)
Todos se construyen con `Conexion` (`ServicioX(conexion)`) y lanzan `app.logica.errores.ErrorNegocio(mensaje)` cuando algo no es válido.

`app/logica/servicio_autenticacion.py` → `ServicioAutenticacion`
- `autenticar(nombre_usuario, clave) -> dict` (sesión). Lanza `ErrorNegocio` con un mensaje claro si la clave es incorrecta, si el usuario está inactivo o si está bloqueado. Bloquea 15 min tras 5 intentos fallidos (RNF-03).
- `cambiar_clave(id_usuario, clave_actual, clave_nueva)`

`app/logica/servicio_vehiculos.py` → `ServicioVehiculos`
- `listar(id_consultante, incluir_inactivos=False) -> list[dict]`
- `obtener(id_consultante, id_vehiculo) -> dict`
- `crear(id_consultante, datos: dict) -> int`; `actualizar(id_consultante, id_vehiculo, datos)`; `desactivar(id_consultante, id_vehiculo)`
- `opciones() -> {"combustible": [...], "transmision": [...]}`

`app/logica/servicio_diagnostico.py` → `ServicioDiagnostico` (se extiende, no se rompe)
- `iniciar(id_area, id_vehiculo=None, testigos=None, codigos_obd=None) -> (id_atencion, pregunta)`
- `responder(...)`, `finalizar(...)`, `confirmar_falla(id_atencion, id_hipotesis, observacion=None)` (igual que hoy). El resultado ahora incluye `reglas_activadas` (lista de códigos R##) por hipótesis.

`app/logica/servicio_historial.py` → `ServicioHistorial`
- `historial(id_consultante) -> list[dict]` (fecha, vehículo, área, estado, hipótesis principal y probabilidad)
- `detalle(id_consultante, id_atencion) -> dict` (vehículo, área, testigos, OBD, respuestas en orden con certeza, top 5 con nivel, recomendación, reglas y falla confirmada). Es la base del reporte imprimible.

`app/logica/servicio_conocimiento.py` → `ServicioConocimiento` (rol ingeniero)
- `resumen() -> dict` (conteos)
- `listar_areas()`, `crear_area(datos, id_empleado)`, `actualizar_area(id, datos, id_empleado)`
- `listar_preguntas(id_area=None)`, `crear_pregunta(...)`, `actualizar_pregunta(...)`, `cambiar_estado_pregunta(id, activa, id_empleado)`
- `listar_hipotesis()`, `crear_hipotesis(...)`, `actualizar_hipotesis(...)`
- `listar_reglas(id_area=None)`, `obtener_regla(id)`, `crear_regla(...)`, `actualizar_regla(...)` (sube `version`), `cambiar_estado_regla(id, activa, id_empleado)`
- `granulos_por_hipotesis(id_hipotesis) -> dict` → `{"hipotesis", "area", "granulos": [{"tipo": "directo"|"rama", "id_pregunta", "enunciado", "codigo_regla", "peso", "nivel_atencion", "recomendacion"}]}`
- `validar() -> list[dict]` (reglas sin pregunta activa, hipótesis sin regla, reglas duplicadas pregunta-hipótesis, áreas sin pregunta de entrada)
- Cada creación o cambio escribe en `bitacora_conocimiento`.

`app/logica/servicio_administracion.py` → `ServicioAdministracion` (rol administrador)
- `listar_usuarios()`, `crear_usuario(nombre_usuario, clave, rol, nombres, correo=None, telefono=None, cargo=None) -> int` (crea también consultante o empleado)
- `cambiar_rol(id_usuario, rol)`, `bloquear(id_usuario)`, `desbloquear(id_usuario)`, `activar(id_usuario, activo: bool)`
- `auditoria(limite=200) -> list[dict]`
- `respaldo_sql() -> str` (script SQL con INSERT de las tablas de conocimiento y transaccionales, sin contraseñas en claro; los hash sí van) y `restaurar_conocimiento(sql: str)` opcional.

## Rutas web (A7)
- `/login`, `/logout`, `/` → redirige al panel según el rol
- Consultante: `/vehiculos`, `/vehiculos/nuevo`, `/vehiculos/<id>/editar`, `/consulta/nueva` (elige vehículo, área, testigos y OBD), `/consulta/<id>` (preguntas con la API existente), `/historial`, `/historial/<id>` (detalle + confirmar falla), `/historial/<id>/reporte` (versión para imprimir o guardar en PDF)
- Ingeniero: `/conocimiento` (resumen y validación), `/conocimiento/areas`, `/conocimiento/preguntas`, `/conocimiento/hipotesis`, `/conocimiento/reglas`, `/conocimiento/hipotesis/<id>/granulos`
- Administrador: `/admin/usuarios`, `/admin/auditoria`, `/admin/respaldos` (descarga `.sql`)
- Se conservan las rutas `/api/*` actuales y `/api/salud` pública.
- Decorador `rol_requerido(*roles)`. La sesión expira a los 15 minutos de inactividad (`PERMANENT_SESSION_LIFETIME` y refresco en cada petición).
