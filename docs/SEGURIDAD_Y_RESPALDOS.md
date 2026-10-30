# Seguridad, claves y respaldos

## Las tres claves del sistema
| Variable | Para qué sirve | Si se pierde |
|---|---|---|
| `GASTROMED_SECRET_KEY` | Firma interna de la aplicación | Se generan nuevas sesiones; no se pierden datos |
| `GASTROMED_DATA_KEY` | Cifra los adjuntos y los secretos de verificación en dos pasos | **Los adjuntos quedan ilegibles para siempre** |
| `GASTROMED_BACKUP_KEY` | Cifra los respaldos | **Los respaldos no se pueden abrir** |

Generar una clave de datos o de respaldo:
```
python scripts/respaldo.py generar-clave
```
Guarde `GASTROMED_DATA_KEY` y `GASTROMED_BACKUP_KEY` **fuera del servidor**: en un gestor de contraseñas y una copia impresa en un lugar seguro (por ejemplo, caja fuerte). Nunca en el mismo lugar que los respaldos.

## Qué protege el sistema hoy
- Contraseñas con scrypt; bloqueo tras intentos fallidos; verificación en dos pasos (TOTP) opcional u obligatoria por política.
- Sesiones en servidor, expiración por inactividad, cierre de otras sesiones al cambiar contraseña o desactivar usuario.
- Permisos verificados en el servidor en cada solicitud; aislamiento entre clínicas.
- Adjuntos validados por su contenido (PDF/JPG/PNG/HEIC), PDF con scripts rechazados, máximo 20 MB, **cifrados en disco**, servidos solo a usuarios con permiso clínico, sin enlaces públicos.
- Notas finalizadas, recetas, historial de citas, archivos y auditoría protegidos contra cambios y borrado en la propia base de datos.
- Bitácora de auditoría encadenada por hash.

## Pendiente antes de usar datos reales
- Cifrado del disco del servidor (opción del proveedor) — la base de datos SQLite no se cifra a nivel de aplicación.
- Antivirus sobre adjuntos (p. ej., ClamAV en el servidor): **no disponible** en el entorno de desarrollo. Hoy hay validación por contenido y rechazo de PDF activos, que no equivale a un antivirus.
- Respaldos programados (diarios) y copia en otro proveedor; prueba de restauración mensual documentada.
- Revisión legal en Honduras sobre almacenamiento de datos clínicos fuera del país.

## Rutina de respaldo
```
python scripts/respaldo.py crear respaldos          # crea respaldos/gastromed-AAAAMMDD-HHMMSS.gmbak (cifrado)
python scripts/respaldo.py verificar respaldos/ARCHIVO.gmbak   # restaura en una carpeta temporal y comprueba todo
```
La verificación comprueba: clave correcta, que el archivo no fue alterado, huellas SHA-256 de cada pieza, integridad de la base, claves foráneas, conteos por tabla y que cada adjunto se descifre con su huella original.

## Restaurar
```
python scripts/respaldo.py restaurar respaldos/ARCHIVO.gmbak C:\GastroMed\restaurado
```
Nunca sobrescribe datos existentes: restaura en una carpeta nueva y luego se apunta la aplicación a ella.

## Exportación completa
```
python scripts/respaldo.py exportar exportacion.zip
```
Genera CSV por tabla y los adjuntos descifrados por número de expediente. **El archivo no está cifrado**: guárdelo protegido.

## Limitación conocida
El respaldo se arma en memoria. Es adecuado mientras los adjuntos sumen unos pocos GB; al crecer, se cambiará a respaldo por partes.
