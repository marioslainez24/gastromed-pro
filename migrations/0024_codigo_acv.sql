-- NeuroMed Pro · Migración 0024 · v1.0.0: registro del Código ACV por paciente.
-- Borrador editable mientras se atiende; al finalizar queda inmutable (como las notas y los informes).
CREATE TABLE stroke_codes (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES organizations(id),
  patient_id    TEXT NOT NULL REFERENCES patients(id),
  on_date       TEXT NOT NULL,                 -- fecha local de la atención (AAAA-MM-DD)
  data          TEXT NOT NULL,                 -- JSON con tiempos, evaluación, contraindicaciones y notas
  summary       TEXT,                          -- resumen escrito al finalizar
  status        TEXT NOT NULL DEFAULT 'borrador' CHECK (status IN ('borrador','finalizado')),
  version       INTEGER NOT NULL DEFAULT 1,
  created_by    TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  finalized_by  TEXT REFERENCES users(id),
  finalized_at  TEXT
) STRICT;
CREATE INDEX stroke_codes_patient ON stroke_codes(patient_id, created_at);
CREATE INDEX stroke_codes_org ON stroke_codes(org_id, created_at);
CREATE TRIGGER stroke_codes_finalized_immutable BEFORE UPDATE ON stroke_codes
WHEN OLD.status = 'finalizado' BEGIN SELECT RAISE(ABORT, 'codigo_acv_finalizado_inmutable'); END;
CREATE TRIGGER stroke_codes_no_delete BEFORE DELETE ON stroke_codes BEGIN SELECT RAISE(ABORT, 'codigo_acv_no_se_borra'); END;
