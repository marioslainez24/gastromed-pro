-- GastroMed Pro · Migración 0020 · v0.26.0: plantillas de hallazgos por patología (del documento de Word del Dr. Lainez)
-- Cada plantilla es un texto del médico para un segmento del informe (esófago, estómago, colon…) o para las recomendaciones.
CREATE TABLE endo_templates (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  kind        TEXT NOT NULL CHECK (kind IN ('eda', 'colonoscopia', 'rectosigmoidoscopia')),
  section     TEXT NOT NULL CHECK (section IN ('esofago', 'ueg', 'estomago', 'duodeno', 'colon', 'rectosigmoides', 'recomendaciones')),
  title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
  body        TEXT NOT NULL CHECK (length(trim(body)) > 0),
  conclusion  TEXT,
  position    INTEGER NOT NULL DEFAULT 0,
  active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  TEXT REFERENCES users(id),
  seed_key    TEXT               -- plantilla original del programa (para agregar las nuevas sin duplicar); NULL = creada por el médico
) STRICT;
CREATE INDEX endo_templates_kind ON endo_templates(org_id, kind, active, position);
