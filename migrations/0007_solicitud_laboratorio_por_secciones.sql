-- v0.9.0: solicitud de laboratorio con casillas por sección y perfiles (como la hoja de papel).
-- Sección del estudio solicitado, para agrupar en pantalla y en el PDF. NULL en órdenes anteriores.
ALTER TABLE order_items ADD COLUMN grp TEXT;
