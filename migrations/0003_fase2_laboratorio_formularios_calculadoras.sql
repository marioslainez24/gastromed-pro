-- GastroMed Pro · Migración 0003 · Fase 2: órdenes, resultados, tareas, formularios GI, diario, calculadoras

-- Catálogo de pruebas de laboratorio (los rangos de referencia NO se precargan: se toman del informe de cada laboratorio)
CREATE TABLE lab_tests (
  code        TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  unit        TEXT,                 -- unidad canónica esperada (las calculadoras solo importan valores en esta unidad)
  kind        TEXT NOT NULL DEFAULT 'numerico' CHECK (kind IN ('numerico','cualitativo')),
  grp         TEXT NOT NULL,
  position    INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE orders (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  patient_id      TEXT NOT NULL REFERENCES patients(id),
  note_id         TEXT REFERENCES clinical_notes(id),
  order_type      TEXT NOT NULL CHECK (order_type IN ('laboratorio','imagen','endoscopia')),
  indication      TEXT,
  priority        TEXT NOT NULL DEFAULT 'rutina' CHECK (priority IN ('rutina','preferente','urgente')),
  status          TEXT NOT NULL DEFAULT 'solicitada'
                    CHECK (status IN ('solicitada','resultado_parcial','resultado_recibido','cerrada','anulada')),
  responsible_id  TEXT NOT NULL REFERENCES users(id),   -- quién revisa y comunica el resultado
  expected_by     TEXT,                                 -- fecha en que se espera el resultado (AAAA-MM-DD)
  author_id       TEXT NOT NULL REFERENCES users(id),
  created_at      TEXT NOT NULL,
  closed_at       TEXT,
  void_reason     TEXT,
  version         INTEGER NOT NULL DEFAULT 1
) STRICT;
CREATE INDEX orders_patient ON orders(patient_id, created_at);
CREATE INDEX orders_status ON orders(org_id, status);
CREATE TRIGGER orders_no_delete BEFORE DELETE ON orders BEGIN SELECT RAISE(ABORT, 'ordenes_no_se_eliminan'); END;

CREATE TABLE order_items (
  id          TEXT PRIMARY KEY,
  order_id    TEXT NOT NULL REFERENCES orders(id),
  position    INTEGER NOT NULL,
  test_code   TEXT REFERENCES lab_tests(code),   -- laboratorio
  description TEXT NOT NULL                       -- texto mostrado / estudio de imagen o endoscopia
) STRICT;
CREATE TRIGGER order_items_immutable_u BEFORE UPDATE ON order_items BEGIN SELECT RAISE(ABORT, 'orden_inmutable'); END;
CREATE TRIGGER order_items_immutable_d BEFORE DELETE ON order_items BEGIN SELECT RAISE(ABORT, 'orden_inmutable'); END;

-- Resultados estructurados
CREATE TABLE lab_results (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  patient_id      TEXT NOT NULL REFERENCES patients(id),
  order_id        TEXT REFERENCES orders(id),
  file_id         TEXT REFERENCES files(id),
  test_code       TEXT NOT NULL REFERENCES lab_tests(code),
  value_num       REAL,
  value_text      TEXT,
  unit            TEXT,
  ref_low         REAL,
  ref_high        REAL,
  ref_text        TEXT,
  flag            TEXT CHECK (flag IN ('bajo','normal','alto','sin_rango')),
  taken_on        TEXT NOT NULL,          -- fecha de toma de muestra (AAAA-MM-DD)
  laboratory      TEXT,
  source          TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','ocr_validado')),
  status          TEXT NOT NULL DEFAULT 'pendiente_revision' CHECK (status IN ('pendiente_revision','revisado','anulado')),
  entered_by      TEXT NOT NULL REFERENCES users(id),
  entered_at      TEXT NOT NULL,
  reviewed_by     TEXT REFERENCES users(id),
  reviewed_at     TEXT,
  review_comment  TEXT,
  communicated_at TEXT,
  communicated_by TEXT REFERENCES users(id),
  communication   TEXT,
  void_reason     TEXT,
  CHECK (value_num IS NOT NULL OR value_text IS NOT NULL)
) STRICT;
CREATE INDEX lab_results_patient_test ON lab_results(patient_id, test_code, taken_on);
CREATE INDEX lab_results_pending ON lab_results(org_id, status);
CREATE TRIGGER lab_results_no_delete BEFORE DELETE ON lab_results BEGIN SELECT RAISE(ABORT, 'resultados_no_se_eliminan'); END;
-- El valor, unidad, fecha y prueba no se modifican: un error se corrige anulando y registrando de nuevo.
CREATE TRIGGER lab_results_value_immutable BEFORE UPDATE ON lab_results
WHEN NEW.value_num IS NOT OLD.value_num OR NEW.value_text IS NOT OLD.value_text OR NEW.unit IS NOT OLD.unit
  OR NEW.test_code <> OLD.test_code OR NEW.taken_on <> OLD.taken_on OR NEW.patient_id <> OLD.patient_id
BEGIN SELECT RAISE(ABORT, 'resultado_inmutable'); END;

-- Tareas y seguimiento
CREATE TABLE tasks (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES organizations(id),
  patient_id    TEXT REFERENCES patients(id),
  title         TEXT NOT NULL,
  detail        TEXT,
  due_on        TEXT,
  assigned_to   TEXT NOT NULL REFERENCES users(id),
  status        TEXT NOT NULL DEFAULT 'abierta' CHECK (status IN ('abierta','hecha','cancelada')),
  created_by    TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL,
  done_by       TEXT REFERENCES users(id),
  done_at       TEXT,
  done_note     TEXT
) STRICT;
CREATE INDEX tasks_open ON tasks(org_id, status, due_on);
CREATE TRIGGER tasks_no_delete BEFORE DELETE ON tasks BEGIN SELECT RAISE(ABORT, 'tareas_no_se_eliminan'); END;

-- Formularios gastroenterológicos vinculados a la nota
CREATE TABLE clinical_forms (
  id          TEXT PRIMARY KEY,
  org_id      TEXT NOT NULL REFERENCES organizations(id),
  patient_id  TEXT NOT NULL REFERENCES patients(id),
  note_id     TEXT NOT NULL REFERENCES clinical_notes(id),
  form_code   TEXT NOT NULL,
  form_version INTEGER NOT NULL,
  data        TEXT NOT NULL,      -- JSON
  author_id   TEXT NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  version     INTEGER NOT NULL DEFAULT 1
) STRICT;
CREATE INDEX clinical_forms_note ON clinical_forms(note_id);
CREATE TRIGGER clinical_forms_no_delete BEFORE DELETE ON clinical_forms BEGIN SELECT RAISE(ABORT, 'formularios_no_se_eliminan'); END;
-- Si la nota está finalizada, el formulario queda bloqueado igual que la nota.
CREATE TRIGGER clinical_forms_locked BEFORE UPDATE ON clinical_forms
WHEN (SELECT status FROM clinical_notes WHERE id = OLD.note_id) = 'finalizada'
BEGIN SELECT RAISE(ABORT, 'formulario_de_nota_finalizada'); END;

-- Diario de síntomas y deposiciones (registrado por el personal a partir de lo que reporta el paciente)
CREATE TABLE symptom_diary (
  id            TEXT PRIMARY KEY,
  org_id        TEXT NOT NULL REFERENCES organizations(id),
  patient_id    TEXT NOT NULL REFERENCES patients(id),
  entry_date    TEXT NOT NULL,
  stools        INTEGER,
  bristol       INTEGER CHECK (bristol BETWEEN 1 AND 7),
  blood         INTEGER NOT NULL DEFAULT 0,
  urgency       INTEGER NOT NULL DEFAULT 0,
  nocturnal     INTEGER NOT NULL DEFAULT 0,
  pain          INTEGER CHECK (pain BETWEEN 0 AND 10),
  notes         TEXT,
  recorded_by   TEXT NOT NULL REFERENCES users(id),
  recorded_at   TEXT NOT NULL
) STRICT;
CREATE INDEX symptom_diary_patient ON symptom_diary(patient_id, entry_date);
CREATE TRIGGER symptom_diary_no_delete BEFORE DELETE ON symptom_diary BEGIN SELECT RAISE(ABORT, 'registros_clinicos_no_se_eliminan'); END;

-- Calculadoras: aprobación clínica por versión y resultados guardados con sus entradas
CREATE TABLE calculator_approvals (
  org_id       TEXT NOT NULL REFERENCES organizations(id),
  calc_code    TEXT NOT NULL,
  calc_version TEXT NOT NULL,
  approved_by  TEXT NOT NULL REFERENCES users(id),
  approved_at  TEXT NOT NULL,
  comment      TEXT,
  PRIMARY KEY (org_id, calc_code, calc_version)
) STRICT;

CREATE TABLE calc_results (
  id           TEXT PRIMARY KEY,
  org_id       TEXT NOT NULL REFERENCES organizations(id),
  patient_id   TEXT NOT NULL REFERENCES patients(id),
  note_id      TEXT REFERENCES clinical_notes(id),
  calc_code    TEXT NOT NULL,
  calc_version TEXT NOT NULL,
  inputs       TEXT NOT NULL,     -- JSON: valor, unidad, origen (manual / expediente con fecha)
  result       TEXT NOT NULL,     -- JSON
  author_id    TEXT NOT NULL REFERENCES users(id),
  created_at   TEXT NOT NULL
) STRICT;
CREATE INDEX calc_results_patient ON calc_results(patient_id, created_at);
CREATE TRIGGER calc_results_immutable_u BEFORE UPDATE ON calc_results BEGIN SELECT RAISE(ABORT, 'calculo_inmutable'); END;
CREATE TRIGGER calc_results_immutable_d BEFORE DELETE ON calc_results BEGIN SELECT RAISE(ABORT, 'calculo_inmutable'); END;

-- Permisos nuevos para los roles existentes
INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'resultados.registrar' FROM roles WHERE code IN ('propietario','medico','enfermeria');
INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'resultados.revisar' FROM roles WHERE code IN ('propietario','medico');
INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'ordenes.emitir' FROM roles WHERE code IN ('propietario','medico');
INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'tareas.gestionar' FROM roles WHERE code IN ('propietario','medico','enfermeria','recepcion');
INSERT INTO role_permissions(role_id, permission)
  SELECT id, 'calculadoras.aprobar' FROM roles WHERE code = 'propietario';

-- Catálogo inicial (sin rangos de referencia)
INSERT INTO lab_tests(code, name, unit, kind, grp, position) VALUES
 ('hb','Hemoglobina','g/dL','numerico','Hematología',1), ('hto','Hematocrito','%','numerico','Hematología',2),
 ('vcm','Volumen corpuscular medio','fL','numerico','Hematología',3), ('leu','Leucocitos','10^3/µL','numerico','Hematología',4),
 ('plt','Plaquetas','10^3/µL','numerico','Hematología',5), ('ferritina','Ferritina','ng/mL','numerico','Hierro y vitaminas',10),
 ('hierro','Hierro sérico','µg/dL','numerico','Hierro y vitaminas',11), ('sat_tf','Saturación de transferrina','%','numerico','Hierro y vitaminas',12),
 ('b12','Vitamina B12','pg/mL','numerico','Hierro y vitaminas',13), ('folato','Ácido fólico','ng/mL','numerico','Hierro y vitaminas',14),
 ('bt','Bilirrubina total','mg/dL','numerico','Hepático',20), ('bd','Bilirrubina directa','mg/dL','numerico','Hepático',21),
 ('ast','AST (TGO)','U/L','numerico','Hepático',22), ('alt','ALT (TGP)','U/L','numerico','Hepático',23),
 ('fa','Fosfatasa alcalina','U/L','numerico','Hepático',24), ('ggt','GGT','U/L','numerico','Hepático',25),
 ('alb','Albúmina','g/dL','numerico','Hepático',26), ('prot','Proteínas totales','g/dL','numerico','Hepático',27),
 ('tp','Tiempo de protrombina','s','numerico','Coagulación',30), ('tp_control','TP control','s','numerico','Coagulación',31),
 ('inr','INR',NULL,'numerico','Coagulación',32),
 ('creat','Creatinina','mg/dL','numerico','Renal y electrolitos',40), ('bun','Nitrógeno ureico (BUN)','mg/dL','numerico','Renal y electrolitos',41),
 ('na','Sodio','mmol/L','numerico','Renal y electrolitos',42), ('k','Potasio','mmol/L','numerico','Renal y electrolitos',43),
 ('glu','Glucosa','mg/dL','numerico','Metabólico',50), ('hba1c','Hemoglobina glicada (HbA1c)','%','numerico','Metabólico',51),
 ('col','Colesterol total','mg/dL','numerico','Metabólico',52), ('tg','Triglicéridos','mg/dL','numerico','Metabólico',53),
 ('amilasa','Amilasa','U/L','numerico','Páncreas',60), ('lipasa','Lipasa','U/L','numerico','Páncreas',61),
 ('pcr','Proteína C reactiva','mg/L','numerico','Inflamación',70), ('vsg','Velocidad de sedimentación','mm/h','numerico','Inflamación',71),
 ('calpro','Calprotectina fecal','µg/g','numerico','Inflamación',72),
 ('afp','Alfafetoproteína','ng/mL','numerico','Marcadores tumorales',80), ('cea','Antígeno carcinoembrionario','ng/mL','numerico','Marcadores tumorales',81),
 ('ca199','CA 19-9','U/mL','numerico','Marcadores tumorales',82),
 ('hbsag','HBsAg','','cualitativo','Serologías',90), ('anti_hbc','Anti-HBc total','','cualitativo','Serologías',91),
 ('anti_hcv','Anti-VHC','','cualitativo','Serologías',92), ('vih','VIH','','cualitativo','Serologías',93),
 ('hp_ag_heces','H. pylori antígeno en heces','','cualitativo','H. pylori',95), ('hp_urea','H. pylori prueba de aliento con urea','','cualitativo','H. pylori',96),
 ('sangre_oculta','Sangre oculta en heces (FIT)','','cualitativo','Heces',97), ('tsh','TSH','µUI/mL','numerico','Otros',99);
