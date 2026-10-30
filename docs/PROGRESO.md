# Bitácora de progreso — GastroMed Pro

Este archivo permite continuar el trabajo en futuras conversaciones. Léalo primero.

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
