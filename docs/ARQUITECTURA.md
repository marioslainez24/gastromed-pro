# GastroMed Pro — Arquitectura

Versión del documento: 0.1 · 30 de octubre de 2026

## 1. Decisión principal

**Aplicación web única, renderizada en servidor, con base de datos relacional y un solo servidor en la nube detrás de HTTPS.**

| Capa | Tecnología | Versión verificada | Motivo |
|---|---|---|---|
| Lenguaje | Python | 3.13 | Estable, legible, amplio soporte a largo plazo |
| Web | Flask + Jinja2 + Werkzeug | 3.1.3 / 3.1.6 / 3.1.9 | Maduro, documentado, pocas piezas que mantener |
| Base de datos | SQLite en modo WAL, tablas `STRICT` | 3.53 | Relacional, transaccional, sin servidor aparte; ideal para 1 clínica |
| PDF | ReportLab | 5.0.1 | Generación precisa de carta/A4 sin navegador |
| Frontend | HTML + CSS + JavaScript propio, sin dependencias | — | Carga rápida en celular, sin cadena de compilación |
| Servidor de producción | Waitress (WSGI) + proxy HTTPS (Caddy) | pendiente de instalar | Funciona en Linux y Windows |

### Por qué esta elección y no otra

- **Una clínica pequeña con un médico** necesita algo que una sola persona pueda mantener durante años. Menos piezas = menos fallos y menos costo.
- **SQLite** soporta sin problema el volumen de una clínica (miles de pacientes, decenas de usuarios simultáneos). Las escrituras se serializan, lo que *simplifica* la prevención de reservas dobles. Los respaldos son un único archivo más la carpeta de adjuntos.
- **Ruta de crecimiento:** si en el futuro hay muchas sucursales con alto volumen, el esquema (SQL estándar, identificadores UUID, fechas UTC) se migra a PostgreSQL. Esa migración está anotada como tarea futura, no es necesaria hoy.
- **Nota de transparencia:** el entorno donde se construyó esta etapa no permite descargar paquetes de Node.js ni de PyPI. Se eligió una pila cuyas piezas estaban disponibles **y** que es adecuada por sí misma. No se escribió código que no se pudiera probar.

## 2. Cómo se usa desde PC y celular

```
 PC Windows (navegador) ─┐
                         ├── HTTPS ──► Servidor en la nube (Linux) ──► Base de datos + archivos privados
 Celular (navegador/PWA)─┘                     │
                                               └──► Respaldos cifrados en otro proveedor/región
```

- No se instala nada en la PC ni en el celular: se abre una dirección web y, si se desea, se "instala" como aplicación (PWA).
- La información vive solo en el servidor. **No se guardan expedientes en el dispositivo** (el service worker solo guarda estilos e íconos).

## 3. Modelo de datos (Fase 1)

| Tabla | Contenido | Reglas clave |
|---|---|---|
| `organizations`, `sites` | Clínica y sedes | Todo registro lleva `org_id`; las consultas siempre filtran por él |
| `roles`, `role_permissions` | Roles configurables y permisos por acción | Mínimo privilegio por defecto |
| `users`, `user_sites` | Usuarios y sedes asignadas | No se borran: se desactivan (trigger) |
| `sessions`, `login_attempts` | Sesiones de servidor y control de intentos | Solo se guarda el hash del token |
| `clinic_settings` | Encabezado, región, moneda, papel, duraciones | Control de versión |
| `patients`, `patient_allergies` | Expediente administrativo + cabecera clínica | ID interno UUID + número legible GM-000001; documento opcional y único |
| `appointments`, `appointment_events` | Citas e historial | Trigger impide cruces; historial inmutable |
| `clinical_notes`, `note_addenda` | Notas y adendas | Nota finalizada inmutable (trigger) + huella SHA-256 |
| `prescriptions`, `prescription_items` | Recetas | Inmutables; solo se pueden anular con motivo |
| `audit_log` | Bitácora | Solo inserción (triggers) + encadenada por hash |

Todas las fechas se guardan en UTC y se muestran en la zona horaria configurada (America/Tegucigalpa por defecto).

## 4. Permisos iniciales

| Permiso | Propietario | Médico | Enfermería | Recepción | Caja |
|---|:-:|:-:|:-:|:-:|:-:|
| Ver datos administrativos | ✔ | ✔ | ✔ | ✔ | ✔ |
| Registrar/editar datos administrativos | ✔ | ✔ | — | ✔ | — |
| Ver información clínica | ✔ | ✔ | ✔ | — | — |
| Registrar información clínica y notas | ✔ | ✔ | — | — | — |
| Finalizar notas | ✔ | ✔ | — | — | — |
| Emitir / anular recetas | ✔ | ✔ | — | — | — |
| Ver agenda | ✔ | ✔ | ✔ | ✔ | ✔ |
| Gestionar citas | ✔ | ✔ | — | ✔ | — |
| Ajustes, usuarios, auditoría | ✔ | — | — | — | — |

La verificación ocurre **siempre en el servidor**, en cada solicitud. Ocultar un botón no es la protección; el servidor responde 403.

## 5. Costos previsibles (sin precios inventados)

| Concepto | Opción propuesta | Costo |
|---|---|---|
| Servidor (1 vCPU, 1–2 GB RAM, disco cifrado) | Un VPS de proveedor reconocido o un servicio de contenedores | **Pendiente de verificar** con el proveedor elegido; suele ser un cargo mensual fijo bajo |
| Dominio | Registrador de dominios | **Pendiente de verificar** (anual) |
| Certificado HTTPS | Let's Encrypt vía Caddy | Sin costo de licencia (servicio gratuito actual, puede cambiar) |
| Respaldos externos | Almacenamiento de objetos en otro proveedor | **Pendiente de verificar** (por GB/mes) |
| Correo transaccional | Proveedor de correo (Fase 5) | **Pendiente de verificar** |
| WhatsApp | API oficial de WhatsApp Business vía proveedor autorizado (Fase 5) | **Pendiente de verificar**; cobran por conversación/plantilla |
| IA opcional | Proveedor con acuerdo de tratamiento de datos (Fase 5) | **Pendiente de verificar**; por uso |
| Vademécum con licencia | Proveedor farmacológico (pendiente de identificar) | **Pendiente de verificar** |

Antes de contratar cualquier servicio se pedirá su aprobación.

## 6. Integraciones previstas

Ninguna integración externa está activa. Cada una se documentará con: proveedor, función, requisitos, costo verificado, datos compartidos, configuración, prueba de aceptación y comportamiento ante fallo. Ver `MATRIZ.md` (sección Integraciones).
