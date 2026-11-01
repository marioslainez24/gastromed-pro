-- v0.14.0: copia de los respaldos cifrados en una carpeta sincronizada (Google Drive para computadora). Apagada por defecto.
ALTER TABLE clinic_settings ADD COLUMN offsite_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE clinic_settings ADD COLUMN offsite_dir TEXT;
ALTER TABLE clinic_settings ADD COLUMN offsite_keep INTEGER NOT NULL DEFAULT 7;
ALTER TABLE clinic_settings ADD COLUMN offsite_last_at TEXT;
ALTER TABLE clinic_settings ADD COLUMN offsite_last_msg TEXT;
