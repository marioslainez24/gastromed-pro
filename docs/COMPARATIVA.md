# Comparativa con programas similares

Fecha de la revisión: 30 de octubre de 2026.

## Cómo se hizo y sus límites
- Los sitios oficiales de **Medilink** y de varios competidores (DigitalOcean, OpenEMR y otros) **están bloqueados** desde el entorno de desarrollo. No se afirma haber visto sus pantallas.
- Se usaron fuentes accesibles: reseñas y comparativas publicadas por terceros (algunas escritas por **competidores** de Medilink, lo que puede sesgarlas) y páginas oficiales de un proveedor especializado en gastroenterología (Modernizing Medicine, «gGastro»).
- Lo que dice una reseña no se toma como verificado. Cada función aparece con su fuente.

## Fuentes
| Ref. | Fuente | Fecha | Observación |
|---|---|---|---|
| R1 | Medesk – reseña de Medilink (medesk.net/es/blog/medilink-review) | publ. 20-sep-2023, act. 7-sep-2026 | Escrita por un competidor |
| R2 | ComparaSoftware – ficha de Medilink | sin fecha precisa | Directorio; precios «bajo cotización» |
| R3 | AgendaPro – «Medilink vs. AgendaPro» | 3-feb-2026 | Escrita por un competidor |
| R4 | Medesk – «Alternativas a Medilink» | sin fecha precisa | Nimbo, AppsMedical, DriCloud, Clinic Cloud |
| R5 | Medesk – comparativa de software médico | act. 27-may-2026 | 14 programas; cobertura parcial |
| R6 | ModMed – gGastro Endoscopy Report Writer (página oficial) | vigente | Estándar de referencia en gastroenterología (EE. UU.) |
| R7 | ModMed – «Gastroenterology EHR: the need to have» | vigente | Requisitos de un expediente gastroenterológico |

## Funciones observadas y su lugar en GastroMed Pro

| Función | Visto en | GastroMed Pro |
|---|---|---|
| Plataforma en la nube, accesible desde celular | R1, R2 | ✅ web adaptable + PWA |
| Agenda con vistas por recepción / profesional / clínica | R1 | ✅ día/semana/mes y filtro por profesional |
| Estados de cita y sala de espera | R1, R4 (Clinic Cloud) | ✅ |
| Indicadores de color por tipo/estado de cita | R2 | ✅ por estado; por tipo ⬜ |
| Horarios de atención por profesional | R1, R3 | ⬜ Fase 1b |
| Recursos: salas, equipos, personal de apoyo | R3 (AgendaPro) | ⬜ (requisito original: consultorio y equipo) |
| Reserva en línea, con pago anticipado opcional | R1, R3 | 🔌 Fase 5 |
| Recordatorios por correo/WhatsApp con confirmar o anular en un clic | R1, R4 | 🔌 Fase 5 (nuevo detalle: confirmación en un clic) |
| Sincronización con Google Calendar / Outlook | R1, R4 | 🔌 Fase 5 |
| Ficha con plantillas estructuradas por especialidad | R1, R2 | ✅ SOAP/narrativa; plantillas GI Fase 2 |
| Antecedentes, anamnesis, examen físico | R1 | ✅ (esta etapa añade antecedentes) |
| CIE precargado | R1, R4 (Medesk) | ⬜ Fase 2 (requiere fuente oficial OMS/OPS) |
| Respuestas/frases predefinidas | R1 | ⬜ Fase 2 (nuevo) |
| Categorías de consulta (general, urgencia, interconsulta) | R1 | ⬜ Fase 2 (nuevo) |
| Adjuntos (imágenes, PDF) | R1 | ✅ esta etapa |
| Búsqueda por palabras clave dentro del expediente | R1, R6, R7 | ⬜ Fase 2 (nuevo) |
| Envío de resultados por correo / impresión del historial | R1 | ⬜ Fase 2–5 |
| Dictado por voz con transcripción por IA | R1, R4 (DriCloud) | 🔌 Fase 5 (IA opcional, con aprobación) |
| Resumen clínico automático del historial | R1 | 🔌 Fase 5 (con citas a la fuente) |
| Recetas con vademécum integrado | R1 | 🔌 requiere vademécum con licencia |
| Recetas electrónicas enviadas a farmacias | R4 (DriCloud) | 🔌 depende de marco legal en Honduras |
| Documentos clínicos ilimitados (incapacidades, constancias) | R2 | ⬜ Fase 2 |
| Presupuestos generados desde el diagnóstico | R2 | ⬜ Fase 4 (nuevo detalle) |
| Estado de pago visible y cobro desde la agenda | R1, R2 | ⬜ Fase 4 (nuevo detalle) |
| Caja, pagos en línea, terminal POS | R1, R3 | ⬜ / 🔌 Fase 4 |
| Facturación electrónica con entidad fiscal | R1, R3, R4 | 🔌 requiere verificar requisitos del SAR |
| Comisiones / liquidación de profesionales | R3 | ⬜ Fase 4 |
| Inventario | R3, R5 | ⬜ Fase 4 |
| Reportes: ingresos, gastos, pacientes nuevos, productividad, exportar a Excel | R1 | ⬜ Fase 4 |
| Consultas de reportes en lenguaje natural (IA) | R1 | 🔌 Fase 5 |
| Encuestas de satisfacción | R3, R4 | ⬜ Fase 5 |
| Multi-sucursal | R3 | 🟡 modelo de datos listo |
| Roles y permisos (médico, caja, recepción, gerencia) | R1 | ✅ |
| Portal del paciente (citas, pagos, recetas, resultados) | R2 (anunciado), R4 (Nimbo) | ⬜ Fase 5 |
| Telemedicina con sala de espera virtual | R1, R4 | 🔌 Fase 5 |
| Marketing por correo / campañas | R3 | ⬜ Fase 5 (con consentimiento separado) |
| App nativa iOS/Android | R3, R4 | No previsto: la PWA cubre el uso; se reevalúa si hace falta |

### Referencia gastroenterológica (R6, R7)
| Función | GastroMed Pro |
|---|---|
| Informe de endoscopia con hallazgos, intervenciones y terapéuticas GI precargadas | ⬜ Fase 3 |
| Captura de imágenes/video con etiquetas sobre diagrama anatómico | ⬜ Fase 3 |
| Seguimiento automatizado de muestras de patología | ⬜ Fase 3 |
| Indicadores de calidad (p. ej., tasa de detección de adenomas) | ⬜ Fase 3 |
| Registro de *recall* (vigilancia) automático | ⬜ Fase 3 (nuevo detalle) |
| Notas de enfermería que alimentan el informe del procedimiento | ⬜ Fase 3 (nuevo) |
| Conexión con monitores de signos vitales y endoscopios | ⬜ Fase 3+ (evaluar equipo real) |
| Búsqueda de texto completo para identificar candidatos a investigación | ⬜ Fase 2 (nuevo) |
| Interoperabilidad hospitalaria | ⬜ futuro (estándar HL7 FHIR) |

## Conclusión
El alcance del documento original ya cubre la mayoría de lo observado. La comparativa **añadió** estos requisitos a la matriz:
confirmación de cita en un clic, indicadores de color por tipo, frases predefinidas, categorías de consulta, búsqueda de texto completo en el expediente, presupuestos desde el diagnóstico, cobro desde la agenda, *recall* automático, notas de enfermería del procedimiento.
