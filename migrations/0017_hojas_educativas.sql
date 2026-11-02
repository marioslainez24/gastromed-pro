-- GastroMed Pro · Migración 0017 · v0.21.0: hojas educativas y dietas para pacientes (pedido del Dr. Lainez)
-- El médico escribe sus hojas («Dieta para reflujo», «Dieta rica en fibra»…) y las imprime o envía por correo al paciente.
CREATE TABLE edu_handouts (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  title       TEXT NOT NULL,
  body        TEXT NOT NULL,
  active      INTEGER NOT NULL DEFAULT 1,
  reviewed    INTEGER NOT NULL DEFAULT 1,       -- 0 = ejemplo cargado que el médico aún no revisó (no se puede entregar)
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;
CREATE INDEX edu_handouts_org ON edu_handouts(org_id, active, title);

-- Registro de qué hoja se entregó a cada paciente (copia del título y del texto del momento).
CREATE TABLE patient_handouts (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  patient_id  TEXT NOT NULL REFERENCES patients(id),
  handout_id  TEXT NOT NULL REFERENCES edu_handouts(id),
  title       TEXT NOT NULL,
  body        TEXT NOT NULL,
  via         TEXT NOT NULL CHECK (via IN ('impresa','correo')),
  given_by    TEXT NOT NULL REFERENCES users(id),
  given_at    TEXT NOT NULL
) STRICT;
CREATE INDEX patient_handouts_patient ON patient_handouts(patient_id, given_at);
CREATE TRIGGER patient_handouts_immutable_u BEFORE UPDATE ON patient_handouts BEGIN SELECT RAISE(ABORT, 'registro_inmutable'); END;
CREATE TRIGGER patient_handouts_immutable_d BEFORE DELETE ON patient_handouts BEGIN SELECT RAISE(ABORT, 'registro_inmutable'); END;
