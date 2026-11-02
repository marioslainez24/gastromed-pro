-- GastroMed Pro · Migración 0015 · v0.19.0: recetas frecuentes del médico
-- El médico guarda sus esquemas habituales (nombre + medicamentos con la dosis que él escribe) y los aplica con un clic en una
-- receta nueva. No es una receta emitida: no tiene paciente y se puede modificar o desactivar.
CREATE TABLE rx_templates (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  name        TEXT NOT NULL,
  items       TEXT NOT NULL,             -- JSON: lista de medicamentos con los mismos campos que prescription_items
  general_instructions TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;
CREATE INDEX rx_templates_org ON rx_templates(org_id, active, name);
