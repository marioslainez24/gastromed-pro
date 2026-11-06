-- GastroMed Pro · Migración 0022 · v0.28.0: dónde va cada logo (izquierda / centro / derecha) y su tamaño (pedido del Dr. Lainez).
-- JSON: {"logo": "izquierda", "logo2": "derecha", "logo3": "centro", "size": "grande"}. NULL = colocación automática anterior.
ALTER TABLE clinic_settings ADD COLUMN logo_layout TEXT;
