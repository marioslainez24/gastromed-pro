# Bitácora de progreso — GastroMed Pro

Este archivo permite continuar el trabajo en futuras conversaciones. Léalo primero.

## Decisión 30-oct-2026: Fase 4 descartada
El Dr. Lainez indicó que **no desea** las funciones administrativas y financieras (cobros, presupuestos, caja, convenios, comprobantes,
liquidaciones, inventario ni reportes financieros). No se desarrollarán salvo que él lo solicite de nuevo.
Siguiente fase disponible: Fase 5 (portal del paciente, recordatorios, teleconsulta, IA opcional) o mejoras de las fases 1–3.

## Decisión 30-oct-2026: de la Fase 5 solo recordatorios y dictado, sin servicios de pago (el dictado se quitó el 1-nov-2026)
El Dr. Lainez pidió solo recordatorios de citas (correo o WhatsApp) y dictado de notas, **sin ningún servicio de pago**: si algo cuesta,
se sustituye por una opción gratuita. Portal del paciente, reserva en línea, teleconsulta y campañas: no solicitados.

## Etapa 17 · 1-nov-2026 · Sin dictado ni diario; calculadoras de otras especialidades (v0.17.0 · PUBLICADA)

**Pedido del Dr. Lainez:** «quita la opción de dictar y lo de diario de síntomas, añade más cálculos aparte de los de gastroenterología y haz
el programa de un solo» (publicar sin esperar el «ya»).
- **Dictado quitado**: sin botón 🎤 en notas ni endoscopia, sin sección en Ajustes (pestaña ahora «Recordatorios»), sin `dictado.js`
  ni la ruta `/ajustes/dictado`; el micrófono queda bloqueado en todas las pantallas. Las columnas `dictation_*` de la base se dejan sin uso.
- **Diario de síntomas quitado**: sin pestaña ni pantalla (`/pacientes/<id>/diario` da 404). La tabla `symptom_diary` y sus datos se conservan.
- **11 calculadoras nuevas** (`app/calculators.py`), cada una con fuente, población, límites y casos de referencia:
  - Riñón y electrolitos: CKD-EPI 2021 (Inker NEJM 2021; caso externo MetricGate 53.5), Cockcroft-Gault, calcio corregido (Payne),
    brecha aniónica (Kraut y Madias).
  - Cardiología: CHA₂DS₂-VASc (Lip 2010), HAS-BLED (Pisters 2010), QTc de Bazett (umbrales AHA/ACCF/HRS 2009).
  - Infección y urgencias: CURB-65 (Lim 2003), qSOFA (Sepsis-3), escala de coma de Glasgow (Teasdale 1974).
  - General: superficie corporal de Mosteller.
  - Se rellenan solas con creatinina, BUN, sodio y albúmina del expediente, y con la edad y el sexo del paciente.
  - Como todas, deben aprobarse en «Calculadoras → Revisar» antes de poder guardar un resultado en el expediente.
**Cómo se comprobó**: 174 pruebas (`test_v017.py` y casos de referencia); navegador real PC y celular actualizando desde v0.16.0;
prueba del ejecutable.

## Etapa 16 · 31-oct-2026 · Antecedentes con clics que se arrastran y carta al médico que refirió (v0.16.0 · rama `desarrollo`, SIN publicar)

**Pedido del Dr. Lainez:** ideas 4 y 5.
- **Antecedentes con clics** (`app/antecedents.py`): panel «＋ Antecedentes con clics» en la nota (campo nuevo «Antecedentes») y en el expediente:
  patológicos, quirúrgicos, familiares (con parentesco), procedimientos previos, hábitos (tabaco, alcohol, drogas: la respuesta nueva deja como
  no vigente la anterior) y «Otro» con año. Se guardan en el expediente (`patient_history`, sin borrar nada; sin duplicados) y cada **nota nueva**
  trae el campo «Antecedentes» ya escrito con antecedentes, medicamentos actuales y alergias (copia del momento, editable). Si el médico no ha
  editado el campo, se actualiza al marcar; si lo editó, el botón «↻ Actualizar desde el expediente» lo reemplaza (con confirmación).
- **Carta al médico que refirió**: botón en la nota («✉ Preparar carta») y en el informe de endoscopia. Arma el texto con el médico remitente del
  expediente, motivo, impresión, diagnósticos y plan (nota) o hallazgos por segmento, línea Z, conclusión, frascos y recomendaciones (endoscopia).
  El médico revisa y emite como documento clínico (inmutable, PDF con encabezado y firma). Avisa si la nota/estudio sigue en borrador o si falta
  el nombre del remitente.
**Cómo se comprobó**: 149 pruebas (2 nuevas en `test_v016.py`); navegador real PC y celular actualizando desde v0.14.0; prueba del ejecutable.

## Etapa 15 · 31-oct-2026 · Nota anterior útil, plan único, otros resultados y solicitudes con estudios para marcar (v0.15.0 · rama `desarrollo`, SIN publicar)

**Pedido del Dr. Lainez** (tras probar la v0.14.0):
1. El panel «Información de la nota anterior» no hacía nada → **corregido**: solo mostraba diagnósticos/plan y, si la nota anterior no los tenía,
   quedaba vacío. Ahora muestra todo lo que tenía (historia, exploración, impresión, diagnósticos, plan), con «Copiar» por campo y
   «Copiar todo a esta nota»; cada texto lleva «[Tomado de la nota del … — revisar]». Los campos antiguos de plan se copian al «Plan» nuevo.
2. **Quitar «Diagnósticos diferenciales» y dejar un solo «Plan»**: la nota tiene ahora un único campo «Plan». Los campos anteriores
   (diferenciales, plan diagnóstico/terapéutico, educación, signos de alarma, seguimiento) solo aparecen en notas que ya tenían texto en ellos,
   para no perder información. Frases y plantillas antiguas se reasignan a «Plan»/«Diagnósticos» (migración 0012).
3. **Otros resultados de laboratorio**: cuadro en «Registrar resultados» para escribir pruebas que no están en la lista (nombre, resultado, unidad,
   rangos). Al guardar, la prueba queda en el catálogo («Otros (agregados por usted)») sin duplicarse; numérica o cualitativa según el valor.
4. **Solicitudes de imagen, endoscopia y la nueva de colonoscopia** con lista para marcar (`app/study_catalog.py`): ultrasonido (incl. Doppler del eje
   esplenoportal, elastografía), TAC (incl. trifásica de hígado, páncreas, entero-TAC), resonancia (CPRM…), radiología con contraste, medicina nuclear;
   endoscopia alta diagnóstica/terapéutica, CPRE, USE, cápsula, pH-metría, manometría; colonoscopia diagnóstica/tamizaje/vigilancia/polipectomía,
   rectosigmoidoscopia, anoscopia, ligadura de hemorroides, manometría anorrectal. Buscador, contador y «Otros». La colonoscopia se guarda como
   orden de endoscopia con título propio (`orders.study_label`); el PDF dice «SOLICITUD DE COLONOSCOPIA».
**Cómo se comprobó**: 147 pruebas (4 nuevas en `test_v015.py`); navegador real PC y celular actualizando desde v0.14.0 con perfil persistente;
prueba del ejecutable ampliada.

## Etapa 14.1 · 31-oct-2026 · Copia de los respaldos en Google Drive con botón en Ajustes (v0.14.0 · rama `desarrollo`, SIN publicar)

**Pedido del Dr. Lainez:** copia de respaldo cifrada en Google Drive, gratis, que él active con un botón en Ajustes.
**Qué quedó funcionando**
- Nueva pestaña **Ajustes → Respaldos** (solo propietario): estado del respaldo diario (último, tamaño, antigüedad, mensajes) y la sección
  «Copia fuera del consultorio (Google Drive, gratis)», **desactivada por defecto**.
- Usa **Google Drive para computadora** (gratis): el programa copia cada respaldo cifrado (.gmbak) a `<Mi unidad>\GastroMed-respaldos` y Drive lo sube.
  Sin API ni cuenta de Google en el programa. Detecta solo las carpetas «Mi unidad»/«My Drive» (y OneDrive); también se puede escribir la ruta.
- Botones: **Activar** (comprueba que se pueda escribir), **Copiar ahora**, **Desactivar** (no borra lo que ya está en Drive). Conserva las últimas
  3/7/14/30 copias en Drive. Copia atómica (archivo «.parcial» renombrado). Si Drive no está disponible, avisa sin afectar el respaldo local.
- Solo se configura desde la PC del consultorio (no desde el celular). La clave de respaldo NUNCA se sube; la pantalla lo advierte.
- Migración 0011 (`clinic_settings.offsite_*`).
**Cómo se comprobó**: 143 pruebas (2 nuevas en `test_copia_drive.py`: apagada por defecto, carpeta inválida, copiar, conservar últimas N, Drive
desconectado, desactivar, permisos y acceso remoto); navegador real; prueba del ejecutable activando y copiando.

## Etapa 14 · 31-oct-2026 · Diez mejoras para endoscopia y consulta (v0.14.0 · rama `desarrollo`, SIN publicar)

**Pedido del Dr. Lainez:** ideas 5 a 14 de la lista. Sigue vigente: no construir el .exe hasta que diga «ya».
**Qué quedó funcionando (probado, sin publicar)**
- **Hallazgos de endoscopia con clics** (`app/endo_findings.py`): «＋ Hallazgo con clics» en cada segmento (esófago, UEG, estómago, duodeno, colon y
  rectosigmoides): esofagitis LA, Barrett (Praga), várices, cándida, eosinofílica, úlcera, estenosis, cáusticos (Zargar), hernia hiatal, Mallory-Weiss,
  eritema/erosiones/atrofia por localización, gastropatía hipertensiva, várices gástricas (Sarin), GAVE, úlceras Forrest, pólipos, lesiones,
  pólipo de colon (tamaño, localización, París, NICE, resección), divertículos, hemorroides, inflamación (signos, distribución, extensión), etc.
  Redacta solo lo marcado y SUGIERE el diagnóstico con CIE-10 para la conclusión (el médico decide con un clic). Si el segmento tenía el texto
  normal, lo reemplaza y lo avisa.
- **Recomendaciones por diagnóstico** (Endoscopia → Recomendaciones): las escribe el médico; aparecen como sugerencia según la conclusión.
- **Hojas de preparación y consentimiento** por tipo de estudio (Endoscopia → Hojas): borrador sin productos, dosis ni riesgos; solo se imprimen
  después de que el médico las revisa y guarda. Se llenan con paciente, identidad, fecha y hora de la cita. Enlaces en la cita y en Procedimientos.
  Recepción puede imprimir la preparación, no el consentimiento.
- **Etiquetas de frascos** en PDF (2×6 por hoja): nombre, expediente, nacimiento, estudio, fecha, frasco, sitio, fragmentos.
- **Clasificaciones** Sarin, Zargar, NICE y Kudo, verificadas (fuentes en `endoscopy_defs.py`), en la tabla de hallazgos y en el catálogo.
- **Sala de espera**: espera en minutos, «✓ Preconsulta», botón «Atender →» que abre la nota directamente (sin elegir tipo; usa la última plantilla
  del médico); lista «En consulta»; al finalizar la nota la cita pasa sola a «atendida».
- **Preconsulta de enfermería** (permiso nuevo `preconsulta.registrar`, migración 0010): signos vitales y motivo que pasan a la nota.
- **Imprimir todo** en la nota: recetas, órdenes y documentos del día en un PDF (pypdf incluido en el .exe).
- **Resumen del paciente** arriba del expediente: problemas, medicamentos, última consulta, último estudio por tipo, patología pendiente, control,
  últimos laboratorios con tendencia, pendientes, próxima cita.
- **Cálculos rápidos** (`app/quick_calcs.py`) en el resumen: Child-Pugh, MELD-Na, MELD 3.0, FIB-4, APRI, Maddrey con los últimos laboratorios y su
  fecha; resultado PRELIMINAR solo si todo viene del expediente (nunca supone ascitis, encefalopatía ni diálisis); aviso si los datos tienen >3 meses.
**Cómo se comprobó**: 141 pruebas (10 nuevas en `test_lote_v013.py`); navegador real PC y celular actualizando desde v0.12.0 con perfil persistente;
prueba del ejecutable ampliada (imprimir todo, etiquetas, hojas, recomendaciones, resumen).

## Etapa 13 · 31-oct-2026 · Exploración física con clics y diagnósticos de consulta con CIE-10 (v0.13.0 · rama `desarrollo`, SIN publicar)

**Instrucción del Dr. Lainez:** hacer estas mejoras pero NO construir el .exe hasta que él diga «ya». Por eso el trabajo está en la rama
`desarrollo` (la construcción automática solo corre en `main`). Al recibir «ya»: fusionar `desarrollo` en `main` y empujar.
**Qué quedó funcionando (probado, sin publicar)**
- 🩺 «Exploración física con clics» encima de *Exploración física general* (SOAP) o en la nota narrativa: «Normal» por sistema (general,
  cardiopulmonar, abdomen, tacto rectal), «✓ Todo normal y escribir» (no incluye tacto rectal) y hallazgos por clic: palidez, ictericia, estigmas,
  edema, asterixis; corazón/pulmón; abdomen (inspección, dolor por cuadrante, Murphy, McBurney, rebote, defensa, Rovsing, hepato/esplenomegalia,
  borde hepático en cm, masa, ascitis, peristalsis); tacto rectal (hemorroides, fisura, tono, masa, guante con sangre/melena).
  Redacta SOLO lo marcado (`app/exam.py`); «Resto sin alteraciones» solo si se marca. General y cardiopulmonar → exploración general; abdomen y
  tacto rectal → exploración abdominal. Textos normales editables en Ajustes → Frases y plantillas (migración 0009).
- «＋ Diagnóstico ▾» en *Diagnósticos* de la nota: 96 diagnósticos de consulta (síntomas, esófago-estómago, intestino, ano-recto, sangrado, hígado,
  vía biliar-páncreas, oncología con histología, antecedentes). CIE-10 OMS 5.ª ed. verificado en classbrowser.nhs.uk (A00-A09, B15-B19, B95-B98,
  R10-R19, R70-R79, Z80-Z99 además de los bloques K y C). H. pylori = B98.0 (complementario). Sin código verificable (anemia ferropénica,
  intolerancia a la lactosa, pérdida de peso): se escribe sin código.
**Cómo se comprobó**: 131 pruebas (5 nuevas en `test_exploracion_diagnosticos.py`); navegador real PC y celular actualizando desde v0.12.0 con perfil
persistente; prueba del ejecutable en local.

## Etapa 12 · 31-oct-2026 · Asistente para redactar la historia de la enfermedad actual (v0.12.0)

**Pedido del Dr. Lainez:** lo que más tiempo le toma en la consulta es escribir la historia de la enfermedad actual.
**Qué quedó funcionando**
- «✍ Asistente de historia» encima del campo *Historia de la enfermedad actual* (SOAP) o de *Nota narrativa*: elige el motivo (los 13 formularios GI)
  y marca opciones con clics (tiempo de evolución exacto con unidad, evolución, localización, carácter, síntomas, factores, signos de alarma…).
  «Escribir en la historia» agrega un párrafo redactado (`app/hea.py`) al final del campo; el médico lo corrige o dicta lo que falte.
- Regla: el texto contiene SOLO lo marcado. Los negativos («Niega…») se escriben únicamente si el médico marca
  «Interrogué los signos de alarma…». Valores no válidos se descartan. Con nada marcado solo sale la frase inicial.
- Las opciones marcadas se guardan también como formulario de la nota (datos estructurados).
- Los campos del asistente pertenecen a un formulario aparte (`form="hea-form"`) para no mezclarse con los de la nota (p. ej. «signos_alarma»).
**Cómo se comprobó**: 126 pruebas (4 nuevas en `test_asistente_historia.py`); navegador real PC y celular actualizando desde la v0.11.0 con perfil
persistente (redacción, autoguardado y recarga); prueba del ejecutable con el asistente.

## Etapa 11 · 31-oct-2026 · Diagnósticos frecuentes con CIE-10 en la conclusión de endoscopia (v0.11.0)

**Pedido del Dr. Lainez:** un desplegable con los diagnósticos más usados (p. ej., esofagitis grado A de Los Ángeles, gastropatía hipertensiva) con CIE-10.
**Qué quedó funcionando**
- Botón «＋ Diagnóstico ▾» junto a la conclusión: buscador y lista por grupo según el estudio (EDA/CPRE/USE: esófago, estómago, duodeno, vía biliar y
  páncreas; colonoscopia: colon y recto). 93 diagnósticos: Los Ángeles A–D, Barrett (Praga), hernia hiatal, várices por tamaño/signos rojos, úlceras
  gástricas y duodenales Forrest Ia–III, gastropatía hipertensiva, GAVE, pólipos, divertículos, hemorroides I–IV, colitis ulcerosa por extensión,
  Crohn, coledocolitiasis, etc. Cada clic agrega una línea; varios a la vez; casilla para incluir o no el código.
- Códigos CIE-10 de la OMS (5.ª ed.) comprobados uno por uno en classbrowser.nhs.uk (bloques C15-C26, D10-D36, I80-I89, K20-K31, K40-K46, K50-K52,
  K55-K64, K70-K77, K80-K87, K90-K93). Sin código propio → categoría general marcada con * (p. ej., gastropatía hipertensiva K31.8*).
  Sospecha de neoplasia → sin código hasta la histología. Prueba `test_diagnosticos_endoscopia.py` exige que todo código esté en la lista verificada.
- Pendiente: no se verificó un código para H. pylori ni candidiasis específica (se usa K20 para esofagitis); se pueden agregar como frases.
**Cómo se comprobó**: 122 pruebas; navegador real PC y celular **actualizando desde la v0.10.2 con perfil persistente** (el código nuevo cargó al primer
intento); prueba del ejecutable.

## Etapa 10.2 · 31-oct-2026 · Corrección grave: el navegador usaba el código de la primera instalación (v0.10.2)

**Reporte del Dr. Lainez:** el dictado no funciona y los botones «Normal» de endoscopia (y otros) no hacen nada.
**Causa (reproducida en navegador real con perfil persistente):** el service worker guardaba `app.js` y `app.css` con un nombre de caché fijo
(`gm-static-v1`) e ignoraba el `?v=` de la dirección, y `sw.js` nunca cambiaba; por eso el navegador servía PARA SIEMPRE la copia de la primera
instalación. Todo lo hecho en JavaScript desde entonces (botones Normal, frases, plantillas, hoja de laboratorio, subida una por una) no existía en su
navegador. Las pruebas no lo detectaban porque usan un navegador limpio.
**Corrección**
- Archivos del programa servidos con la versión en la dirección (`/static/v0.10.2/js/app.js`): al actualizar, el navegador recibe el código nuevo en la
  primera carga aunque tenga la copia vieja (comprobado: versión vieja instalada → actualización → una recarga → código nuevo).
- `sw.js` lleva la versión (la caché se renueva en cada versión) y pide primero a la PC; la copia guardada solo se usa sin conexión.
- Dictado: mensajes claros para cada error (micrófono bloqueado, navegador sin soporte, sin internet, sin voz) y aviso «Escuchando…».
- Pruebas nuevas `test_cache_navegador.py`; la prueba del .exe verifica el archivo versionado.
**Lección:** las pruebas de navegador deben incluir una actualización con un perfil que ya tenía la versión anterior.

## Etapa 10.1 · 31-oct-2026 · Corrección: imágenes de endoscopia que no se subían (v0.10.1)

**Problema reportado por el Dr. Lainez:** las imágenes de endoscopia nunca se subían.
**Causas encontradas (reproducidas en navegador real):**
1. Varias fotos a la vez se enviaban en un solo envío; al pasar de 21 MB el servidor rechazaba todo («Contenido demasiado grande»). 8 fotos de 3 MB bastaban.
2. Los formatos BMP y TIFF (frecuentes en torres de endoscopia y capturadoras) se rechazaban.
3. La subida recargaba la página y se perdía lo escrito en el informe sin guardar.

**Corrección**
- Las imágenes se suben **una por una** con progreso («Subiendo imagen 3 de 8…») y resumen de las que fallen con su motivo.
- BMP, TIFF, WebP y GIF se **convierten a JPG** de alta calidad (Pillow; plugins añadidos al .exe). HEIC del iPhone: mensaje con la solución gratuita
  (Ajustes → Cámara → Formatos → «Más compatible»).
- Antes de subir, el informe **se guarda solo** si había cambios.

**Cómo se comprobó**: 118 pruebas automáticas (3 nuevas en `test_imagenes_formatos.py`); navegador real: 8 JPG de 3 MB + BMP + TIFF a la vez → 10 imágenes y el texto
del informe conservado; prueba del ejecutable con conversión de BMP dentro del .exe.

## Etapa 10 · 31-oct-2026 · Frases, plantillas de nota y documentos clínicos (v0.10.0)

**Qué quedó funcionando**
- **Frases predefinidas** (*Ajustes → Frases y plantillas*): el médico escribe una frase una vez (nombre, campo y texto) y la inserta con un clic
  desde el botón «Frases» que aparece bajo cada campo de las notas, de los informes de endoscopia (hallazgos por segmento, conclusión,
  recomendaciones) y de los documentos. Editar, desactivar, y botón opcional «Agregar frases de ejemplo» (7 frases genéricas que él revisa).
- **Plantillas de nota**: «Guardar esta nota como plantilla» (solo textos, sin signos vitales; para SOAP, narrativa o ambas). En una nota nueva,
  «Plantilla → Aplicar» llena solo los campos vacíos. Renombrar, corregir y desactivar en Ajustes.
- **Documentos clínicos** (pestaña «Documentos» del paciente): constancia de incapacidad (días en número y letras, desde/hasta automático),
  constancia de atención (horario), referencia/interconsulta y documento libre. El diagnóstico solo se escribe si el médico lo marca (privacidad).
  Flujo: datos → «Preparar el texto» → revisar/editar → «Emitir». Inmutable (triggers), huella SHA-256, anulación con motivo, PDF carta/A4
  con logo, firma y marca ANULADO. Migración 0008.

**Cómo se comprobó**: 115 pruebas automáticas (7 nuevas en `test_frases_documentos.py`); navegador real PC y celular sin errores de JavaScript;
prueba del ejecutable ampliada (frases de ejemplo + incapacidad + PDF), que detectó y corrigió un error cuando la fecha venía vacía.

**Siguiente (pedido):** búsqueda dentro del expediente, CIE-10, clasificaciones adicionales de endoscopia, módulos de hepatología/EII/H. pylori/páncreas.

## Etapa 9 · 31-oct-2026 · Solicitud de laboratorio como la hoja de papel (v0.9.0)

**Pedido del Dr. Lainez:** que el apartado de laboratorio sea como la hoja de solicitud de análisis clínicos que usa (fotos enviadas),
con todas sus pruebas, para ir marcando.

**Qué quedó funcionando**
- Catálogo `app/lab_order_catalog.py` transcrito de la hoja (versión abril 2024): 20 secciones y más de 300 pruebas (hematología, coagulación,
  química en sangre y orina, orina, heces, hormonas, drogas y fármacos, inmunología, autoinmunes, infecciosas, marcadores tumorales, COVID-19,
  microbiología, biología molecular) y 24 perfiles (pre-operatorio, hepático, anemias, bioquímico, lipídico, diabético, tiroideos, renales, etc.).
  Solo nombres de pruebas: sin precios ni datos del laboratorio.
- Pantalla en columnas con casillas como el papel; buscador; contador de seleccionadas. Al marcar un perfil se marcan sus pruebas («en perfil»)
  y no se duplican en la orden. Campo para pruebas que no estén en la lista.
- La orden y el PDF muestran las pruebas agrupadas por sección (perfiles con sus componentes). Migración 0007 (`order_items.grp`).
- Las pruebas de un solo valor (creatinina, TGO, ferritina, calprotectina, etc.) siguen enlazadas con el registro de resultados.

**Cómo se comprobó**: 108 pruebas automáticas (3 nuevas); navegador real PC y celular sin errores de JavaScript; prueba del ejecutable con orden + PDF.

## Etapa 8 · 30-oct-2026 · Hallazgos por segmento con texto libre y botón «Normal» (v0.8.0)

**Pedido del Dr. Lainez:** en el informe, describir con sus palabras cada segmento; en EDA: esófago, unión esofagogástrica
(si coincide o no con la línea Z), estómago y duodeno; en colonoscopia un solo apartado; y un botón que escriba el estudio normal para ahorrar tiempo.

**Qué quedó funcionando**
- Apartado «Hallazgos por segmento» con un cuadro de texto por segmento: EDA (Esófago, Unión esofagogástrica, Estómago, Duodeno);
  colonoscopia, rectosigmoidoscopia, CPRE y USE con un solo apartado. El dictado por voz funciona en todos.
- Unión esofagogástrica: «Coincide / No coincide con la línea Z»; si no coincide, campos opcionales de línea Z e impronta diafragmática (cm de la arcada).
- Botón **Normal** en cada segmento y en la conclusión (si el campo ya tiene texto, pregunta antes de reemplazar) y botón **Todo normal**
  (llena solo los campos vacíos y marca «coincide»). El médico revisa y edita.
- Textos normales editables en *Endoscopia → Textos de estudio normal* (con «Restaurar predeterminados»); los informes finalizados no cambian.
- La tabla estructurada (clasificaciones, pólipos, frascos) se conserva como «Hallazgos detallados (opcional)», plegada; sigue alimentando patología y calidad.
- Para finalizar se exige descripción de hallazgos (texto o tabla). Vista de lectura y PDF muestran «Descripción de hallazgos» por segmento.
- Migración 0006 (`clinic_settings.endo_normal_texts`).

**Cómo se comprobó**: 105 pruebas automáticas (5 nuevas en `test_hallazgos_texto.py`); navegador real PC y celular sin errores de JavaScript
(captura `evidencia/capturas/v080-hallazgos-eda-pc.png`); prueba de humo del ejecutable ampliada (finaliza EDA con texto por segmento).

**Siguiente (pedido):** frases y plantillas, documentos clínicos (incapacidad, constancia), búsqueda en el expediente, CIE-10, clasificaciones adicionales, módulos de hepatología/EII/H. pylori/páncreas.

## Etapa 7 · 30-oct-2026 · Recordatorios, dictado y mejoras (v0.7.0)

**Qué quedó funcionando (todo gratuito)**
- **Recordatorio por correo automático** desde la cuenta Gmail del consultorio (contraseña de aplicación, cifrada en la PC). Revisión cada 10 min;
  envía X horas antes (configurable). Solo a pacientes con canal «Correo» y autorización registrada (quién y cuándo). Sin datos clínicos en el mensaje.
  Errores se registran como «falló» con el motivo (nunca se simula un envío); máximo 3 intentos; sin duplicados; al reprogramar se reenvía.
  Correo de prueba desde Ajustes.
- **WhatsApp sin API de pago:** botón por cita que abre WhatsApp (wa.me) con el mensaje escrito; la persona pulsa «Enviar». Requiere autorización del paciente.
- **Dictado por voz** con el reconocimiento integrado de Chrome/Edge (gratis), en notas clínicas e informes de endoscopia; comandos «punto», «coma»,
  «punto y aparte», «nueva línea», «dos puntos». Desactivado por defecto; para activarlo hay que aceptar el aviso (el audio lo procesa Google/Microsoft).
  Micrófono permitido solo en pantallas editables con el dictado activo. No inventa contenido: transcribe lo que el médico dice y él lo revisa.
- **Logo e imagen de firma** (cifrados) en recetas, órdenes e informes de endoscopia. La imagen de firma no es firma electrónica.
- **Horario de atención** por profesional (fuera de horario pide confirmación) y **bloqueos/vacaciones** (impiden agendar y reprogramar). Colores por tipo de cita.
- **Conexión cifrada para el celular:** el programa crea su propio certificado y atiende en https://IP:8443; las conexiones http desde otros equipos se redirigen a https.

**Cómo se comprobó**: 100 pruebas automáticas (13 nuevas con servidor de correo de prueba local); navegador real; prueba de humo del ejecutable con https.

**Pendiente / límites**: el dictado necesita internet y Chrome/Edge; en el celular hay que aceptar una vez el aviso del certificado (no es de una
autoridad comercial, que sería de pago). WhatsApp no es automático (sería de pago). Dictado local sin internet (Whisper) no incluido por peso y velocidad en una PC sin GPU.
Probar en sitio: envío real con Gmail del consultorio y micrófono del celular por https.

## Etapa 6 · 30-oct-2026 · Fase 3 (v0.6.0)

**Qué quedó funcionando**
- Informes estructurados de EDA, colonoscopia, rectosigmoidoscopia, CPRE y USE: indicación (tipo), consentimiento, ASA, comorbilidades, anticoagulación, preparación, sedación y monitorización documentadas por el profesional, equipo y asistentes, extensión y completitud, tiempo de retirada, escala de Boston, hallazgos por segmento con clasificaciones (Los Ángeles, Forrest, París, Praga C/M, tamaño de várices), biopsias por frasco, intervenciones, material, complicaciones, prótesis, conclusión, recomendaciones y fecha de vigilancia.
- Finalización inmutable (base de datos) con huella SHA-256 y adendas; datos mínimos obligatorios para finalizar.
- Imágenes: importación JPG/PNG o captura desde capturadora UVC (o señal de prueba), confirmación explícita del paciente, marca de agua con el paciente en el video, la cámara se apaga al salir; localización anatómica, leyenda, selección para el informe y marcas numeradas que NO alteran el original. PDF del informe con fotografías anotadas.
- Patología: frascos creados al finalizar, envío, resultado (categoría y displasia; inmutable), comunicación y cierre; extravío; tarea automática de seguimiento.
- Tablero de endoscopia: patología pendiente, vigilancia próxima/vencida, prótesis con fecha de revisión, procedimientos recientes.
- Indicadores de calidad con numerador, denominador y exclusiones: intubación cecal, ADR (confirmado por patología, ≥45 años, tamizaje), preparación adecuada, retirada ≥6 min, complicaciones.
- Endoscopios y bitácora de reprocesamiento inmutable (fuga fallida no puede ser «apto»).

**Cómo se comprobó**: 87 pruebas automáticas; navegador real con capturadora simulada; prueba de humo del ejecutable ampliada a endoscopia con imagen en PDF.

**Pendiente / límites**: compatibilidad con la capturadora real del consultorio (probar en sitio); intervalos de vigilancia NO se calculan (los fija el médico); clasificaciones adicionales (Kudo, NICE, Zargar, Spigelman…) pendientes.

## Etapa 5 · 30-oct-2026 · Fase 2 (v0.5.0)

**Qué quedó funcionando**
- Órdenes de laboratorio, imagen y endoscopia con PDF (carta/A4), prioridad, responsable de revisión y fecha esperada; estados automáticos (solicitada → parcial → recibido), cierre y anulación con motivo.
- Resultados estructurados con unidad y **rangos del informe del laboratorio** (no se inventan rangos), marca alto/bajo, comparación de las últimas 8 tomas y gráfica de tendencia (SVG propio). Valores inmutables en la base de datos; corrección por anulación.
- Pendientes: resultados por revisar (con registro de comunicación al paciente), órdenes sin resultado/vencidas, tareas con responsable y vencimiento.
- 13 formularios de gastroenterología dentro de la nota (bloqueados al finalizarla), escala de Bristol con ilustraciones propias, diario de síntomas con gráficas.
- 11 calculadoras: Child-Pugh, MELD-Na (OPTN 2016), MELD 3.0 (2021), FIB-4, APRI, Maddrey, Lille, Glasgow-Blatchford, Rockall (clínico y completo), BISAP, IMC. Cada una con fuente, verificación, población, fórmula, redondeo, datos ausentes, límites y casos de referencia calculados a mano. Importan datos del expediente mostrando la fecha. **Requieren aprobación del médico propietario** antes de guardar resultados; resultado guardado con entradas, origen, versión y autor (inmutable).
- Cuestionarios con licencia (GerdQ, Roma IV, Mayo, Harvey-Bradshaw, etc.) NO incluidos: pendientes de licencia.

**Cómo se comprobó**: 79 pruebas automáticas; navegador real PC y celular sin errores de JavaScript.

**Pendiente de verificar contra fuente primaria**: Lille (término de diferencia de bilirrubina) y regla de diálisis de MELD 3.0 — señalado en la pantalla de revisión.

**Siguiente:** Fase 3 (informes de endoscopia, imágenes, patología, vigilancia).

## Etapa 4 · 30-oct-2026 · Ejecutable único para Windows (v0.4.0)

**Decisión del Dr. Lainez:** un solo `GastroMedPro.exe`, sin instalar otros programas, para usar en su clínica.

- `gastromed_exe.py`: primer arranque crea `C:\GastroMed` y las claves (copia en el escritorio), configuración inicial en el navegador (solo desde la misma PC), servidor waitress en el puerto 8000 (PC + Wi-Fi), respaldo automático cada 24 h en segundo plano, abre el navegador.
- Construcción en Windows real con GitHub Actions (repositorio privado `marioslainez24/gastromed-pro`, flujo `construir-exe.yml`): pruebas automáticas en Windows → PyInstaller → prueba de humo del .exe (configuración, ingreso, paciente, nota, receta PDF, respaldo) → artefacto descargable.
- 45 pruebas automáticas.

## Etapa 3 · 30-oct-2026 · Servidor privado en la PC del consultorio (v0.3.0)

**Decisión del Dr. Lainez:** todo se guarda en su PC con Windows 11, que será el servidor privado. Se descarta Vultr por ahora.

**Qué quedó funcionando**
- Modo `consultorio`: claves obligatorias (nunca se generan en silencio), configuración guardada junto a los datos en `C:\GastroMed\datos`.
- `INSTALAR.bat` + `windows/instalar.ps1`: Python 3.13 vía winget, componentes, claves, cuenta del propietario, permisos de carpeta, pruebas automáticas en la PC, accesos directos, inicio automático, respaldo diario 21:00 (se ejecuta al encender si estaba apagada), firewall solo red privada, respaldo previo en actualizaciones.
- `servidor.py` (waitress) en puerto 8000 para la PC y el celular en el mismo Wi-Fi; muestra la dirección para el celular.
- Modo DEMOSTRACIÓN separado (puerto 8001, solo esta PC, base aparte).
- Respaldo automático: crear → verificar restaurando → copiar a disco externo → conservar 30. Diagnóstico de estado.

**Cómo se comprobó**
- 42 pruebas automáticas pasan, incluida una instalación simulada de punta a punta (configuración, re-ejecución sin cambiar claves, 3 respaldos automáticos con copia externa, diagnóstico «TODO CORRECTO»).
- Simulación manual: servidor iniciado con la configuración del consultorio, inicio de sesión correcto, respaldo copiado a la carpeta «USB».
- **No probado en Windows real** (entorno Linux, sin acceso a PyPI): el instalador PowerShell, waitress y los accesos directos quedan *pendientes de validación* en la PC del doctor.

**Pendiente inmediato**
1. Validar la instalación en la PC del doctor y corregir lo que aparezca.
2. HTTPS en la red local (certificado propio) para cifrar el tráfico Wi-Fi y permitir instalar la PWA.
3. Logo y firma en la receta; código QR para dos pasos; horarios por profesional y colores por tipo de cita.
4. Fase 2: laboratorio estructurado con tendencias, formularios GI, calculadoras validadas (con revisión del doctor).

## Etapa 2 · 30-oct-2026 · Fase 1 casi completa (v0.2.0)

**Qué quedó funcionando**
- Comparativa con programas similares (`COMPARATIVA.md`) y 11 requisitos nuevos en la matriz.
- Antecedentes, medicamentos actuales con conciliación y lista de problemas (nada se borra).
- Archivos privados: subida desde PC o cámara del celular, validación por contenido, cifrado en disco, acceso solo clínico, retiro con motivo.
- Verificación en dos pasos (TOTP), política para exigirla, cambio obligatorio de contraseña temporal.
- Pantalla de usuarios: alta, rol, agenda propia, desactivar/reactivar, restablecer acceso.
- Respaldos cifrados con verificación completa, restauración en carpeta nueva y exportación completa.

**Cómo se comprobó**
- `python -m pytest -q` → **38 pruebas pasan** (30-oct-2026), incluida una restauración completa que vuelve a levantar la aplicación y abre el mismo PDF byte por byte.
- Scripts de respaldo ejecutados sobre la base de demostración: crear → verificar (CORRECTO) → exportar.
- Navegador real en PC (1366 px) y celular (390 px, modo oscuro): búsqueda, subida de estudio, expediente, dos pasos, usuarios. Sin errores de JavaScript.

**Pendiente inmediato**
1. Puesta en línea (Vultr Miami recomendado) con HTTPS, disco cifrado, respaldos diarios automáticos y copia externa. Requiere que el Dr. Lainez cree la cuenta.
2. Logo y firma en la receta; código QR para dos pasos.
3. Horarios por profesional, bloqueos/vacaciones, colores por tipo de cita.
4. Fase 2: órdenes y resultados de laboratorio con tendencias, formularios GI y primeras calculadoras validadas.

## Etapa 1 · 30-oct-2026 · Primer flujo funcional

**Qué quedó funcionando**
- Inicio/cierre de sesión con sesiones de servidor, bloqueo por intentos, CSRF y cabeceras de seguridad.
- Roles con permisos por acción (propietario, médico, enfermería, recepción, caja).
- Pacientes: registro, edición con control de versión, búsqueda global con autocompletado, detección de duplicados, alergias y alertas.
- Agenda: día/semana/mes, nueva cita, estados, llegada/sala de espera, reprogramación con historial, imposibilidad de cruces (garantizada por la base de datos).
- Notas: primera/subsecuente, SOAP/narrativa, signos vitales con IMC, autoguardado, finalización inmutable con huella SHA-256, adendas, información previa con fecha.
- Recetas: varios medicamentos, PDF carta/A4, advertencia de alergias no investigadas, anulación con motivo.
- Ajustes de clínica, matriz de permisos, bitácora de auditoría con verificación de integridad.
- PWA (manifiesto + service worker que no guarda datos clínicos), modo claro/oscuro, diseño para celular.

**Cómo se comprobó**
- `python -m pytest -q` → 20 pruebas pasan (ejecutadas el 30-oct-2026).
- Navegador Chromium real (Playwright) a 1366×860 y 390×844: inicio de sesión, agenda, búsqueda, expediente, nota con autoguardado. Sin errores de JavaScript. Capturas en `evidencia/capturas/`.
- PDF de ejemplo: `evidencia/receta-ejemplo-carta.pdf`.

**Decisiones**
- Python/Flask/SQLite (ver ARQUITECTURA.md §1). El entorno de desarrollo no tenía acceso a npm ni a PyPI.
- Sin almacenamiento de expedientes en el dispositivo.
- Notas, recetas, historial de citas y auditoría son inmutables a nivel de base de datos.

**Pendiente inmediato (resto de la Fase 1), en orden**
1. Archivos privados: carga desde PC/celular, validación de tipo por contenido, límite de tamaño, enlaces temporales firmados, logo y firma en recetas.
2. Respaldos: copia consistente (API de respaldo de SQLite) + archivos, cifrado, script de restauración y prueba automática de restauración.
3. MFA (TOTP) para todos los usuarios con permisos clínicos o administrativos.
4. Pantalla de usuarios (alta, rol, desactivar, restablecer contraseña) y cambio de contraseña propio.
5. Antecedentes, medicamentos actuales, lista de problemas.
6. Despliegue en servidor con HTTPS (requiere su aprobación para contratar servicios).
7. Prueba automática de expiración por inactividad y de anulación de recetas.

**Bloqueos que requieren al Dr. Lainez**
- Elegir y aprobar el proveedor de servidor (costo mensual) para poder usarlo desde su PC y celular.
- Número de colegiación y datos del encabezado (se editan en Ajustes).
- Opcional: enviar capturas o texto de las funciones de Medilink que más usa, ya que sus páginas no fueron accesibles.
