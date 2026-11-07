-- GastroMed Pro · Migración 0023 · v0.29.0: cuántas copias de respaldo se guardan en la PC (pedido del Dr. Lainez).
-- NULL = el valor del archivo de configuración (30).
ALTER TABLE clinic_settings ADD COLUMN backup_keep INTEGER CHECK (backup_keep IS NULL OR backup_keep IN (7, 15, 30, 60));
