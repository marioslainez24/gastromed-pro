# GastroMed Pro

Sistema de gestión clínica para Gastroenterología, Hepatología y Endoscopia — Dr. Mario Lainez.

> **Estado: en desarrollo (v0.1.0). No apto todavía para pacientes reales.** Use solo datos ficticios.

## Documentos
- `docs/ARQUITECTURA.md` — tecnologías, modelo de datos, permisos, costos.
- `docs/MATRIZ.md` — todos los requisitos con su estado (probado / pendiente / proveedor externo).
- `docs/PROGRESO.md` — qué está hecho, cómo se comprobó y qué sigue. **Leer primero al retomar.**
- `docs/INSTALACION_WINDOWS.md` — probar la demostración en Windows.
- `evidencia/` — capturas en navegador real y PDF de ejemplo.

## Inicio rápido (desarrollo)
```
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_demo.py
python run.py                                    # http://127.0.0.1:8000
python -m pytest -q                              # pruebas
```

## Estructura
```
app/            código de la aplicación (vistas, seguridad, PDF, plantillas, estáticos)
migrations/     esquema SQL versionado
scripts/        datos de demostración y administración de usuarios
tests/          pruebas automáticas
docs/           documentación
```
