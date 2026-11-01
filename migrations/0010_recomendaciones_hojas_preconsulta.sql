-- v0.13.0: recomendaciones por diagnóstico, hojas de preparación/consentimiento y preconsulta de enfermería.
ALTER TABLE clinic_settings ADD COLUMN endo_recs TEXT;            -- JSON {texto del diagnóstico: recomendación del médico}
ALTER TABLE clinic_settings ADD COLUMN proc_sheets TEXT;          -- JSON {tipo de estudio: {"prep": texto, "consent": texto}}

-- Preconsulta: signos vitales y motivo registrados por enfermería mientras el paciente espera; pasan a la nota.
CREATE TABLE appointment_intake (
  appointment_id  TEXT PRIMARY KEY REFERENCES appointments(id),
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  vitals          TEXT NOT NULL,     -- JSON {clave: valor}
  motivo          TEXT,
  recorded_by     TEXT NOT NULL REFERENCES users(id),
  recorded_at     TEXT NOT NULL,
  updated_at      TEXT NOT NULL
) STRICT;

INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'preconsulta.registrar' FROM roles WHERE code IN ('propietario','medico','enfermeria');
