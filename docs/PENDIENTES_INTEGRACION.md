# Pendientes de integración

## De A1 (datos y lógica) para A7 (presentación) y el coordinador

1. **Servicios listos según el contrato.** Todos se construyen con `Conexion`. `ErrorNegocio` hereda de `ValueError`, así que las rutas `/api/*` actuales que capturan `ValueError` siguen funcionando.
2. **`ServicioDiagnostico`** acepta `ServicioDiagnostico(conexion)` y también el constructor antiguo `(repo_conocimiento, repo_atencion)`. Añadidos que no rompen nada:
   - `iniciar(..., id_consultante=None)`: si se pasa, valida que el vehículo sea suyo y guarda la atención a su nombre. Conviene pasarlo siempre desde la web, porque una consulta sin vehículo solo aparece en el historial si tiene `id_consultante`.
   - `testigos` y `codigos_obd` se reciben como lista o como texto separado por comas. Los códigos OBD se validan (`P0300`, `C1234`, `B0001`, `U0100`) y se guardan en mayúsculas.
   - `pertenece(id_atencion, id_consultante) -> bool`: úsenlo antes de `responder`, `finalizar` o `confirmar_falla`, que no reciben el consultante.
   - `estado(id_atencion)`: permite retomar una consulta. Si la memoria de trabajo se perdió (reinicio o varios workers de gunicorn), se reconstruye con las respuestas guardadas.
   - `testigos_disponibles()`: lista de testigos del tablero para el formulario.
   - `confirmar_falla` deja una sola hipótesis confirmada por atención y valida que pertenezca al diagnóstico.
3. **`ServicioVehiculos.opciones()`** devuelve listas de valores en minúsculas (`gasolina`, `diesel`, …). Para mostrar etiquetas existe `opciones_etiquetadas()` (`[{"valor", "etiqueta"}]`), y cada vehículo trae `combustible_etiqueta` y `transmision_etiqueta`.
4. **`ServicioAdministracion`**: los métodos de usuarios aceptan un `id_empleado=None` opcional al final para registrar en la bitácora quién hizo el cambio (`crear_usuario`, `cambiar_rol`, `bloquear`, `desbloquear`, `activar`, `restablecer_clave`). Se recomienda pasar `session["id_empleado"]`. `restaurar_conocimiento(sql)` solo aplica los INSERT de las tablas de conocimiento como upsert (no borra nada), ignora los datos transaccionales del respaldo y rechaza cualquier otra sentencia. Extras disponibles: `respaldo_conocimiento_sql()`, `obtener_usuario(id)` y `restablecer_clave(id, clave)`.
5. **`ServicioConocimiento`**: `crear_x(datos, id_empleado) -> id`, `actualizar_x(id, datos, id_empleado)` y `cambiar_estado_x(id, activa, id_empleado)`. Extras: `opciones_regla()`, `obtener_area`, `obtener_pregunta`, `obtener_hipotesis`. En las reglas, si `gravedad` o `peso` llegan vacíos, se deducen del nivel de atención (peso = 0,8 + 0,1 × gravedad). Cada elemento de `granulos_por_hipotesis` trae además la clave `activa`. Cada elemento de `validar()` es `{"tipo", "entidad", "id", "mensaje"}`.
6. **Contraseñas:** mínimo 8 caracteres con letras y números (`validar_clave` en `servicio_autenticacion.py`).
7. **`Conexion`** reutiliza una conexión por hilo, así que es seguro compartir una sola instancia en `app.extensions`.

## Para el coordinador

- **Producción (Azure):** ejecutar `python scripts/aplicar_sql.py` (aplica 05 y 06; son idempotentes y no borran datos). Después, crear los usuarios con `python scripts/crear_usuario.py <usuario> <rol> "<nombres>"`. La clave generada se imprime una sola vez.
- **Archivo fuera de lo asignado:** `pruebas/apoyo_bd.py` (fixtures compartidas; no es un archivo de pruebas). Lo importan los `test_dao*`, `test_servicios*` y `test_motor*`. No se creó `conftest.py` para no chocar con A7.
- **Esquemas de prueba:** las pruebas crean los esquemas `se_pruebas` y `se_pruebas_motor` en la BD de `DATABASE_URL` (DROP/CREATE solo de esos esquemas) y no tocan `public`. **No ejecutar pytest contra la base de producción.**
