-- GastroMed Pro · Migración 0016 · v0.20.0: personal de endoscopia (pedido del Dr. Lainez)
-- Médicos endoscopistas y asistentes que se eligen con menús en el informe. El dueño de la cuenta queda como primer endoscopista.
-- En el informe se guarda el NOMBRE (copia del momento): cambiar o desactivar a alguien aquí no altera informes ya hechos.
CREATE TABLE endo_staff (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  role        TEXT NOT NULL CHECK (role IN ('medico','asistente')),
  name        TEXT NOT NULL,
  detail      TEXT,                       -- p. ej., «Licenciada en enfermería»
  active      INTEGER NOT NULL DEFAULT 1,
  position    INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL
) STRICT;
CREATE INDEX endo_staff_org ON endo_staff(org_id, role, active, position);
INSERT INTO endo_staff(id, org_id, role, name, position, created_at)
  SELECT lower(hex(randomblob(16))), org_id, 'medico', doctor_display_name, 0, strftime('%Y-%m-%dT%H:%M:%SZ', 'now') FROM clinic_settings;
