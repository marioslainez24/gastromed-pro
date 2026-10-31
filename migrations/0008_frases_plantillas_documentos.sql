-- v0.10.0: frases predefinidas, plantillas de nota y documentos clínicos (incapacidad, constancia, referencia).

-- Frases que se insertan con un clic en los campos de texto (notas e informes). field = clave del campo o '*' para cualquiera.
CREATE TABLE phrases (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  field       TEXT NOT NULL DEFAULT '*',
  title       TEXT NOT NULL,
  body        TEXT NOT NULL,
  position    INTEGER NOT NULL DEFAULT 0,
  active      INTEGER NOT NULL DEFAULT 1,
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;
CREATE INDEX phrases_org ON phrases(org_id, active, field);

-- Plantillas de nota: rellenan varios campos de un borrador a la vez (solo los vacíos).
CREATE TABLE note_templates (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  name        TEXT NOT NULL,
  template    TEXT NOT NULL CHECK (template IN ('soap','narrativa','ambas')),
  fields      TEXT NOT NULL,            -- JSON {campo: texto}
  active      INTEGER NOT NULL DEFAULT 1,
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;
CREATE INDEX note_templates_org ON note_templates(org_id, active);

-- Documentos clínicos emitidos. Inmutables: solo se pueden anular con motivo.
CREATE TABLE clinical_documents (
  id             TEXT PRIMARY KEY,
  org_id         TEXT NOT NULL REFERENCES organizations(id),
  patient_id     TEXT NOT NULL REFERENCES patients(id),
  kind           TEXT NOT NULL CHECK (kind IN ('incapacidad','constancia','referencia','libre')),
  title          TEXT NOT NULL,
  data           TEXT NOT NULL,          -- JSON con los datos estructurados
  body           TEXT NOT NULL,          -- texto final del documento
  author_id      TEXT NOT NULL REFERENCES users(id),
  issued_at      TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'emitido' CHECK (status IN ('emitido','anulado')),
  voided_at      TEXT,
  voided_by      TEXT REFERENCES users(id),
  void_reason    TEXT
) STRICT;
CREATE INDEX clinical_documents_patient ON clinical_documents(patient_id, issued_at);
CREATE TRIGGER clinical_documents_only_void BEFORE UPDATE ON clinical_documents
WHEN NOT (OLD.status = 'emitido' AND NEW.status = 'anulado' AND NEW.void_reason IS NOT NULL AND NEW.voided_by IS NOT NULL
          AND NEW.body = OLD.body AND NEW.data = OLD.data AND NEW.title = OLD.title AND NEW.kind = OLD.kind
          AND NEW.patient_id = OLD.patient_id AND NEW.issued_at = OLD.issued_at AND NEW.author_id = OLD.author_id
          AND NEW.content_sha256 = OLD.content_sha256)
BEGIN SELECT RAISE(ABORT, 'documento_inmutable'); END;
CREATE TRIGGER clinical_documents_no_delete BEFORE DELETE ON clinical_documents
BEGIN SELECT RAISE(ABORT, 'documentos_no_se_eliminan'); END;
