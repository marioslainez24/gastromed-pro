-- v0.13.0: textos normales de la exploración física editables por el médico (JSON {sistema: texto}).
ALTER TABLE clinic_settings ADD COLUMN exam_normal_texts TEXT;
