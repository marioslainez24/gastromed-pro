-- v0.15.0: la nota tiene un solo «Plan» y ya no tiene «Diagnósticos diferenciales» (pedido del médico).
-- Las frases guardadas para los campos anteriores pasan a los nuevos.
UPDATE phrases SET field = 'plan' WHERE field IN ('plan_diagnostico','plan_terapeutico','educacion','signos_alarma','seguimiento');
UPDATE phrases SET field = 'diagnosticos' WHERE field = 'diferenciales';

-- Solicitudes de imagen, endoscopia y colonoscopia: nombre que se imprime en el título (p. ej. «Colonoscopia»).
ALTER TABLE orders ADD COLUMN study_label TEXT;
