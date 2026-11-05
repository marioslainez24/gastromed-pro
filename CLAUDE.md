# GastroMed Pro: guía para continuar el desarrollo (leer primero)

Usuario: Dr. Mario Lainez, gastroenterólogo en Honduras. No es programador. Comunicación en español sencillo y sin jerga técnica.
Repositorio: github.com/marioslainez24/gastromed-pro (rama `main`). Descarga para el usuario: `/releases/latest` → `GastroMedPro.exe`.
Bitácora detallada: `docs/PROGRESO.md`. Estado de cada requisito: `docs/MATRIZ.md`. Copias de ambos en el Proyecto «gastromed» de claude.ai.

## Decisiones del usuario (no cambiarlas sin preguntar)
- Todo se guarda en **su PC con Windows 11**, que actúa como servidor privado. No usar nube ni Vultr.
- Entrega: **un solo .exe**. No se le pide instalar nada más ni pagar ningún servicio. Se usa con pacientes reales.
- **Sin servicios de pago.** Si algo cuesta, se sustituye por una opción gratuita y se explica la diferencia.
  - WhatsApp: enlace wa.me con envío manual (no la API).
  - Correo: su Gmail con contraseña de aplicación.
  - Dictado: QUITADO en v0.17.0 a pedido del usuario (no volver a ponerlo sin que lo pida). Diario de síntomas también quitado.
  - HTTPS: certificado autofirmado.
- **Fase 4 (finanzas: cobros, caja, inventario, presupuestos) DESCARTADA.**
- **Fase 5:** solo recordatorios (el dictado se quitó en v0.17.0). Portal del paciente, reserva en línea, teleconsulta y campañas no fueron solicitados.
- Reglas del documento de requisitos original:
  - Sin integraciones falsas ni precios o fórmulas inventados.
  - Calculadoras con fuente y caso verificado.
  - IA o dictado no inventa contenido; el médico aprueba.
  - Ningún dato identificable a terceros sin autorización.
  - Auditoría encadenada; registros finalizados inmutables.
  - Pacientes ficticios en pruebas; secretos fuera del código.
  - Distinguir siempre ✅ hecho y probado, ⬜ pendiente y 🔌 proveedor externo.

## Arquitectura
Flask 3 + Jinja2 + SQLite, con WAL, tablas STRICT y triggers de inmutabilidad y de cruce de citas.
- **PDF y cifrado:** ReportLab para los PDF; Fernet (`cryptography`) para archivos, logo y firma, contraseña SMTP, secretos MFA y respaldos.
- **Frontend:** JS y CSS propios, sin librerías externas. CSP estricta: nada de scripts en línea; los datos se pasan con atributos `data-*`.
- **Migraciones:** `migrations/000N_*.sql`, aplicadas en orden. Nunca modificar una migración publicada: crear una nueva.
- **Permisos:** por acción en `app/security.py` (roles: propietario, medico, enfermeria, recepcion, caja).
- **Módulos:** un `views_*.py` por módulo. Al crear uno nuevo, registrar su blueprint en `app/__init__.py`.
- **Versión:** `APP_VERSION` en `app/__init__.py` y `build/version_info.txt`. Subirla en cada etapa.
- **Lanzador del ejecutable** (`gastromed_exe.py`):
  - Datos en `C:\GastroMed\datos` y respaldos en `C:\GastroMed\respaldos`. Las claves se guardan en `datos\gastromed.env` y se deja una copia en el Escritorio.
  - waitress en el puerto 8000; HTTPS con werkzeug en el 8443 con certificado propio (`datos\https-cert.pem`). El http desde la red se redirige a https; localhost sigue en http.
  - Hilos de fondo: respaldo cada 24 h (verificado restaurando) y recordatorios por correo cada 10 min.
  - La configuración inicial solo se permite desde localhost.

## Publicación (instrucción del 31-oct-2026)
El usuario pidió NO construir el .exe hasta que diga «ya». Trabajar en la rama `desarrollo` (empujarla para no perder el trabajo; no dispara la
construcción). Cuando diga «ya»: `git checkout main && git merge --ff-only desarrollo && git push`, esperar la CI y avisarle.
El 31-oct-2026 dijo «ya» y se publicó la v0.14.0 (todo lo acumulado). Para mejoras nuevas, seguir en `desarrollo` y esperar su «ya».
El 31-oct-2026 (noche) dijo «ya» otra vez: se publicó la v0.16.0 (incluye v0.15).
El 1-nov-2026 pidió publicar «de un solo» la v0.17.0 (sin dictado ni diario, calculadoras de otras especialidades). Lo siguiente, de nuevo en `desarrollo` hasta su «ya».
El 1-nov-2026 dijo «ya»: se publicó la v0.18.0 (descartar borradores; hojas de preparación de colonoscopía y EDA). Lo siguiente, en `desarrollo` hasta su «ya».
v0.19.0 (clasificaciones del consenso cubano; recetas frecuentes; partir del estudio anterior; estadísticas + Excel; búsqueda en expedientes; esquema anatómico; envío al correo del paciente) se publicó el 1-nov-2026 tras su «ya». Lo siguiente, en `desarrollo` hasta su «ya». El Dr. Lainez NO quiere atlas ni fotos de internet.
v0.20.0 (personal de endoscopia: endoscopista y asistentes con menús) se publicó el 1-nov-2026 tras su «ya». Lo siguiente, en `desarrollo` hasta su «ya».
v0.21.0 (hojas educativas y dietas; agenda en el calendario del celular) se publicó el 2-nov-2026 tras su «ya». Lo siguiente, en `desarrollo` hasta su «ya».
v0.22.0 (versión para Mac preparada pero NO publicada: chip Apple en `macos-14` e Intel en `macos-15-intel`; `build/GastroMedPro-mac.spec`, `build/LEEME-mac.txt`;
`adapt_paths` corrige rutas si se copia la carpeta datos de Windows a Mac) se publicó el 3-nov-2026 tras su «ya» como v0.22.0-28 (solo Windows); además letra 12 en todos los PDF y el informe de endoscopia
firmado por el endoscopista elegido (no por el usuario); estudios agrupados por fecha con visor en grande; DNI, nacimiento y más datos del paciente en el informe; tipo de atención (consulta externa/sala/emergencia, cama, hospital); ningún documento muestra folio (no volver a ponerlo); Endoscopista 1 y 2 con dos firmas, endoscopistas y asistentes en negrita; 3 estilos de informe en Ajustes (migración 0018). Lo siguiente, en `desarrollo` hasta su «ya».
v0.23.0 (descartar informes de endoscopia FINALIZADOS con motivo; migración 0019 `procedure_voids`; no se borran) se publicó el 3-nov-2026 tras su «ya» como v0.23.0-29 (solo Windows). Lo siguiente, en `desarrollo` hasta su «ya».
v0.24.0 (licencia por computadora con clave firmada Ed25519; secreto GitHub `GM_LICENCIA_CLAVE`; workflow «Activar una computadora»;
titular en pie de programa y PDF) se publicó el 4-nov-2026 tras su «ya» como v0.24.0-30 (el secreto `GM_LICENCIA_CLAVE` ya existe en GitHub;
sin él la CI falla a propósito). El 4-nov el repositorio SEGUÍA PÚBLICO: recordarle hacerlo privado (Settings → Danger Zone). Lo siguiente, en `desarrollo` hasta su «ya». Desde aquí NO se pueden cambiar ajustes ni secretos del repositorio (proxy).
v0.24.1 (documentos SIN pie «Generado con GastroMed Pro…» ni «Licencia de uso»: no volver a ponerlos; el titular solo en la pantalla) publicada dentro de la v0.25.0.
v0.25.0 (número de expediente = DNI; sin DNI, GM-…; los existentes se convierten al iniciar con auditoría) se publicó el 4-nov-2026 tras su «ya» como v0.25.0-31 (incluye v0.24.1; repositorio aún público). Lo siguiente, en `desarrollo` hasta su «ya».
v0.26.0 (plantillas de hallazgos por patología del Word «Endo NIC»: menú «📋 Plantillas» por segmento; migración 0020 `endo_templates`; página Endoscopia → Plantillas por patología; incluye «Metaplasia intestinal gástrica» redactada por Claude, a revisar por él) se publicó el 4-nov-2026 tras su «ya» como v0.26.0-32 (repositorio aún público). Lo siguiente, en `desarrollo` hasta su «ya».
v0.27.0 (hasta 3 logos —logo, logo2, logo3—, grandes en el informe; migración 0021) publicada el 5-nov-2026 por su «hazlo ya». Lo siguiente, en `desarrollo` hasta su «ya».
Para activar una PC: él copia el código de equipo y corre el workflow (o lo hace Claude si tiene la llave en la sesión). La llave privada NUNCA va al código.
La CI tiene trabajos windows, mac (matriz) y publicar (solo en main; sube el .exe y los .zip de Mac que salieron bien). `macos-latest` se quedó sin máquinas: usar `macos-14`.
**Mac SOLO CUANDO ÉL LO PIDA (3-nov-2026):** primero pidió Mac una vez y luego dijo «no hagas para Mac en este momento, solo Windows».
El trabajo mac corre solo si el último commit que llega a main tiene «[mac]» en el mensaje (o workflow_dispatch con mac=true). Hoy NO
se publica para Mac: no poner «[mac]» en ningún commit hasta que él lo pida. La construcción para Mac ya está probada y lista para entonces.
Los cambios solo de `*.md` o `docs/` en `main` no disparan la construcción.

## Flujo de trabajo que funcionó
1. Crear tareas, programar y escribir pruebas pytest para cada función nueva. Ejemplo: un servidor SMTP falso en localhost; nunca simular un éxito.
2. Correr `python3 -m pytest -q` (245 pruebas en v0.27.0).
3. Revisar en el navegador con Playwright y guardar capturas en `evidencia/capturas/`.
4. Correr la prueba del exe en local: `build/smoke_exe.py` con un script que ejecute `python3 gastromed_exe.py`. Si waitress no está instalado, usar un sustituto con `werkzeug.make_server` en `PYTHONPATH`.
5. Actualizar `docs/PROGRESO.md` y `docs/MATRIZ.md` (y `INSTALACION_WINDOWS.md` si cambia el uso). Copiarlos al Proyecto con `project_write`.
6. Commit con atribución, `git push`. GitHub Actions (`.github/workflows/construir-exe.yml`, windows-latest) hace lo siguiente: pruebas, PyInstaller (`build/GastroMedPro.spec`), prueba de humo del exe y Release `vX.Y.Z-N`.
7. Esperar la CI en segundo plano con un ciclo `until` sobre `gh api repos/.../actions/runs?head_sha=...`.
8. Confirmar la publicación con `gh api repos/marioslainez24/gastromed-pro/releases/latest`.

## Trampas conocidas
- **Red del entorno:**
  - PyPI y npm bloqueados: usar los paquetes ya instalados.
  - Los registros y artefactos de Actions no se pueden descargar y GraphQL está bloqueado. Usar REST: `/actions/runs/<id>/jobs` para el estado de cada paso y `/check-runs/<job>/annotations` para el texto del error. `smoke_exe.py` imprime `::error title=Prueba del ejecutable::` con el traceback.
- **Consola de Windows (cp1252):** no imprimir «→» ni emojis en la salida del exe ni de las pruebas, o forzar UTF-8 con `reconfigure`.
- **Cabeceras de seguridad:**
  - La CSP `form-action 'self'` bloquea los formularios que redirigen a otros dominios. Ejemplo: la página de recordatorios de WhatsApp define su propia CSP con `https://wa.me`.
  - `Permissions-Policy` se aplica con `setdefault`. Las pantallas que necesitan cámara o micrófono ponen su propia cabecera (ver `with_dictation`).
- **Plantillas Jinja:** `str.replace("{% endblock %}", …)` sin límite modifica el PRIMER bloque (el de `title`). Insertar antes del último `{% endblock %}` con `rindex`.
- **Diseño y servidor:**
  - `label`/`.field` son grid: un botón dentro necesita `justify-self: start`.
  - Matar el servidor local con `fuser -k 8000/tcp`, no con `pkill -f`.
- **Pruebas:**
  - `env["org"]` es un dict; usar `env["org"]["org_id"]`.
  - `agenda.new` redirige al día, no a la cita.
  - Los pacientes con el mismo DNI dan 409.
  - ReportLab reutiliza imágenes idénticas: usar imágenes distintas en las pruebas.
- **Caché del navegador:** nunca referenciar `/static/...?v=`; usar `{{ asset('js/archivo.js') }}` (dirección con versión). El service worker
  pide primero a la red. Probar las actualizaciones con un perfil de navegador persistente que ya tenga la versión anterior.
- **Pendientes de verificar en el sitio:**
  - Fórmula de Lille (diferencia de bilirrubina) y regla de diálisis en MELD 3.0.
  - Capturadora de video real.
  - Envío real con Gmail.
