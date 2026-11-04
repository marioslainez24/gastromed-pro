-- GastroMed Pro · Migración 0019 · v0.23.0: descartar (anular) informes de endoscopia FINALIZADOS
-- Pedido del Dr. Lainez (3-nov-2026): poder quitar de la lista un informe finalizado (p. ej., duplicado o hecho por error).
-- El informe NO se borra ni cambia su contenido: se registra la anulación con motivo, quién y cuándo (tabla inmutable) y se marca
-- discarded_at para que deje de aparecer en listas, búsquedas y estadísticas. Queda en la base y en la auditoría.
CREATE TABLE procedure_voids (
  id           TEXT PRIMARY KEY,
  org_id       TEXT NOT NULL REFERENCES organizations(id),
  procedure_id TEXT NOT NULL UNIQUE REFERENCES procedures(id),
  reason       TEXT NOT NULL CHECK (length(trim(reason)) >= 3),
  voided_by    TEXT NOT NULL REFERENCES users(id),
  voided_at    TEXT NOT NULL
) STRICT;
CREATE TRIGGER procedure_voids_no_update BEFORE UPDATE ON procedure_voids BEGIN SELECT RAISE(ABORT, 'anulacion_inmutable'); END;
CREATE TRIGGER procedure_voids_no_delete BEFORE DELETE ON procedure_voids BEGIN SELECT RAISE(ABORT, 'anulacion_inmutable'); END;
CREATE TRIGGER procedure_voids_only_finalized BEFORE INSERT ON procedure_voids
WHEN (SELECT status FROM procedures WHERE id = NEW.procedure_id) IS NOT 'finalizado'
BEGIN SELECT RAISE(ABORT, 'solo_finalizados_se_anulan'); END;

-- Un informe finalizado sigue siendo inmutable; la ÚNICA excepción es marcarlo como descartado si ya tiene su anulación registrada,
-- sin cambiar ningún otro dato.
DROP TRIGGER procedures_finalized_immutable;
CREATE TRIGGER procedures_finalized_immutable BEFORE UPDATE ON procedures
WHEN OLD.status = 'finalizado' AND NOT (
  OLD.discarded_at IS NULL AND NEW.discarded_at IS NOT NULL AND NEW.discarded_by IS NOT NULL
  AND EXISTS (SELECT 1 FROM procedure_voids v WHERE v.procedure_id = OLD.id)
  AND NEW.org_id IS OLD.org_id AND NEW.patient_id IS OLD.patient_id AND NEW.appointment_id IS OLD.appointment_id AND NEW.kind IS OLD.kind AND NEW.status IS OLD.status AND NEW.performed_on IS OLD.performed_on AND NEW.indication_category IS OLD.indication_category AND NEW.patient_age_years IS OLD.patient_age_years AND NEW.scope_id IS OLD.scope_id AND NEW.extent IS OLD.extent AND NEW.cecum_reached IS OLD.cecum_reached AND NEW.complete IS OLD.complete AND NEW.withdrawal_minutes IS OLD.withdrawal_minutes AND NEW.bbps_right IS OLD.bbps_right AND NEW.bbps_transverse IS OLD.bbps_transverse AND NEW.bbps_left IS OLD.bbps_left AND NEW.had_complication IS OLD.had_complication AND NEW.surveillance_due IS OLD.surveillance_due AND NEW.data IS OLD.data AND NEW.author_id IS OLD.author_id AND NEW.created_at IS OLD.created_at AND NEW.updated_at IS OLD.updated_at AND NEW.finalized_at IS OLD.finalized_at AND NEW.finalized_by IS OLD.finalized_by AND NEW.content_sha256 IS OLD.content_sha256 AND NEW.version IS OLD.version)
BEGIN SELECT RAISE(ABORT, 'procedimiento_finalizado_inmutable'); END;

DROP TRIGGER procedures_discard_only_draft;
CREATE TRIGGER procedures_discard_only_draft BEFORE UPDATE OF discarded_at ON procedures
WHEN NEW.discarded_at IS NOT NULL AND OLD.status <> 'borrador'
  AND NOT EXISTS (SELECT 1 FROM procedure_voids v WHERE v.procedure_id = OLD.id)
BEGIN SELECT RAISE(ABORT, 'solo_borradores_se_descartan'); END;
