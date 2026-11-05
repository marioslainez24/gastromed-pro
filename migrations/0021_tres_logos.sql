-- GastroMed Pro · Migración 0021 · v0.27.0: hasta 3 logos (pedido del Dr. Lainez). SQLite no permite cambiar un CHECK:
-- se crea la tabla nueva, se copian las imágenes ya cargadas (logo y firma) y se reemplaza.
CREATE TABLE clinic_assets_new (
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  kind        TEXT NOT NULL CHECK (kind IN ('logo', 'logo2', 'logo3', 'firma')),
  mime        TEXT NOT NULL,
  data_enc    BLOB NOT NULL,
  updated_at  TEXT NOT NULL,
  updated_by  TEXT NOT NULL REFERENCES users(id),
  PRIMARY KEY (org_id, kind)
) STRICT;
INSERT INTO clinic_assets_new(org_id, kind, mime, data_enc, updated_at, updated_by)
  SELECT org_id, kind, mime, data_enc, updated_at, updated_by FROM clinic_assets;
DROP TABLE clinic_assets;
ALTER TABLE clinic_assets_new RENAME TO clinic_assets;
