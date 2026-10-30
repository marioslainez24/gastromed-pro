-- GastroMed Pro · Migración 0001 · Esquema inicial (Fase 1, primer flujo)
-- Motor: SQLite 3.37+ (tablas STRICT). Todas las fechas/horas se guardan en UTC, formato ISO 8601.

CREATE TABLE organizations (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  created_at  TEXT NOT NULL
) STRICT;

CREATE TABLE sites (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  name        TEXT NOT NULL,
  address     TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL
) STRICT;

CREATE TABLE roles (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  code        TEXT NOT NULL,
  name        TEXT NOT NULL,
  is_system   INTEGER NOT NULL DEFAULT 1,
  UNIQUE (org_id, code)
) STRICT;

CREATE TABLE role_permissions (
  role_id     TEXT NOT NULL REFERENCES roles(id),
  permission  TEXT NOT NULL,
  PRIMARY KEY (role_id, permission)
) STRICT;

CREATE TABLE users (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
  full_name       TEXT NOT NULL,
  password_hash   TEXT NOT NULL,
  role_id         TEXT NOT NULL REFERENCES roles(id),
  is_practitioner INTEGER NOT NULL DEFAULT 0,
  active          INTEGER NOT NULL DEFAULT 1,
  failed_logins   INTEGER NOT NULL DEFAULT 0,
  locked_until    TEXT,
  created_at      TEXT NOT NULL,
  deactivated_at  TEXT,
  version         INTEGER NOT NULL DEFAULT 1
) STRICT;

-- Los usuarios nunca se borran: se desactivan para conservar la atribución histórica.
CREATE TRIGGER users_no_delete BEFORE DELETE ON users
BEGIN SELECT RAISE(ABORT, 'usuarios_no_se_eliminan'); END;

CREATE TABLE user_sites (
  user_id  TEXT NOT NULL REFERENCES users(id),
  site_id  TEXT NOT NULL REFERENCES sites(id),
  PRIMARY KEY (user_id, site_id)
) STRICT;

-- Sesiones en servidor. Solo se guarda el hash del token; el token real vive en la cookie.
CREATE TABLE sessions (
  token_hash   TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users(id),
  csrf_token   TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  revoked_at   TEXT,
  ip           TEXT,
  user_agent   TEXT
) STRICT;
CREATE INDEX sessions_user ON sessions(user_id);

CREATE TABLE login_attempts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ip         TEXT NOT NULL,
  email      TEXT,
  at         TEXT NOT NULL,
  success    INTEGER NOT NULL
) STRICT;
CREATE INDEX login_attempts_ip_at ON login_attempts(ip, at);

CREATE TABLE clinic_settings (
  org_id                 TEXT PRIMARY KEY REFERENCES organizations(id),
  doctor_display_name    TEXT NOT NULL,
  specialty              TEXT,
  license_number         TEXT,           -- colegiación (editable, sin valor por defecto)
  address                TEXT,
  phones                 TEXT,
  contact_email          TEXT,
  timezone               TEXT NOT NULL DEFAULT 'America/Tegucigalpa',
  currency               TEXT NOT NULL DEFAULT 'HNL',
  locale                 TEXT NOT NULL DEFAULT 'es-HN',
  phone_prefix           TEXT NOT NULL DEFAULT '+504',
  paper_size             TEXT NOT NULL DEFAULT 'carta' CHECK (paper_size IN ('carta','a4')),
  appointment_durations  TEXT NOT NULL,  -- JSON {tipo: minutos}
  updated_at             TEXT NOT NULL,
  updated_by             TEXT,
  version                INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE patients (
  id                       TEXT PRIMARY KEY,
  org_id                   TEXT NOT NULL REFERENCES organizations(id),
  mrn                      TEXT NOT NULL,           -- identificador interno legible (GM-000001)
  first_names              TEXT NOT NULL,
  last_names               TEXT NOT NULL,
  birth_date               TEXT,                    -- AAAA-MM-DD
  sex                      TEXT NOT NULL DEFAULT 'no_registrado'
                             CHECK (sex IN ('femenino','masculino','intersexual','no_registrado')),
  document_type            TEXT NOT NULL DEFAULT 'sin_documento'
                             CHECK (document_type IN ('dni','pasaporte','carne_residente','otro','sin_documento')),
  document_number          TEXT,
  phone                    TEXT,
  email                    TEXT,
  address                  TEXT,
  origin                   TEXT,                    -- procedencia
  emergency_contact_name   TEXT,
  emergency_contact_phone  TEXT,
  referring_physician      TEXT,
  payer                    TEXT,                    -- seguro / convenio / condición de pago
  -- Datos clínicos de cabecera (solo visibles con permiso clínico)
  allergy_status           TEXT NOT NULL DEFAULT 'no_investigado'
                             CHECK (allergy_status IN ('no_investigado','sin_alergias_conocidas','con_alergias')),
  clinical_alerts          TEXT,
  search_text              TEXT NOT NULL,
  merged_into              TEXT REFERENCES patients(id),
  created_at               TEXT NOT NULL,
  created_by               TEXT NOT NULL REFERENCES users(id),
  updated_at               TEXT NOT NULL,
  updated_by               TEXT NOT NULL REFERENCES users(id),
  version                  INTEGER NOT NULL DEFAULT 1,
  UNIQUE (org_id, mrn)
) STRICT;
CREATE UNIQUE INDEX patients_document_unique
  ON patients(org_id, document_type, document_number)
  WHERE document_number IS NOT NULL AND document_type <> 'sin_documento' AND merged_into IS NULL;
CREATE INDEX patients_org_search ON patients(org_id, search_text);

CREATE TRIGGER patients_no_delete BEFORE DELETE ON patients
BEGIN SELECT RAISE(ABORT, 'expedientes_no_se_eliminan'); END;

CREATE TABLE patient_allergies (
  id           TEXT PRIMARY KEY,
  patient_id   TEXT NOT NULL REFERENCES patients(id),
  substance    TEXT NOT NULL,
  reaction     TEXT,
  severity     TEXT NOT NULL DEFAULT 'desconocida'
                 CHECK (severity IN ('leve','moderada','grave','desconocida')),
  active       INTEGER NOT NULL DEFAULT 1,
  recorded_by  TEXT NOT NULL REFERENCES users(id),
  recorded_at  TEXT NOT NULL
) STRICT;

CREATE TABLE appointments (
  id               TEXT PRIMARY KEY,
  org_id           TEXT NOT NULL REFERENCES organizations(id),
  site_id          TEXT NOT NULL REFERENCES sites(id),
  practitioner_id  TEXT NOT NULL REFERENCES users(id),
  patient_id       TEXT NOT NULL REFERENCES patients(id),
  appt_type        TEXT NOT NULL CHECK (appt_type IN ('primera_vez','seguimiento','procedimiento','teleconsulta')),
  status           TEXT NOT NULL DEFAULT 'solicitada'
                     CHECK (status IN ('solicitada','confirmada','presente','en_consulta','atendida','cancelada','no_asistio')),
  starts_at        TEXT NOT NULL,
  ends_at          TEXT NOT NULL,
  admin_note       TEXT,     -- nota administrativa (no clínica)
  arrived_at       TEXT,
  created_at       TEXT NOT NULL,
  created_by       TEXT NOT NULL REFERENCES users(id),
  updated_at       TEXT NOT NULL,
  version          INTEGER NOT NULL DEFAULT 1,
  CHECK (ends_at > starts_at)
) STRICT;
CREATE INDEX appointments_practitioner_time ON appointments(practitioner_id, starts_at);
CREATE INDEX appointments_org_time ON appointments(org_id, starts_at);

-- Garantía en la propia base de datos: un profesional no puede tener dos citas activas que se crucen.
CREATE TRIGGER appointments_no_overlap_insert BEFORE INSERT ON appointments
WHEN NEW.status NOT IN ('cancelada','no_asistio') AND EXISTS (
  SELECT 1 FROM appointments a
  WHERE a.practitioner_id = NEW.practitioner_id
    AND a.status NOT IN ('cancelada','no_asistio')
    AND a.starts_at < NEW.ends_at AND a.ends_at > NEW.starts_at)
BEGIN SELECT RAISE(ABORT, 'cruce_de_horario'); END;

CREATE TRIGGER appointments_no_overlap_update BEFORE UPDATE OF starts_at, ends_at, practitioner_id, status ON appointments
WHEN NEW.status NOT IN ('cancelada','no_asistio') AND EXISTS (
  SELECT 1 FROM appointments a
  WHERE a.id <> NEW.id
    AND a.practitioner_id = NEW.practitioner_id
    AND a.status NOT IN ('cancelada','no_asistio')
    AND a.starts_at < NEW.ends_at AND a.ends_at > NEW.starts_at)
BEGIN SELECT RAISE(ABORT, 'cruce_de_horario'); END;

CREATE TRIGGER appointments_no_delete BEFORE DELETE ON appointments
BEGIN SELECT RAISE(ABORT, 'citas_no_se_eliminan'); END;

CREATE TABLE appointment_events (
  id              TEXT PRIMARY KEY,
  appointment_id  TEXT NOT NULL REFERENCES appointments(id),
  at              TEXT NOT NULL,
  user_id         TEXT NOT NULL REFERENCES users(id),
  action          TEXT NOT NULL,   -- creada, estado, reprogramada
  from_status     TEXT,
  to_status       TEXT,
  from_starts_at  TEXT,
  to_starts_at    TEXT,
  detail          TEXT
) STRICT;
CREATE TRIGGER appointment_events_immutable_u BEFORE UPDATE ON appointment_events
BEGIN SELECT RAISE(ABORT, 'historial_inmutable'); END;
CREATE TRIGGER appointment_events_immutable_d BEFORE DELETE ON appointment_events
BEGIN SELECT RAISE(ABORT, 'historial_inmutable'); END;

CREATE TABLE clinical_notes (
  id               TEXT PRIMARY KEY,
  org_id           TEXT NOT NULL REFERENCES organizations(id),
  patient_id       TEXT NOT NULL REFERENCES patients(id),
  appointment_id   TEXT REFERENCES appointments(id),
  author_id        TEXT NOT NULL REFERENCES users(id),
  kind             TEXT NOT NULL CHECK (kind IN ('primera','subsecuente')),
  template         TEXT NOT NULL CHECK (template IN ('soap','narrativa')),
  fields           TEXT NOT NULL,   -- JSON con las secciones de la nota
  status           TEXT NOT NULL DEFAULT 'borrador' CHECK (status IN ('borrador','finalizada')),
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  updated_by       TEXT NOT NULL REFERENCES users(id),
  finalized_at     TEXT,
  finalized_by     TEXT REFERENCES users(id),
  content_sha256   TEXT,            -- huella del contenido al finalizar
  version          INTEGER NOT NULL DEFAULT 1
) STRICT;
CREATE INDEX clinical_notes_patient ON clinical_notes(patient_id, created_at);

-- Una nota finalizada no puede modificarse ni borrarse; las correcciones van como adendas.
CREATE TRIGGER clinical_notes_finalized_immutable BEFORE UPDATE ON clinical_notes
WHEN OLD.status = 'finalizada'
BEGIN SELECT RAISE(ABORT, 'nota_finalizada_inmutable'); END;
CREATE TRIGGER clinical_notes_no_delete BEFORE DELETE ON clinical_notes
BEGIN SELECT RAISE(ABORT, 'notas_no_se_eliminan'); END;

CREATE TABLE note_addenda (
  id          TEXT PRIMARY KEY,
  note_id     TEXT NOT NULL REFERENCES clinical_notes(id),
  author_id   TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  text        TEXT NOT NULL
) STRICT;
CREATE TRIGGER note_addenda_immutable_u BEFORE UPDATE ON note_addenda
BEGIN SELECT RAISE(ABORT, 'adenda_inmutable'); END;
CREATE TRIGGER note_addenda_immutable_d BEFORE DELETE ON note_addenda
BEGIN SELECT RAISE(ABORT, 'adenda_inmutable'); END;

CREATE TABLE prescriptions (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES organizations(id),
  patient_id    TEXT NOT NULL REFERENCES patients(id),
  note_id       TEXT REFERENCES clinical_notes(id),
  author_id     TEXT NOT NULL REFERENCES users(id),
  issued_at     TEXT NOT NULL,
  general_instructions TEXT,
  status        TEXT NOT NULL DEFAULT 'emitida' CHECK (status IN ('emitida','anulada')),
  voided_at     TEXT,
  voided_by     TEXT REFERENCES users(id),
  void_reason   TEXT
) STRICT;
CREATE INDEX prescriptions_patient ON prescriptions(patient_id, issued_at);
-- Solo se permite pasar de 'emitida' a 'anulada' (con motivo); nada más cambia.
CREATE TRIGGER prescriptions_only_void BEFORE UPDATE ON prescriptions
WHEN NOT (OLD.status = 'emitida' AND NEW.status = 'anulada'
          AND NEW.void_reason IS NOT NULL AND NEW.voided_by IS NOT NULL
          AND NEW.patient_id = OLD.patient_id AND NEW.issued_at = OLD.issued_at
          AND NEW.author_id = OLD.author_id
          AND COALESCE(NEW.general_instructions,'') = COALESCE(OLD.general_instructions,''))
BEGIN SELECT RAISE(ABORT, 'receta_inmutable'); END;
CREATE TRIGGER prescriptions_no_delete BEFORE DELETE ON prescriptions
BEGIN SELECT RAISE(ABORT, 'recetas_no_se_eliminan'); END;

CREATE TABLE prescription_items (
  id                TEXT PRIMARY KEY,
  prescription_id   TEXT NOT NULL REFERENCES prescriptions(id),
  position          INTEGER NOT NULL,
  active_ingredient TEXT NOT NULL,
  presentation      TEXT,
  dose              TEXT NOT NULL,
  dose_unit         TEXT NOT NULL,
  route             TEXT NOT NULL,
  frequency         TEXT NOT NULL,
  duration          TEXT NOT NULL,
  quantity          TEXT NOT NULL,
  instructions      TEXT
) STRICT;
CREATE TRIGGER prescription_items_immutable_u BEFORE UPDATE ON prescription_items
BEGIN SELECT RAISE(ABORT, 'receta_inmutable'); END;
CREATE TRIGGER prescription_items_immutable_d BEFORE DELETE ON prescription_items
BEGIN SELECT RAISE(ABORT, 'receta_inmutable'); END;

-- Bitácora de auditoría: solo inserción, encadenada por hash para detectar alteraciones.
CREATE TABLE audit_log (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  org_id     TEXT,
  user_id    TEXT,
  action     TEXT NOT NULL,
  entity     TEXT,
  entity_id  TEXT,
  ip         TEXT,
  detail     TEXT,
  prev_hash  TEXT NOT NULL,
  hash       TEXT NOT NULL
) STRICT;
CREATE INDEX audit_log_entity ON audit_log(entity, entity_id);
CREATE TRIGGER audit_log_immutable_u BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'auditoria_inmutable'); END;
CREATE TRIGGER audit_log_immutable_d BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'auditoria_inmutable'); END;

CREATE TABLE counters (
  org_id  TEXT NOT NULL,
  name    TEXT NOT NULL,
  value   INTEGER NOT NULL,
  PRIMARY KEY (org_id, name)
) STRICT;
