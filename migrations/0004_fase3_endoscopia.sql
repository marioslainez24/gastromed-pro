-- GastroMed Pro · Migración 0004 · Fase 3: endoscopia, imágenes, patología, vigilancia, calidad y trazabilidad

CREATE TABLE scopes (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  name        TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('gastroscopio','colonoscopio','duodenoscopio','ecoendoscopio','otro')),
  serial      TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL
) STRICT;

CREATE TABLE procedures (
  id                   TEXT PRIMARY KEY,
  org_id               TEXT NOT NULL REFERENCES organizations(id),
  patient_id           TEXT NOT NULL REFERENCES patients(id),
  appointment_id       TEXT REFERENCES appointments(id),
  kind                 TEXT NOT NULL CHECK (kind IN ('eda','colonoscopia','rectosigmoidoscopia','cpre','use')),
  status               TEXT NOT NULL DEFAULT 'borrador' CHECK (status IN ('borrador','finalizado')),
  performed_on         TEXT NOT NULL,                       -- AAAA-MM-DD
  indication_category  TEXT CHECK (indication_category IN ('diagnostica','tamizaje','vigilancia','terapeutica')),
  patient_age_years    INTEGER,                             -- edad al procedimiento (para indicadores)
  scope_id             TEXT REFERENCES scopes(id),
  extent               TEXT,
  cecum_reached        INTEGER,                             -- colonoscopia: llegó a ciego/íleon
  complete             INTEGER,
  withdrawal_minutes   REAL,
  bbps_right           INTEGER CHECK (bbps_right BETWEEN 0 AND 3),
  bbps_transverse      INTEGER CHECK (bbps_transverse BETWEEN 0 AND 3),
  bbps_left            INTEGER CHECK (bbps_left BETWEEN 0 AND 3),
  had_complication     INTEGER NOT NULL DEFAULT 0,
  surveillance_due     TEXT,                                -- fecha de control / vigilancia indicada por el médico
  data                 TEXT NOT NULL,                       -- JSON con el resto del informe
  author_id            TEXT NOT NULL REFERENCES users(id),
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL,
  finalized_at         TEXT,
  finalized_by         TEXT REFERENCES users(id),
  content_sha256       TEXT,
  version              INTEGER NOT NULL DEFAULT 1
) STRICT;
CREATE INDEX procedures_patient ON procedures(patient_id, performed_on);
CREATE INDEX procedures_org ON procedures(org_id, kind, performed_on);
CREATE TRIGGER procedures_finalized_immutable BEFORE UPDATE ON procedures
WHEN OLD.status = 'finalizado'
BEGIN SELECT RAISE(ABORT, 'procedimiento_finalizado_inmutable'); END;
CREATE TRIGGER procedures_no_delete BEFORE DELETE ON procedures BEGIN SELECT RAISE(ABORT, 'procedimientos_no_se_eliminan'); END;

CREATE TABLE procedure_addenda (
  id            TEXT PRIMARY KEY,
  procedure_id  TEXT NOT NULL REFERENCES procedures(id),
  author_id     TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL,
  text          TEXT NOT NULL
) STRICT;
CREATE TRIGGER procedure_addenda_immutable_u BEFORE UPDATE ON procedure_addenda BEGIN SELECT RAISE(ABORT, 'adenda_inmutable'); END;
CREATE TRIGGER procedure_addenda_immutable_d BEFORE DELETE ON procedure_addenda BEGIN SELECT RAISE(ABORT, 'adenda_inmutable'); END;

-- Imágenes del procedimiento (el archivo original queda intacto en «files»; las anotaciones se guardan aparte)
CREATE TABLE procedure_images (
  id            TEXT PRIMARY KEY,
  procedure_id  TEXT NOT NULL REFERENCES procedures(id),
  file_id       TEXT NOT NULL REFERENCES files(id),
  source        TEXT NOT NULL CHECK (source IN ('importada','captura')),
  location      TEXT,
  caption       TEXT,
  in_report     INTEGER NOT NULL DEFAULT 0,
  position      INTEGER NOT NULL DEFAULT 0,
  annotations   TEXT NOT NULL DEFAULT '[]',   -- JSON: [{x, y, text}] coordenadas relativas 0–1
  created_by    TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL
) STRICT;
CREATE INDEX procedure_images_proc ON procedure_images(procedure_id, position);
CREATE TRIGGER procedure_images_locked BEFORE UPDATE ON procedure_images
WHEN (SELECT status FROM procedures WHERE id = OLD.procedure_id) = 'finalizado'
BEGIN SELECT RAISE(ABORT, 'imagenes_de_procedimiento_finalizado'); END;
CREATE TRIGGER procedure_images_no_delete BEFORE DELETE ON procedure_images BEGIN SELECT RAISE(ABORT, 'imagenes_no_se_eliminan'); END;

-- Muestras / frascos de patología: seguimiento hasta el cierre
CREATE TABLE specimens (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  procedure_id    TEXT NOT NULL REFERENCES procedures(id),
  patient_id      TEXT NOT NULL REFERENCES patients(id),
  jar             INTEGER NOT NULL,
  site            TEXT NOT NULL,
  description     TEXT,
  pieces          INTEGER,
  status          TEXT NOT NULL DEFAULT 'pendiente_envio'
                    CHECK (status IN ('pendiente_envio','enviado','resultado_recibido','cerrado','extraviado')),
  laboratory      TEXT,
  sent_on         TEXT,
  result_on       TEXT,
  result_text     TEXT,
  result_category TEXT CHECK (result_category IN ('normal','inflamatorio','hiperplasico','adenoma_tubular','adenoma_tubulovelloso',
                                                  'adenoma_velloso','serrado_sesil','adenocarcinoma','otro_neoplasico','otro')),
  dysplasia       TEXT CHECK (dysplasia IN ('no_aplica','sin_displasia','bajo_grado','alto_grado','indefinida')),
  result_file_id  TEXT REFERENCES files(id),
  result_by       TEXT REFERENCES users(id),
  communicated_at TEXT,
  communication   TEXT,
  closed_by       TEXT REFERENCES users(id),
  closed_at       TEXT,
  created_at      TEXT NOT NULL,
  UNIQUE (procedure_id, jar)
) STRICT;
CREATE INDEX specimens_status ON specimens(org_id, status);
CREATE TRIGGER specimens_no_delete BEFORE DELETE ON specimens BEGIN SELECT RAISE(ABORT, 'muestras_no_se_eliminan'); END;
-- Un resultado de patología registrado no se reescribe (correcciones como adenda del procedimiento)
CREATE TRIGGER specimens_result_immutable BEFORE UPDATE ON specimens
WHEN OLD.result_text IS NOT NULL AND (NEW.result_text IS NOT OLD.result_text OR NEW.result_category IS NOT OLD.result_category
     OR NEW.dysplasia IS NOT OLD.dysplasia)
BEGIN SELECT RAISE(ABORT, 'resultado_patologia_inmutable'); END;

-- Reprocesamiento de endoscopios (trazabilidad)
CREATE TABLE scope_reprocessing (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES organizations(id),
  scope_id      TEXT NOT NULL REFERENCES scopes(id),
  procedure_id  TEXT REFERENCES procedures(id),
  done_at       TEXT NOT NULL,
  method        TEXT NOT NULL CHECK (method IN ('manual','automatizado')),
  agent         TEXT,
  agent_lot     TEXT,
  leak_test     TEXT NOT NULL CHECK (leak_test IN ('aprobada','fallida','no_realizada')),
  result        TEXT NOT NULL CHECK (result IN ('apto','no_apto')),
  notes         TEXT,
  done_by       TEXT NOT NULL REFERENCES users(id)
) STRICT;
CREATE INDEX scope_reprocessing_scope ON scope_reprocessing(scope_id, done_at);
CREATE TRIGGER scope_reprocessing_immutable_u BEFORE UPDATE ON scope_reprocessing BEGIN SELECT RAISE(ABORT, 'registro_inmutable'); END;
CREATE TRIGGER scope_reprocessing_immutable_d BEFORE DELETE ON scope_reprocessing BEGIN SELECT RAISE(ABORT, 'registro_inmutable'); END;

-- Prótesis (biliares, pancreáticas, esofágicas, colónicas) con fecha prevista de revisión o retiro
CREATE TABLE stents (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES organizations(id),
  patient_id    TEXT NOT NULL REFERENCES patients(id),
  procedure_id  TEXT REFERENCES procedures(id),
  kind          TEXT NOT NULL,
  description   TEXT,
  placed_on     TEXT NOT NULL,
  review_due    TEXT,
  status        TEXT NOT NULL DEFAULT 'colocada' CHECK (status IN ('colocada','retirada','recambiada','migrada')),
  removed_on    TEXT,
  notes         TEXT,
  created_by    TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL
) STRICT;
CREATE INDEX stents_due ON stents(org_id, status, review_due);
CREATE TRIGGER stents_no_delete BEFORE DELETE ON stents BEGIN SELECT RAISE(ABORT, 'registros_clinicos_no_se_eliminan'); END;

INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'endoscopia.reprocesamiento' FROM roles WHERE code IN ('propietario','medico','enfermeria');
