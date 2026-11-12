# Arquitectura de la capa de datos (patrón DAO)

Documento de referencia para dibujar el diagrama de clases DAO del manual técnico. Se conservan las tres capas: **presentación** (`app/web`) → **lógica** (`app/logica`, servicios) → **datos** (`app/datos`, DAO y repositorios) → PostgreSQL. Solo `Conexion` ejecuta SQL; los DAO y los repositorios del motor son las únicas clases que le envían sentencias.

## 1. Clases de infraestructura

| Clase | Archivo | Responsabilidad |
|---|---|---|
| `Conexion` | `app/datos/conexion.py` | Lee `DATABASE_URL`. Reutiliza una conexión por hilo y reintenta una vez si la conexión se cayó. Métodos: `consultar(sql, parametros) -> list[dict]`, `ejecutar(sql, parametros) -> int`, `ejecutar_retornando(sql, parametros) -> dict`, `transaccion()` (context manager que entrega un cursor; hace commit o rollback), `cerrar()` |
| `BaseDAO` | `app/datos/dao/base_dao.py` | Clase base abstracta de todos los DAO. Atributo `_db: Conexion`, propiedad `conexion`. Ayudas protegidas: `_filas`, `_fila`, `_ejecutar`, `_retornando`, `_escalar`, `_set_dinamico` |
| `RepositorioConocimiento` | `app/datos/repositorio_conocimiento.py` | Consultas del motor de inferencia (no se reescribió). Se añadieron `codigos_de_reglas(ids)` y `area(id_area)` |
| `RepositorioAtencion` | `app/datos/repositorio_atencion.py` | Hereda de `AtencionDAO` (se conserva por compatibilidad con el constructor antiguo de `ServicioDiagnostico`) |

**Convención transaccional:** todo método público de un DAO acepta `tx=None`. Si el servicio abre `with conexion.transaccion() as tx:` y pasa `tx`, varias operaciones (por ejemplo, el cambio de una regla y su registro en la bitácora) se confirman juntas.

## 2. Clases DAO (todas heredan de `BaseDAO`)

Retorno: **E** = entidad (dataclass), **d** = `dict` (listados enriquecidos con JOIN), **int** = id o filas afectadas.

### RolDAO (`rol_dao.py`), tabla `rol`
- `listar() -> list[Rol]`
- `obtener(id_rol) -> Rol | None`

### UsuarioDAO (`usuario_dao.py`), tabla `usuario`
- `obtener(id_usuario) -> Usuario | None`
- `obtener_por_nombre(nombre_usuario) -> Usuario | None` (sin distinguir mayúsculas)
- `existe_nombre(nombre_usuario) -> bool`
- `listar_detallado() -> list[d]` (usuario + rol + consultante/empleado)
- `crear(id_rol, nombre_usuario, contrasena_hash, estado='activo') -> int`
- `cambiar_hash(id_usuario, contrasena_hash) -> int`
- `cambiar_rol(id_usuario, id_rol) -> int`
- `cambiar_estado(id_usuario, estado) -> int` (limpia intentos y bloqueo temporal)
- `registrar_intento_fallido(id_usuario, max_intentos, minutos_bloqueo) -> d` (atómico en SQL)
- `registrar_acceso(id_usuario) -> int`
- `liberar_bloqueo_vencido(id_usuario) -> int`
- `fijar_bloqueo_hasta(id_usuario, minutos) -> int`
- `eliminar(id_usuario) -> int`

### ConsultanteDAO (`consultante_dao.py`), tabla `consultante`
- `obtener(id_consultante)`, `obtener_por_usuario(id_usuario) -> Consultante | None`
- `listar() -> list[Consultante]`
- `crear(id_usuario, nombres, correo=None, telefono=None) -> int`
- `actualizar(id_consultante, datos) -> int`

### EmpleadoDAO (`empleado_dao.py`), tabla `empleado`
- `obtener(id_empleado)`, `obtener_por_usuario(id_usuario) -> Empleado | None`
- `listar() -> list[Empleado]`
- `crear(id_usuario, nombres, cargo=None) -> int`
- `actualizar(id_empleado, datos) -> int`

### VehiculoDAO (`vehiculo_dao.py`), tabla `vehiculo`
- `obtener(id_vehiculo) -> Vehiculo | None`
- `listar_por_consultante(id_consultante, incluir_inactivos=False) -> list[Vehiculo]`
- `buscar_placa_activa(placa, excluir_id=None) -> Vehiculo | None`
- `crear(id_consultante, datos) -> int`
- `actualizar(id_vehiculo, datos) -> int`
- `cambiar_activo(id_vehiculo, activo) -> int`

### AreaDAO (`area_dao.py`), tabla `areas`
- `obtener(id_area) -> Area | None`, `listar() -> list[Area]`
- `listar_con_conteos() -> list[d]`
- `existe_nombre(nombre, excluir_id=None) -> bool`
- `crear(nombre, descripcion='') -> int`, `actualizar(id_area, datos) -> int`
- `sin_pregunta_de_entrada() -> list[Area]`, `contar() -> int`

### PreguntaDAO (`pregunta_dao.py`), tabla `preguntas`
- `obtener(id_pregunta) -> Pregunta | None`
- `listar(id_area=None) -> list[d]`
- `entrada_del_area(id_area, solo_activa=True, excluir_id=None) -> Pregunta | None`
- `crear(datos) -> int`, `actualizar(id_pregunta, datos) -> int`
- `cambiar_activa(id_pregunta, activa) -> int`, `contar(solo_activas=False) -> int`

### HipotesisDAO (`hipotesis_dao.py`), tabla `hipotesis`
- `obtener(id_hipotesis) -> Hipotesis | None`
- `listar() -> list[d]` (con área y conteo de reglas)
- `existe_nombre(nombre, excluir_id=None) -> bool`
- `crear(nombre, descripcion='') -> int`, `actualizar(id_hipotesis, datos) -> int`
- `sin_regla_activa() -> list[Hipotesis]`, `areas_de(id_hipotesis) -> list[int]`, `contar() -> int`

### ReglaDAO (`regla_dao.py`), tabla `reglas`
- `obtener(id_regla)`, `obtener_por_codigo(codigo) -> Regla | None`
- `obtener_detalle(id_regla) -> d`, `listar(id_area=None) -> list[d]`
- `listar_por_hipotesis(id_hipotesis) -> list[Regla]`
- `codigos(ids_regla) -> dict[id_regla, codigo]`
- `existe_activa(id_pregunta, id_hipotesis, excluir_id=None) -> bool`
- `existe_codigo(codigo, excluir_id=None) -> bool`, `siguiente_codigo() -> str`
- `crear(datos) -> int`, `actualizar(id_regla, datos) -> int` (sube `version`), `cambiar_activa(id_regla, activa) -> int`
- Validación: `activas_con_pregunta_inactiva()`, `activas_sobre_pregunta_de_entrada()`, `duplicadas()`, `area_distinta_a_pregunta()` (todas `list[d]`)
- `contar(solo_activas=False) -> int`

### AtencionDAO (`atencion_dao.py`), tablas `atencion`, `atencion_respuesta`, `atencion_diagnostico`
- `abrir(id_area, id_vehiculo=None, testigos=None, codigos_obd=None, id_consultante=None) -> int`
- `obtener(id_atencion) -> Atencion | None`
- `propietario(id_atencion) -> id_consultante | None`
- `cerrar(id_atencion) -> int`
- `historial_por_consultante(id_consultante) -> list[d]`
- `guardar_respuesta(id_atencion, id_pregunta, respuesta, certeza, orden) -> int`
- `respuestas(id_atencion) -> list[d]`
- `guardar_diagnostico(id_atencion, resultados, codigos_por_hipotesis=None)` (reemplaza el diagnóstico y cierra la atención en una transacción)
- `diagnostico(id_atencion) -> list[d]`
- `confirmar_falla(id_atencion, id_hipotesis, observacion=None) -> int` (solo una hipótesis confirmada)
- `contar() -> int`, `eliminar(id_atencion) -> int`

### BitacoraDAO (`bitacora_dao.py`), tabla `bitacora_conocimiento`
- `registrar(entidad, id_registro, accion, id_empleado=None, id_regla=None, detalle=None) -> int`
- `listar(limite=200, entidad=None) -> list[d]` (con empleado, usuario y código de regla)
- `por_registro(entidad, id_registro) -> list[RegistroBitacora]`

### RespaldoDAO (`respaldo_dao.py`), lee el catálogo (`information_schema`, `pg_index`)
- `tablas_existentes() -> set`, `columnas(tabla)`, `llave_primaria(tabla)`, `columnas_serial(tabla)`
- `filas(tabla, columnas, orden) -> list[d]`
- `sentencias_insert(tabla, actualizar_si_existe=False) -> list[str]`
- `sentencias_secuencias(tabla) -> list[str]`
- `ejecutar_lote(sentencias) -> int` (una sola transacción)
- Función del módulo: `literal_sql(valor) -> str`

## 3. Entidades del dominio (`app/logica/entidades.py`; las de conocimiento en `modelos.py`)

| Entidad | Atributos |
|---|---|
| `Rol` | id_rol, nombre; propiedad `clave` (consultante, ingeniero o administrador) |
| `Usuario` | id_usuario, id_rol, nombre_usuario, contrasena_hash, estado, intentos_fallidos, bloqueado_hasta, ultimo_acceso, creado, bloqueo_vigente, minutos_restantes; propiedad `rol` |
| `Consultante` | id_consultante, id_usuario, nombres, correo, telefono |
| `Empleado` | id_empleado, id_usuario, nombres, cargo |
| `Vehiculo` | id_vehiculo, id_consultante, placa, marca, modelo, combustible, transmision, anio, kilometraje, activo, creado; propiedad `descripcion` |
| `Atencion` | id_atencion, id_area, fecha_inicio, fecha_fin, estado, id_vehiculo, id_consultante, testigos_tablero, codigos_obd |
| `RespuestaAtencion` | id_atencion, id_pregunta, respuesta, certeza, orden |
| `DiagnosticoAtencion` | id_atencion, id_hipotesis, puntaje, probabilidad, posicion, falla_confirmada, reglas_activadas, observacion |
| `RegistroBitacora` | id_bitacora, entidad, accion, fecha, id_empleado, id_registro, id_regla, detalle |
| `Area` (modelos.py) | id_area, nombre, descripcion |
| `Pregunta` (modelos.py) | id_pregunta, id_area, enunciado, sintoma_evaluado, es_entrada, activa |
| `Hipotesis` (modelos.py) | id_hipotesis, nombre, descripcion |
| `Regla` (modelos.py) | id_regla, codigo, id_pregunta, id_hipotesis, id_area, nivel_atencion, gravedad, recomendacion, peso, version, activa |

Constantes: `CLAVES_ROL`, `IDS_ROL`, `COMBUSTIBLES`, `TRANSMISIONES`, `NIVELES_ATENCION`, `ACCIONES_BITACORA`.

## 4. Relaciones

**Entre clases (para el diagrama UML):**
- `BaseDAO` ◁— generalización — los 12 DAO; `AtencionDAO` ◁— `RepositorioAtencion`.
- `BaseDAO` ◆→ `Conexion` (asociación 1: cada DAO usa una conexión).
- Cada DAO «crea / devuelve» su entidad: RolDAO→Rol, UsuarioDAO→Usuario, ConsultanteDAO→Consultante, EmpleadoDAO→Empleado, VehiculoDAO→Vehiculo, AreaDAO→Area, PreguntaDAO→Pregunta, HipotesisDAO→Hipotesis, ReglaDAO→Regla, AtencionDAO→Atencion, BitacoraDAO→RegistroBitacora.
- Servicios → DAO (dependencia):
  - `ServicioAutenticacion` → UsuarioDAO, ConsultanteDAO, EmpleadoDAO
  - `ServicioVehiculos` → VehiculoDAO, ConsultanteDAO
  - `ServicioDiagnostico` → RepositorioConocimiento, RepositorioAtencion (AtencionDAO), VehiculoDAO, MotorInferencia, MemoriaTrabajo
  - `ServicioHistorial` → AtencionDAO, VehiculoDAO, AreaDAO, ReglaDAO, RepositorioConocimiento
  - `ServicioConocimiento` → AreaDAO, PreguntaDAO, HipotesisDAO, ReglaDAO, BitacoraDAO, AtencionDAO, RepositorioConocimiento
  - `ServicioAdministracion` → UsuarioDAO, ConsultanteDAO, EmpleadoDAO, BitacoraDAO, RespaldoDAO
- Todos los servicios lanzan `ErrorNegocio` (`app/logica/errores.py`, subclase de `ValueError`).

**Entre entidades (cardinalidades del modelo relacional):**
- Rol 1 — N Usuario
- Usuario 1 — 0..1 Consultante; Usuario 1 — 0..1 Empleado
- Consultante 1 — N Vehiculo
- Vehiculo 0..1 — N Atencion; Consultante 0..1 — N Atencion
- Area 1 — N Atencion; Area 1 — N Pregunta; Area 1 — N Regla
- Atencion 1 — N RespuestaAtencion — N..1 Pregunta
- Atencion 1 — N DiagnosticoAtencion — N..1 Hipotesis
- Pregunta 1 — N Regla — N..1 Hipotesis
- Empleado 0..1 — N RegistroBitacora; Regla 0..1 — N RegistroBitacora

## 5. Tablas y columnas nuevas (`sql/05_transaccional.sql`, `sql/06_semillas.sql`)

Script idempotente: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS` y llaves foráneas agregadas solo si no existen. No contiene `DROP` y no borra datos.

| Tabla | Columnas |
|---|---|
| `rol` | id_rol PK, nombre UNIQUE. Semillas: 1 Consultante, 2 Ingeniero del conocimiento, 3 Administrador |
| `usuario` | id_usuario SERIAL PK, id_rol FK→rol, nombre_usuario UNIQUE, contrasena_hash, estado CHECK (activo, inactivo, bloqueado), intentos_fallidos default 0, bloqueado_hasta NULL, ultimo_acceso, creado default now() |
| `consultante` | id_consultante SERIAL PK, id_usuario FK UNIQUE, nombres, correo, telefono |
| `empleado` | id_empleado SERIAL PK, id_usuario FK UNIQUE, nombres, cargo |
| `vehiculo` | id_vehiculo SERIAL PK, id_consultante FK, placa, marca, modelo, combustible CHECK (gasolina, diesel, gas, hibrido, electrico), transmision CHECK (manual, automatica, cvt), anio CHECK 1950-2100, kilometraje CHECK ≥ 0, activo default true, creado |
| `bitacora_conocimiento` | id_bitacora SERIAL PK, id_empleado FK NULL, entidad (area, pregunta, hipotesis, regla, usuario, respaldo), id_registro, id_regla FK NULL, accion CHECK (crear, modificar, activar, desactivar), fecha default now(), detalle |
| `atencion` (+) | id_vehiculo FK NULL, **id_consultante FK NULL** (añadida), testigos_tablero TEXT, codigos_obd TEXT |
| `atencion_diagnostico` (+) | reglas_activadas TEXT (códigos R## separados por coma), observacion TEXT |

Índices: `idx_vehiculo_consultante`, `idx_atencion_vehiculo`, `idx_atencion_consultante`, `idx_bitacora_fecha`.

Aplicación: `python scripts/aplicar_sql.py` (aplica 05 y 06 sobre `DATABASE_URL`); `--todos` recrea también 01 y 02.
