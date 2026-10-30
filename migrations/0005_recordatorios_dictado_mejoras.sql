-- GastroMed Pro · Migración 0005 · Recordatorios, dictado, logo/firma, horarios y bloqueos

-- Preferencia y consentimiento del paciente para recordatorios (mensajes sin información clínica)
ALTER TABLE patients ADD COLUMN reminder_channel TEXT NOT NULL DEFAULT 'ninguno';
ALTER TABLE patients ADD COLUMN reminder_consent_at TEXT;
ALTER TABLE patients ADD COLUMN reminder_consent_by TEXT REFERENCES users(id);

ALTER TABLE clinic_settings ADD COLUMN reminders_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE clinic_settings ADD COLUMN reminder_hours_before INTEGER NOT NULL DEFAULT 24;
ALTER TABLE clinic_settings ADD COLUMN smtp_host TEXT NOT NULL DEFAULT 'smtp.gmail.com';
ALTER TABLE clinic_settings ADD COLUMN smtp_port INTEGER NOT NULL DEFAULT 587;
ALTER TABLE clinic_settings ADD COLUMN smtp_user TEXT;
ALTER TABLE clinic_settings ADD COLUMN smtp_password_enc TEXT;
ALTER TABLE clinic_settings ADD COLUMN reminder_template TEXT NOT NULL DEFAULT
  'Hola {nombre}: le recordamos su cita en {consultorio} el {fecha} a las {hora}. Si necesita cambiarla, comuníquese al {telefono}. Por favor no responda con información de salud.';
ALTER TABLE clinic_settings ADD COLUMN dictation_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE clinic_settings ADD COLUMN dictation_lang TEXT NOT NULL DEFAULT 'es-MX';

CREATE TABLE appointment_reminders (
  id              TEXT PRIMARY KEY,
  appointment_id  TEXT NOT NULL REFERENCES appointments(id),
  channel         TEXT NOT NULL CHECK (channel IN ('correo','whatsapp')),
  status          TEXT NOT NULL CHECK (status IN ('enviado','fallido','abierto_en_whatsapp')),
  attempts        INTEGER NOT NULL DEFAULT 1,
  detail          TEXT,                 -- error técnico (sin datos clínicos)
  last_at         TEXT NOT NULL,
  by_user         TEXT REFERENCES users(id),
  UNIQUE (appointment_id, channel)      -- evita recordatorios duplicados
) STRICT;

-- Logo e imagen de firma (cifrados). La imagen de firma NO es una firma electrónica verificable.
CREATE TABLE clinic_assets (
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  kind        TEXT NOT NULL CHECK (kind IN ('logo','firma')),
  mime        TEXT NOT NULL,
  data_enc    BLOB NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  TEXT NOT NULL REFERENCES users(id),
  PRIMARY KEY (org_id, kind)
) STRICT;

-- Horarios de atención por profesional
CREATE TABLE practitioner_schedules (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  user_id     TEXT NOT NULL REFERENCES users(id),
  weekday     INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),   -- 0 = lunes
  start_time  TEXT NOT NULL,
  end_time    TEXT NOT NULL,
  CHECK (end_time > start_time)
) STRICT;
CREATE INDEX practitioner_schedules_user ON practitioner_schedules(user_id, weekday);

-- Vacaciones, ausencias y bloqueos (user_id NULL = toda la clínica)
CREATE TABLE schedule_blocks (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  user_id     TEXT REFERENCES users(id),
  start_date  TEXT NOT NULL,
  end_date    TEXT NOT NULL,
  reason      TEXT,
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  CHECK (end_date >= start_date)
) STRICT;
CREATE INDEX schedule_blocks_dates ON schedule_blocks(org_id, start_date, end_date);
