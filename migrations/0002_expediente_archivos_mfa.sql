-- GastroMed Pro · Migración 0002 · Antecedentes, medicamentos, problemas, archivos, MFA y usuarios

CREATE TABLE patient_history (
  id           TEXT PRIMARY KEY,
  patient_id   TEXT NOT NULL REFERENCES patients(id),
  category     TEXT NOT NULL CHECK (category IN ('personal','quirurgico','familiar','habito','hospitalizacion','procedimiento')),
  description  TEXT NOT NULL,
  when_text    TEXT,             -- fecha o época referida (texto libre: "2019", "infancia")
  notes        TEXT,
  active       INTEGER NOT NULL DEFAULT 1,
  recorded_by  TEXT NOT NULL REFERENCES users(id),
  recorded_at  TEXT NOT NULL,
  inactivated_by TEXT REFERENCES users(id),
  inactivated_at TEXT
) STRICT;
CREATE INDEX patient_history_patient ON patient_history(patient_id, category);
CREATE TRIGGER patient_history_no_delete BEFORE DELETE ON patient_history
BEGIN SELECT RAISE(ABORT, 'registros_clinicos_no_se_eliminan'); END;

CREATE TABLE patient_medications (
  id            TEXT PRIMARY KEY,
  patient_id    TEXT NOT NULL REFERENCES patients(id),
  name          TEXT NOT NULL,
  dose          TEXT,
  frequency     TEXT,
  route         TEXT,
  indication    TEXT,
  source        TEXT NOT NULL DEFAULT 'referido_paciente'
                  CHECK (source IN ('referido_paciente','prescrito_aqui','otro_medico')),
  status        TEXT NOT NULL DEFAULT 'activo' CHECK (status IN ('activo','suspendido')),
  stop_reason   TEXT,
  recorded_by   TEXT NOT NULL REFERENCES users(id),
  recorded_at   TEXT NOT NULL,
  stopped_by    TEXT REFERENCES users(id),
  stopped_at    TEXT
) STRICT;
CREATE INDEX patient_medications_patient ON patient_medications(patient_id, status);
CREATE TRIGGER patient_medications_no_delete BEFORE DELETE ON patient_medications
BEGIN SELECT RAISE(ABORT, 'registros_clinicos_no_se_eliminan'); END;

-- Conciliación: quién revisó la lista completa de medicamentos y cuándo
ALTER TABLE patients ADD COLUMN meds_reconciled_at TEXT;
ALTER TABLE patients ADD COLUMN meds_reconciled_by TEXT REFERENCES users(id);

CREATE TABLE patient_problems (
  id            TEXT PRIMARY KEY,
  patient_id    TEXT NOT NULL REFERENCES patients(id),
  description   TEXT NOT NULL,
  onset_text    TEXT,
  status        TEXT NOT NULL DEFAULT 'activo' CHECK (status IN ('activo','resuelto')),
  resolved_at   TEXT,
  resolved_by   TEXT REFERENCES users(id),
  recorded_by   TEXT NOT NULL REFERENCES users(id),
  recorded_at   TEXT NOT NULL
) STRICT;
CREATE INDEX patient_problems_patient ON patient_problems(patient_id, status);
CREATE TRIGGER patient_problems_no_delete BEFORE DELETE ON patient_problems
BEGIN SELECT RAISE(ABORT, 'registros_clinicos_no_se_eliminan'); END;

-- Archivos: el contenido se guarda cifrado fuera de la base de datos, con nombre aleatorio.
CREATE TABLE files (
  id             TEXT PRIMARY KEY,
  org_id         TEXT NOT NULL REFERENCES organizations(id),
  patient_id     TEXT NOT NULL REFERENCES patients(id),
  note_id        TEXT REFERENCES clinical_notes(id),
  category       TEXT NOT NULL CHECK (category IN ('laboratorio','imagen','endoscopia','patologia','referencia','documento','otro')),
  title          TEXT NOT NULL,
  study_date     TEXT,
  institution    TEXT,
  original_name  TEXT NOT NULL,
  mime           TEXT NOT NULL,
  size_bytes     INTEGER NOT NULL,
  sha256         TEXT NOT NULL,            -- huella del contenido original (sin cifrar)
  storage_name   TEXT NOT NULL UNIQUE,
  uploaded_by    TEXT NOT NULL REFERENCES users(id),
  uploaded_at    TEXT NOT NULL,
  archived_at    TEXT,
  archived_by    TEXT REFERENCES users(id),
  archive_reason TEXT
) STRICT;
CREATE INDEX files_patient ON files(patient_id, uploaded_at);
CREATE TRIGGER files_no_delete BEFORE DELETE ON files
BEGIN SELECT RAISE(ABORT, 'archivos_no_se_eliminan'); END;
CREATE TRIGGER files_only_archive BEFORE UPDATE ON files
WHEN NEW.sha256 <> OLD.sha256 OR NEW.storage_name <> OLD.storage_name OR NEW.patient_id <> OLD.patient_id
  OR NEW.uploaded_by <> OLD.uploaded_by OR NEW.uploaded_at <> OLD.uploaded_at
BEGIN SELECT RAISE(ABORT, 'archivo_inmutable'); END;

-- Usuarios: MFA (TOTP) y cambio obligatorio de contraseña
ALTER TABLE users ADD COLUMN mfa_secret_enc TEXT;
ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN mfa_last_counter INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN password_changed_at TEXT;

ALTER TABLE clinic_settings ADD COLUMN require_mfa INTEGER NOT NULL DEFAULT 0;

-- Desafío de segundo factor tras validar la contraseña (vida corta, intentos limitados)
CREATE TABLE mfa_challenges (
  token_hash  TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  next_url    TEXT,
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL,
  attempts    INTEGER NOT NULL DEFAULT 0,
  used_at     TEXT
) STRICT;
