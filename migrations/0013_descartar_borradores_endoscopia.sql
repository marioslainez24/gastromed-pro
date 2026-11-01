-- GastroMed Pro · Migración 0013 · v0.18.0: descartar informes de endoscopia en borrador
-- Pedido del Dr. Lainez: quitar de la lista los borradores que no se van a usar. No se borran (la base no permite eliminar
-- procedimientos): se marcan como descartados, dejan de mostrarse y ya no se pueden modificar. Un informe finalizado no se puede descartar.
ALTER TABLE procedures ADD COLUMN discarded_at TEXT;
ALTER TABLE procedures ADD COLUMN discarded_by TEXT REFERENCES users(id);

CREATE TRIGGER procedures_discarded_immutable BEFORE UPDATE ON procedures
WHEN OLD.discarded_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'procedimiento_descartado_inmutable'); END;

CREATE TRIGGER procedures_discard_only_draft BEFORE UPDATE OF discarded_at ON procedures
WHEN NEW.discarded_at IS NOT NULL AND OLD.status <> 'borrador'
BEGIN SELECT RAISE(ABORT, 'solo_borradores_se_descartan'); END;
