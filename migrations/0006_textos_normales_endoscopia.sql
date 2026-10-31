-- v0.8.0: textos de «estudio normal» personalizables para los informes de endoscopia (JSON {"sec": {...}, "concl": {...}}).
ALTER TABLE clinic_settings ADD COLUMN endo_normal_texts TEXT;
