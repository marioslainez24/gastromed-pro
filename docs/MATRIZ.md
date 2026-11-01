# Matriz de requisitos y cobertura — GastroMed Pro

Actualizada: 30 de octubre de 2026 · versión 0.16.0 (rama desarrollo) · ver también `COMPARATIVA.md`

**Fuentes:** el documento de requisitos del Dr. Mario Lainez. Las páginas de Medilink (softwaremedilink.com y ayuda.softwaremedilink.com) **no fueron accesibles** desde el entorno de desarrollo (bloqueo de red). Por lo tanto **no se afirma haber revisado ninguna función de Medilink**; la comparación queda pendiente hasta que se puedan consultar (o el usuario envíe capturas/textos).

**Estados:**
- ✅ **Probado** — implementado y con prueba automática ejecutada que pasa.
- 🟡 **Pendiente de validación** — implementado, falta validación (clínica, en equipo real o en producción).
- 🔌 **Proveedor externo** — depende de contratar/configurar un servicio.
- ⬜ **Pendiente** — no desarrollado aún.

## Fase 1 — base

| # | Requisito | Estado | Evidencia / nota |
|---|---|---|---|
| 1.1 | Inicio de sesión con contraseña (scrypt) | ✅ | `test_login_correcto_e_incorrecto` |
| 1.2 | Bloqueo por intentos fallidos y límite por IP | ✅ | `test_bloqueo_tras_intentos_fallidos` |
| 1.3 | Sesiones de servidor con expiración por inactividad (30 min) y absoluta (12 h), revocación al salir | ✅ | `test_sesion_revocada_al_salir` (inactividad: 🟡 sin prueba automática) |
| 1.4 | Protección CSRF en toda modificación | ✅ | `test_csrf_obligatorio` |
| 1.5 | MFA (TOTP) opcional u obligatorio por política; secreto cifrado; sin reutilizar códigos | ✅ | `test_mfa_usuarios.py` (incluye vectores oficiales RFC 6238). Código QR: ⬜ |
| 1.6 | Roles y permisos por acción en servidor | ✅ | `test_recepcion_no_accede…`, `test_caja_y_enfermeria` |
| 1.7 | Permisos por sede | ⬜ | Tabla `user_sites` creada; reglas pendientes |
| 1.8 | Desactivar usuarios conservando autoría y cerrando sus sesiones | ✅ | `test_desactivar_usuario…` |
| 1.9 | Pantalla de usuarios: alta con contraseña temporal, rol, reactivar, restablecer acceso, cambio obligatorio de contraseña | ✅ | `test_crear_usuario…`; edición de permisos por rol ⬜ |
| 1.10 | Auditoría de accesos y cambios, inmutable y encadenada | ✅ | `test_auditoria_inmutable_y_encadenada` |
| 1.11 | Aislamiento entre organizaciones / cambio de identificador | ✅ | `test_cambiar_identificador_no_expone_otra_organizacion` |
| 1.12 | Cabeceras de seguridad (CSP sin inline, no-store, anti-iframe) | ✅ | `test_cabeceras_de_seguridad_y_cookies` |
| 1.13 | Sin secretos en código; producción exige clave y HTTPS | ✅ | `test_sin_secretos…`, `test_produccion_exige…` |
| 2.1 | Registro de paciente con ID interno independiente del documento | ✅ | `test_flujo_completo…` |
| 2.2 | Pacientes sin documento; validación DNI hondureño (13 dígitos) | ✅ | `test_deteccion_de_duplicados` |
| 2.3 | Búsqueda global (nombre sin tildes, expediente, DNI, teléfono) con autocompletado | ✅ | `test_paciente_visible_desde_otro_dispositivo…` + captura navegador |
| 2.4 | Paciente visible desde otro dispositivo | ✅ | Misma prueba (dos sesiones independientes) |
| 2.5 | Detección de duplicados con confirmación | ✅ | `test_deteccion_de_duplicados` |
| 2.6 | Fusión de expedientes con trazabilidad | ⬜ | Columna `merged_into` preparada |
| 2.7 | Alergias con reacción y gravedad; «sin alergias conocidas» ≠ «no investigado» | ✅ | Probado en flujo de receta; regla impide marcar «sin alergias» con alergias activas |
| 2.8 | Alertas clínicas visibles | ✅ | Banner en expediente, nota y receta |
| 2.9 | Antecedentes (personales, quirúrgicos, familiares, hábitos, hospitalizaciones, procedimientos), medicamentos actuales con conciliación, lista de problemas | ✅ | `test_antecedentes_medicamentos_problemas` |
| 2.10 | Historial cronológico de consultas y recetas | ✅ | `test_todas_las_pantallas_cargan` |
| 2.11 | Control de concurrencia (no sobrescribir en silencio) | ✅ | `test_concurrencia_no_sobrescribe_en_silencio` |
| 3.1 | Agenda diaria, semanal y mensual | ✅ | `test_todas_las_pantallas_cargan` + capturas |
| 3.2 | Tipos de cita y duraciones configurables | ✅ | `test_guardar_ajustes` |
| 3.3 | Prevención de cruces y reservas simultáneas (garantía en base de datos) | ✅ | `test_reservas_simultaneas…` (6 solicitudes paralelas → 1 aceptada) |
| 3.4 | Estados y transiciones válidas; llegada y sala de espera | ✅ | `test_flujo_completo…`, `test_cancelar_libera…` |
| 3.5 | Reprogramación con historial | ✅ | `test_todas_las_pantallas_cargan` |
| 3.6 | Disponibilidad por consultorio y equipo; horarios del profesional; bloqueos/vacaciones; lista de espera | 🟡 | Horarios y bloqueos ✅ (`test_blocks_and_working_hours`); por equipo y lista de espera ⬜ |
| 3.7 | Reserva online, recordatorios, calendarios externos | 🟡 | Recordatorios por correo propio ✅ y WhatsApp manual (wa.me) ✅ (`test_fase5`); reserva online y calendarios: no solicitados |
| 4.1 | Nota de primera vez / subsecuente; plantillas SOAP y narrativa | ✅ | |
| 4.2 | Signos vitales con rangos de plausibilidad; IMC (OMS: kg/m²) | ✅ | IMC verificado: 70 kg / 170 cm = 24,2 |
| 4.3 | Borrador con autoguardado en servidor y aviso de cambios sin guardar | ✅ | Prueba + navegador real |
| 4.4 | Nota persiste tras cerrar y abrir sesión | ✅ | `test_flujo_completo…` |
| 4.5 | Nota finalizada inmutable (aplicación y base de datos) + adendas | ✅ | `test_nota_finalizada_inmutable_y_adenda` |
| 4.6 | Reutilizar información previa mostrando su fecha y exigiendo revisión | ✅ | Se muestra aparte; copiar inserta la fecha y «revisar» |
| 4.7 | Diagnósticos codificados con catálogo autorizado | ⬜ | Requiere catálogo CIE con licencia/fuente oficial |
| 4.8 | Plantillas personalizables | ✅ | Plantillas de nota y frases (`test_frases_documentos.py`) |
| 5.1 | Receta con principio activo, presentación, dosis, unidad, vía, frecuencia, duración, cantidad, indicaciones | ✅ | |
| 5.2 | PDF carta y A4 con encabezado del Dr. Mario Lainez | ✅ | Dimensiones y texto verificados (pypdf) |
| 5.3 | Receta inmutable; anulación con motivo y marca ANULADA | 🟡 | Triggers activos; sin prueba automática de anulación aún |
| 5.4 | Advertencia de alergias no investigadas antes de emitir | ✅ | |
| 5.5 | Interacciones / vademécum | 🔌 | **No disponible**: se indica en pantalla; no se inventa base farmacológica |
| 5.6 | Colegiación, dirección, teléfonos editables | ✅ | `test_guardar_ajustes` |
| 5.7 | Logo e imagen de firma en recetas | ✅ | También en órdenes e informes (`test_logo_and_signature_upload_and_pdf`) |
| 5.8 | Firma electrónica verificable | 🔌 | No implementada; el PDF lo declara |
| 6.1 | Archivos privados: PDF/JPG/PNG/HEIC, foto desde celular, validación por contenido, rechazo de PDF activos, 20 MB, cifrado en disco, acceso solo clínico | ✅ | `test_expediente_archivos.py` + navegador. Antivirus: 🟡 pendiente en servidor |
| 6.2 | Respaldos cifrados, verificación y restauración (registros + adjuntos) | ✅ | `test_respaldo.py`. Programación diaria automática: ⬜ (en el servidor) |
| 6.3 | Exportación completa (CSV + adjuntos descifrados) | ✅ | `test_exportacion_completa` |
| 7.1 | Interfaz en español, PC y celular, modo claro/oscuro | ✅ | Capturas en `evidencia/capturas` (sin errores de JavaScript) |
| 7.2 | PWA instalable sin guardar expedientes en el dispositivo | 🟡 | Manifiesto + service worker solo estático; con certificado propio el celular puede no permitir instalarla |
| 7.3 | Accesibilidad (teclado, contraste, foco visible, atajo «/») | 🟡 | Implementado; falta auditoría formal |
| 7.4 | Configuración Honduras / HNL / America/Tegucigalpa | ✅ | |
| 8.1 | Servidor privado en la PC del consultorio (Windows 11) con instalador de doble clic | 🟡 | Simulación completa probada (`test_consultorio.py`); falta validar en Windows real |
| 8.2 | Acceso desde celular en el Wi-Fi del consultorio | ✅ | HTTPS con certificado propio en el puerto 8443; http desde la red se redirige (`test_lan_http_redirects_to_https`, prueba del .exe) |
| 8.3 | Respaldo diario automático, verificado, con copia a disco externo y retención | ✅ | `test_instalacion_respaldo_y_diagnostico…`, `test_retencion…`; tarea de Windows 🟡 |
| 8.4 | Modo demostración separado de los datos reales | ✅ | Base y puerto propios |
| L.1 | Solicitud de laboratorio tipo hoja: secciones, >300 pruebas, 24 perfiles, buscador, PDF agrupado | ✅ | `test_solicitud_laboratorio.py` + navegador |
| N.6 | Antecedentes con clics que se arrastran a cada nota nueva | ✅ (sin publicar) | `test_v016.py` + navegador |
| C.9 | Carta al médico que refirió desde la nota o la endoscopia | ✅ (sin publicar) | `test_v016.py` + navegador |
| N.4 | Nota anterior: mostrar todo y copiar (por campo o todo) con marca de revisión | ✅ (sin publicar) | `test_v015.py` + navegador |
| N.5 | Un solo «Plan», sin diagnósticos diferenciales (notas antiguas intactas) | ✅ (sin publicar) | `test_v015.py` |
| L.2 | Otros resultados de laboratorio escritos a mano, recordados en el catálogo | ✅ (sin publicar) | `test_v015.py` + navegador |
| L.3 | Solicitudes de imagen, endoscopia y colonoscopia con estudios para marcar | ✅ (sin publicar) | `test_v015.py` + navegador |
| S.1 | Copia cifrada de respaldos en Google Drive (gratis), activable con botón en Ajustes | ✅ (sin publicar) | `test_copia_drive.py` + prueba del .exe |
| E.4 | Hallazgos de endoscopia con clics y sugerencia de diagnóstico | ✅ (sin publicar) | `test_lote_v013.py` + navegador |
| E.5 | Recomendaciones por diagnóstico (texto del médico, sugeridas) | ✅ (sin publicar) | `test_lote_v013.py` + navegador |
| E.6 | Hojas de preparación y consentimiento con datos de la cita | ✅ (sin publicar) | `test_lote_v013.py` |
| E.7 | Etiquetas de frascos de biopsia | ✅ (sin publicar) | `test_lote_v013.py` |
| E.8 | Clasificaciones Sarin, Zargar, NICE, Kudo (verificadas) | ✅ (sin publicar) | `test_lote_v013.py` |
| A.1 | Sala de espera con «Atender», preconsulta de enfermería, cita atendida al finalizar | ✅ (sin publicar) | `test_lote_v013.py` + navegador |
| C.7 | Imprimir todo (receta, órdenes, documentos) en un PDF | ✅ (sin publicar) | `test_lote_v013.py` + prueba del .exe |
| C.8 | Resumen del paciente y cálculos rápidos con los últimos laboratorios | ✅ (sin publicar) | `test_lote_v013.py` + navegador |
| N.2 | Exploración física con clics (Normal por sistema, hallazgos, textos editables) | ✅ (sin publicar) | `test_exploracion_diagnosticos.py` + navegador |
| N.3 | Diagnósticos de consulta con CIE-10 verificado en la nota | ✅ (sin publicar) | `test_exploracion_diagnosticos.py` |
| N.1 | Asistente para redactar la historia de la enfermedad actual con clics (sin inventar; negativos solo si el médico lo indica) | ✅ | `test_asistente_historia.py` + navegador |
| E.3 | Diagnósticos endoscópicos frecuentes con CIE-10 (OMS 5.ª ed., verificados) en la conclusión | ✅ | `test_diagnosticos_endoscopia.py` + navegador |
| E.1 | Informe de endoscopia: descripción libre por segmento (EDA: esófago, UEG con línea Z, estómago, duodeno; colonoscopia un apartado) | ✅ | `test_hallazgos_texto.py` |
| E.2 | Botón «Normal» por segmento y «Todo normal», con textos editables por el médico | ✅ | `test_textos_normales_personalizables_y_restaurar` + navegador |

## Requisitos añadidos por la comparativa (ver COMPARATIVA.md)

| # | Requisito | Fase | Estado |
|---|---|---|---|
| C.1 | Confirmar o anular la cita en un clic desde el recordatorio | 5 | 🔌 |
| C.2 | Colores por tipo de cita en la agenda | 1b | ⬜ |
| C.3 | Horarios de atención por profesional y recursos (sala, equipo) | 1b | ⬜ |
| C.4 | Frases predefinidas (✅ v0.10.0) y categorías de consulta (⬜) | 2 | 🟡 |
| C.5 | Búsqueda de texto completo dentro del expediente | 2 | ⬜ |
| C.6 | Documentos clínicos (incapacidad, constancia, referencia, libre) con PDF, inmutables | 2 | ✅ |
| C.7 | Presupuesto desde el diagnóstico; estado de pago y cobro desde la agenda | 4 | ⬜ |
| C.8 | Reportes con comparativas mensuales, productividad, exportar a Excel | 4 | ⬜ |
| C.9 | Recall / vigilancia endoscópica automática | 3 | ⬜ |
| C.10 | Notas de enfermería del procedimiento que alimentan el informe | 3 | ⬜ |
| C.11 | Indicadores de calidad (tasa de detección de adenomas, etc.) | 3 | ⬜ |

## Fases 2 a 5 (alcance conservado)

| Fase | Contenido | Estado |
|---|---|---|
| 2 | Órdenes de laboratorio/imagen/endoscopia, resultados estructurados y tendencias, tareas y responsables, formularios GI (reflujo, disfagia, dolor abdominal, diarrea, estreñimiento, sangrado, anemia, ictericia, EII, páncreas/biliar), Bristol propio, diarios de síntomas, calculadoras validadas (Child-Pugh, MELD-Na, MELD 3.0, FIB-4, APRI, Maddrey, Lille, Glasgow-Blatchford, Rockall, BISAP) con fuente primaria, casos de referencia y revisión clínica | ⬜ |
| 3 | Informes de endoscopia alta, colonoscopia, rectosigmoidoscopia, CPRE, USE; clasificaciones (Los Ángeles, Praga, Boston, Forrest, París) tras verificar definiciones/licencias; imágenes y anotaciones; patología hasta cierre; pólipos y vigilancia; calidad de colonoscopia; trazabilidad de endoscopios; prueba de captura UVC con señal ficticia | ⬜ |
| 3b | Módulos de hepatología, EII, H. pylori, páncreas/vías biliares y nutrición | ⬜ |
| 4 | **DESCARTADA por decisión del Dr. Lainez (30-oct-2026).** Catálogo y tarifas, presupuestos, cuentas por cobrar, caja, gastos, comprobantes internos (≠ factura fiscal SAR), liquidaciones, inventario con lotes y vencimientos | ⬜ |
| 5 | Solo lo solicitado (v0.7.0): recordatorios por correo propio y WhatsApp manual ✅, dictado por voz del navegador ✅. Portal, reserva online, teleconsulta y campañas: no solicitados | 🟡 |

## Integraciones

| Integración | Proveedor | Estado |
|---|---|---|
| Correo | Cuenta Gmail del consultorio (SMTP, contraseña de aplicación) | ✅ gratis; probar con la cuenta real |
| WhatsApp | Enlace oficial wa.me (envío manual con un toque) | ✅ gratis; la API automática es de pago y no se usa |
| Pagos en línea | Por elegir (sin guardar tarjetas) | 🔌 pendiente |
| Firma electrónica | Por verificar requisitos en Honduras | 🔌 pendiente |
| Videollamada | Por elegir | 🔌 pendiente |
| Dictado (voz a texto) | Reconocimiento integrado de Chrome/Edge | ✅ gratis, desactivado por defecto, con aviso de privacidad |
| IA generativa | Ninguna (de pago) | ⬜ no incluida por decisión del usuario |
| Vademécum | Por identificar fuente con licencia | 🔌 pendiente |
| Facturación fiscal | Requisitos SAR por verificar | 🔌 pendiente |

## Criterios de aceptación globales (documento §20)

| Criterio | Estado |
|---|---|
| Registrar paciente y encontrarlo desde otro dispositivo | ✅ |
| Consulta persiste tras cerrar y abrir sesión | ✅ |
| Estudios privados solo con autorización | ✅ |
| Recepción no accede a información clínica | ✅ |
| Cambiar identificador no expone otro expediente | ✅ |
| Nota finalizada conserva su versión original | ✅ |
| Dos usuarios no sobrescriben silenciosamente | ✅ |
| Dos reservas simultáneas no ocupan el mismo recurso | ✅ (profesional; consultorio/equipo pendiente) |
| Recetas se imprimen correctamente | 🟡 PDF verificado; falta prueba de impresión física |
| Calculadoras coinciden con casos de referencia | ⬜ Fase 2 |
| Fallos de proveedores no simulan éxito | ⬜ (no hay proveedores aún) |
| Respaldos restauran registros y adjuntos | ✅ |
| Exportación con información clínica y archivos | ✅ |
| No hay secretos expuestos | ✅ |
| Flujos principales en PC y celular | 🟡 capturas en navegador real a 1366 px y 390 px; falta prueba en su equipo |
