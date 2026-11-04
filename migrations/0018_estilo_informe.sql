-- GastroMed Pro · Migración 0018 · v0.22.0: estilo del informe de endoscopia (pedido del Dr. Lainez)
-- clasico = el de siempre; formal = blanco y negro con letra tipo libro; moderno = franja de color arriba.
ALTER TABLE clinic_settings ADD COLUMN report_style TEXT NOT NULL DEFAULT 'clasico' CHECK (report_style IN ('clasico', 'formal', 'moderno'));
