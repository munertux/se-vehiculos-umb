-- 06_semillas.sql
-- Datos semilla: los tres roles del sistema. Idempotente.
-- Los usuarios se crean con scripts/crear_usuario.py (nunca se guardan
-- contrasenas en el repositorio).

INSERT INTO rol (id_rol, nombre) VALUES
    (1, 'Consultante'),
    (2, 'Ingeniero del conocimiento'),
    (3, 'Administrador')
ON CONFLICT (id_rol) DO UPDATE SET nombre = EXCLUDED.nombre;
