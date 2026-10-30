# Matriz de requisitos y cobertura — GastroMed Pro

Actualizada: 30 de octubre de 2026 · versión 0.2.0 · ver también `COMPARATIVA.md`

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
| 3.6 | Disponibilidad por consultorio y equipo; horarios del profesional; bloqueos/vacaciones; lista de espera | ⬜ | |
| 3.7 | Reserva online, recordatorios, calendarios externos | 🔌⬜ | Fase 5 |
| 4.1 | Nota de primera vez / subsecuente; plantillas SOAP y narrativa | ✅ | |
| 4.2 | Signos vitales con rangos de plausibilidad; IMC (OMS: kg/m²) | ✅ | IMC verificado: 70 kg / 170 cm = 24,2 |
| 4.3 | Borrador con autoguardado en servidor y aviso de cambios sin guardar | ✅ | Prueba + navegador real |
| 4.4 | Nota persiste tras cerrar y abrir sesión | ✅ | `test_flujo_completo…` |
| 4.5 | Nota finalizada inmutable (aplicación y base de datos) + adendas | ✅ | `test_nota_finalizada_inmutable_y_adenda` |
| 4.6 | Reutilizar información previa mostrando su fecha y exigiendo revisión | ✅ | Se muestra aparte; copiar inserta la fecha y «revisar» |
| 4.7 | Diagnósticos codificados con catálogo autorizado | ⬜ | Requiere catálogo CIE con licencia/fuente oficial |
| 4.8 | Plantillas personalizables | ⬜ | Fase 2 |
| 5.1 | Receta con principio activo, presentación, dosis, unidad, vía, frecuencia, duración, cantidad, indicaciones | ✅ | |
| 5.2 | PDF carta y A4 con encabezado del Dr. Mario Lainez | ✅ | Dimensiones y texto verificados (pypdf) |
| 5.3 | Receta inmutable; anulación con motivo y marca ANULADA | 🟡 | Triggers activos; sin prueba automática de anulación aún |
| 5.4 | Advertencia de alergias no investigadas antes de emitir | ✅ | |
| 5.5 | Interacciones / vademécum | 🔌 | **No disponible**: se indica en pantalla; no se inventa base farmacológica |
| 5.6 | Colegiación, dirección, teléfonos editables | ✅ | `test_guardar_ajustes` |
| 5.7 | Logo e imagen de firma en recetas | ⬜ | Módulo de archivos listo; falta integrarlo al PDF |
| 5.8 | Firma electrónica verificable | 🔌 | No implementada; el PDF lo declara |
| 6.1 | Archivos privados: PDF/JPG/PNG/HEIC, foto desde celular, validación por contenido, rechazo de PDF activos, 20 MB, cifrado en disco, acceso solo clínico | ✅ | `test_expediente_archivos.py` + navegador. Antivirus: 🟡 pendiente en servidor |
| 6.2 | Respaldos cifrados, verificación y restauración (registros + adjuntos) | ✅ | `test_respaldo.py`. Programación diaria automática: ⬜ (en el servidor) |
| 6.3 | Exportación completa (CSV + adjuntos descifrados) | ✅ | `test_exportacion_completa` |
| 7.1 | Interfaz en español, PC y celular, modo claro/oscuro | ✅ | Capturas en `evidencia/capturas` (sin errores de JavaScript) |
| 7.2 | PWA instalable sin guardar expedientes en el dispositivo | 🟡 | Manifiesto + service worker solo estático; instalar requiere HTTPS |
| 7.3 | Accesibilidad (teclado, contraste, foco visible, atajo «/») | 🟡 | Implementado; falta auditoría formal |
| 7.4 | Configuración Honduras / HNL / America/Tegucigalpa | ✅ | |

## Requisitos añadidos por la comparativa (ver COMPARATIVA.md)

| # | Requisito | Fase | Estado |
|---|---|---|---|
| C.1 | Confirmar o anular la cita en un clic desde el recordatorio | 5 | 🔌 |
| C.2 | Colores por tipo de cita en la agenda | 1b | ⬜ |
| C.3 | Horarios de atención por profesional y recursos (sala, equipo) | 1b | ⬜ |
| C.4 | Frases predefinidas y categorías de consulta (general, urgencia, interconsulta) | 2 | ⬜ |
| C.5 | Búsqueda de texto completo dentro del expediente | 2 | ⬜ |
| C.6 | Documentos clínicos por plantilla (incapacidades, constancias) | 2 | ⬜ |
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
| 4 | Catálogo y tarifas, presupuestos, cuentas por cobrar, caja, gastos, comprobantes internos (≠ factura fiscal SAR), liquidaciones, inventario con lotes y vencimientos | ⬜ |
| 5 | Portal del paciente, reserva online, recordatorios (correo/WhatsApp), teleconsulta, campañas con consentimiento, IA opcional bajo las reglas del documento | 🔌⬜ |

## Integraciones

| Integración | Proveedor | Estado |
|---|---|---|
| Correo | Por elegir | 🔌 pendiente de cotizar y aprobar |
| WhatsApp | API oficial vía proveedor autorizado | 🔌 pendiente |
| Pagos en línea | Por elegir (sin guardar tarjetas) | 🔌 pendiente |
| Firma electrónica | Por verificar requisitos en Honduras | 🔌 pendiente |
| Videollamada | Por elegir | 🔌 pendiente |
| IA | Por elegir, con acuerdo de datos | 🔌 pendiente (desactivada por defecto) |
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
