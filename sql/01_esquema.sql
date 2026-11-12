-- 01_esquema.sql
-- Esquema de la base de conocimiento del Sistema Experto de Diagnostico
-- de Fallas en Vehiculos Automotores (UMB). Capa de datos, PostgreSQL.
-- Replica el modelo relacional de las Figuras 11 y 19 del manual tecnico
-- (version reducida para el prototipo de interfaz web: RF03).

DROP TABLE IF EXISTS atencion_diagnostico CASCADE;
DROP TABLE IF EXISTS atencion_respuesta CASCADE;
DROP TABLE IF EXISTS atencion CASCADE;
DROP TABLE IF EXISTS reglas CASCADE;
DROP TABLE IF EXISTS preguntas CASCADE;
DROP TABLE IF EXISTS hipotesis CASCADE;
DROP TABLE IF EXISTS areas CASCADE;
DROP TABLE IF EXISTS parametros_inferencia CASCADE;

-- ===================== BASE DE CONOCIMIENTO =====================

CREATE TABLE areas (
    id_area     INTEGER PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL,
    descripcion TEXT
);

CREATE TABLE hipotesis (
    id_hipotesis INTEGER PRIMARY KEY,
    nombre       VARCHAR(200) NOT NULL,
    descripcion  TEXT
);

CREATE TABLE preguntas (
    id_pregunta      INTEGER PRIMARY KEY,
    id_area          INTEGER NOT NULL REFERENCES areas(id_area),
    enunciado        TEXT NOT NULL,
    sintoma_evaluado TEXT NOT NULL,
    tipo_respuesta   VARCHAR(30) NOT NULL DEFAULT 'escala_certeza',
    es_entrada       BOOLEAN NOT NULL DEFAULT FALSE,
    activa           BOOLEAN NOT NULL DEFAULT TRUE
);

-- Tabla debil: relaciona cada pregunta especifica con la hipotesis
-- a la que aporta evidencia (granulo directo, peso 1.0 por defecto).
CREATE TABLE reglas (
    id_regla       INTEGER PRIMARY KEY,
    codigo         VARCHAR(10) NOT NULL UNIQUE,   -- R01 .. R68
    id_pregunta    INTEGER NOT NULL REFERENCES preguntas(id_pregunta),
    id_hipotesis   INTEGER NOT NULL REFERENCES hipotesis(id_hipotesis),
    id_area        INTEGER NOT NULL REFERENCES areas(id_area),
    nivel_atencion VARCHAR(40) NOT NULL,          -- Atencion preventiva | Revision proxima | Revision prioritaria | No debe seguir usandose [sin evaluacion]
    gravedad       SMALLINT NOT NULL,              -- 1..4, usado para desempate (Tabla 14)
    recomendacion  TEXT NOT NULL,
    peso           NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    version        INTEGER NOT NULL DEFAULT 1,
    activa         BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE parametros_inferencia (
    clave VARCHAR(40) PRIMARY KEY,
    valor NUMERIC(6,2) NOT NULL
);

-- ===================== BASE TRANSACCIONAL (minima, RNF-11) =====================

CREATE TABLE atencion (
    id_atencion   SERIAL PRIMARY KEY,
    id_area       INTEGER NOT NULL REFERENCES areas(id_area),
    fecha_inicio  TIMESTAMP NOT NULL DEFAULT now(),
    fecha_fin     TIMESTAMP,
    estado        VARCHAR(20) NOT NULL DEFAULT 'en_curso' -- en_curso | finalizada
);

CREATE TABLE atencion_respuesta (
    id_atencion  INTEGER NOT NULL REFERENCES atencion(id_atencion) ON DELETE CASCADE,
    id_pregunta  INTEGER NOT NULL REFERENCES preguntas(id_pregunta),
    respuesta    VARCHAR(20) NOT NULL,   -- si | probablemente_si | no_se | probablemente_no | no
    certeza      NUMERIC(3,2) NOT NULL,
    orden        INTEGER NOT NULL,
    PRIMARY KEY (id_atencion, id_pregunta)
);

CREATE TABLE atencion_diagnostico (
    id_atencion    INTEGER NOT NULL REFERENCES atencion(id_atencion) ON DELETE CASCADE,
    id_hipotesis   INTEGER NOT NULL REFERENCES hipotesis(id_hipotesis),
    puntaje        NUMERIC(8,4) NOT NULL,
    probabilidad   NUMERIC(6,4) NOT NULL,
    posicion       SMALLINT NOT NULL,
    falla_confirmada BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (id_atencion, id_hipotesis)
);

CREATE INDEX idx_preguntas_area ON preguntas(id_area);
CREATE INDEX idx_reglas_pregunta ON reglas(id_pregunta);
CREATE INDEX idx_reglas_hipotesis ON reglas(id_hipotesis);
