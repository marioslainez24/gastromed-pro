-- GastroMed Pro · Migración 0014 · v0.18.0: descartar notas de consulta en borrador
-- Igual que los informes de endoscopia (0013): no se borran, se marcan como descartadas, dejan de mostrarse y ya no se pueden
-- modificar. Una nota finalizada no se puede descartar. Recetas, órdenes y documentos ya emitidos desde esa nota no se tocan.
ALTER TABLE clinical_notes ADD COLUMN discarded_at TEXT;
ALTER TABLE clinical_notes ADD COLUMN discarded_by TEXT REFERENCES users(id);

CREATE TRIGGER clinical_notes_discarded_immutable BEFORE UPDATE ON clinical_notes
WHEN OLD.discarded_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'nota_descartada_inmutable'); END;

CREATE TRIGGER clinical_notes_discard_only_draft BEFORE UPDATE OF discarded_at ON clinical_notes
WHEN NEW.discarded_at IS NOT NULL AND OLD.status <> 'borrador'
BEGIN SELECT RAISE(ABORT, 'solo_borradores_se_descartan'); END;
