-- 05_transaccional.sql
-- Base transaccional ampliada: usuarios, roles, consultantes, empleados,
-- vehiculos, datos adicionales de la atencion y bitacora del conocimiento.
-- Idempotente: se puede ejecutar varias veces sobre una base que ya tiene
-- 01/02 con datos y atenciones. No borra nada; las columnas nuevas de
-- tablas existentes son NULLables.

SET client_encoding = 'UTF8';

-- ===================== SEGURIDAD =====================

CREATE TABLE IF NOT EXISTS rol (
    id_rol  INTEGER PRIMARY KEY,
    nombre  VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario        SERIAL PRIMARY KEY,
    id_rol            INTEGER NOT NULL REFERENCES rol(id_rol),
    nombre_usuario    VARCHAR(40) NOT NULL UNIQUE,
    contrasena_hash   TEXT NOT NULL,
    estado            VARCHAR(10) NOT NULL DEFAULT 'activo'
                      CHECK (estado IN ('activo', 'inactivo', 'bloqueado')),
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta   TIMESTAMP NULL,
    ultimo_acceso     TIMESTAMP NULL,
    creado            TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consultante (
    id_consultante SERIAL PRIMARY KEY,
    id_usuario     INTEGER NOT NULL UNIQUE REFERENCES usuario(id_usuario),
    nombres        VARCHAR(120) NOT NULL,
    correo         VARCHAR(254),
    telefono       VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS empleado (
    id_empleado SERIAL PRIMARY KEY,
    id_usuario  INTEGER NOT NULL UNIQUE REFERENCES usuario(id_usuario),
    nombres     VARCHAR(120) NOT NULL,
    cargo       VARCHAR(80)
);

-- ===================== VEHICULOS =====================

CREATE TABLE IF NOT EXISTS vehiculo (
    id_vehiculo    SERIAL PRIMARY KEY,
    id_consultante INTEGER NOT NULL REFERENCES consultante(id_consultante),
    placa          VARCHAR(10) NOT NULL,
    marca          VARCHAR(40) NOT NULL,
    modelo         VARCHAR(60) NOT NULL,
    combustible    VARCHAR(15) NOT NULL
                   CHECK (combustible IN ('gasolina', 'diesel', 'gas', 'hibrido', 'electrico')),
    transmision    VARCHAR(15) NOT NULL
                   CHECK (transmision IN ('manual', 'automatica', 'cvt')),
    anio           SMALLINT CHECK (anio BETWEEN 1950 AND 2100),
    kilometraje    INTEGER CHECK (kilometraje >= 0),
    activo         BOOLEAN NOT NULL DEFAULT TRUE,
    creado         TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vehiculo_consultante ON vehiculo(id_consultante);

-- ===================== ATENCION (columnas nuevas) =====================

ALTER TABLE atencion ADD COLUMN IF NOT EXISTS id_vehiculo INTEGER NULL;
ALTER TABLE atencion ADD COLUMN IF NOT EXISTS id_consultante INTEGER NULL;
ALTER TABLE atencion ADD COLUMN IF NOT EXISTS testigos_tablero TEXT NULL;
ALTER TABLE atencion ADD COLUMN IF NOT EXISTS codigos_obd TEXT NULL;

ALTER TABLE atencion_diagnostico ADD COLUMN IF NOT EXISTS reglas_activadas TEXT NULL;
ALTER TABLE atencion_diagnostico ADD COLUMN IF NOT EXISTS observacion TEXT NULL;

-- Las FK se agregan solo si no existen (ALTER ... ADD CONSTRAINT no admite IF NOT EXISTS).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'fk_atencion_vehiculo'
                     AND conrelid = 'atencion'::regclass) THEN
        ALTER TABLE atencion ADD CONSTRAINT fk_atencion_vehiculo
            FOREIGN KEY (id_vehiculo) REFERENCES vehiculo(id_vehiculo);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'fk_atencion_consultante'
                     AND conrelid = 'atencion'::regclass) THEN
        ALTER TABLE atencion ADD CONSTRAINT fk_atencion_consultante
            FOREIGN KEY (id_consultante) REFERENCES consultante(id_consultante);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_atencion_vehiculo ON atencion(id_vehiculo);
CREATE INDEX IF NOT EXISTS idx_atencion_consultante ON atencion(id_consultante);

-- ===================== BITACORA DEL CONOCIMIENTO =====================

CREATE TABLE IF NOT EXISTS bitacora_conocimiento (
    id_bitacora SERIAL PRIMARY KEY,
    id_empleado INTEGER NULL REFERENCES empleado(id_empleado),
    entidad     VARCHAR(30) NOT NULL,     -- area | pregunta | hipotesis | regla | usuario
    id_registro INTEGER,
    id_regla    INTEGER NULL REFERENCES reglas(id_regla),
    accion      VARCHAR(12) NOT NULL
                CHECK (accion IN ('crear', 'modificar', 'activar', 'desactivar')),
    fecha       TIMESTAMP NOT NULL DEFAULT now(),
    detalle     TEXT
);
CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON bitacora_conocimiento(fecha DESC);
