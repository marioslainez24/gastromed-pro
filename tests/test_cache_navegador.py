"""v0.10.2: el navegador debe recibir siempre el código de la versión instalada (antes servía para siempre la copia de la primera instalación)."""
import re

from app import APP_VERSION
from conftest import login


def test_paginas_cargan_archivos_con_la_version_en_la_direccion(env):
    med = login(env["app"], "propietario")
    html = med.get("/agenda/").get_data(as_text=True)
    for f in ("css/app.css", "js/app.js", "js/theme.js"):
        assert f'/static/v{APP_VERSION}/{f}' in html, f
        r = med.get(f"/static/v{APP_VERSION}/{f}")
        assert r.status_code == 200 and len(r.data) > 100
    assert not re.search(r'/static/(css|js)/[\w.]+\?v=', html)          # ya no se usa ?v= (la caché vieja lo ignoraba)
    # la pantalla de ingreso (sin sesión) también recibe los archivos versionados
    anon = env["app"].test_client()
    assert anon.get(f"/static/v{APP_VERSION}/js/app.js").status_code == 200
    assert anon.get("/static/js/app.js").status_code == 200                 # dirección antigua sigue funcionando


def test_service_worker_lleva_la_version_y_pide_primero_a_la_red(env):
    sw = env["app"].test_client().get("/sw.js")
    src = sw.get_data(as_text=True)
    assert sw.status_code == 200 and sw.headers["Cache-Control"] in ("no-cache", "no-store")
    assert f'const VERSION = "{APP_VERSION}"' in src and "__GM_VERSION__" not in src
    assert "ignoreSearch" not in src and "fetch(e.request).then" in src
