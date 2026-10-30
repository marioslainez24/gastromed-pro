# Bitácora de progreso — GastroMed Pro

Este archivo permite continuar el trabajo en futuras conversaciones. Léalo primero.

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
