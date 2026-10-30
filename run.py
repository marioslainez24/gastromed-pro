"""Arranque local de GastroMed Pro (servidor de desarrollo).

    python run.py            → http://127.0.0.1:8000

En producción se usa un servidor WSGI (waitress o gunicorn) detrás de HTTPS; ver docs/DESPLIEGUE.md.
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("GASTROMED_HOST", "127.0.0.1")
    port = int(os.environ.get("GASTROMED_PORT", "8000"))
    app.run(host=host, port=port, debug=False, threaded=True)
