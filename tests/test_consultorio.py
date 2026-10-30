"""Modo consultorio (servidor privado en la PC): claves obligatorias, configuración inicial y respaldo automático."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_consultorio_exige_claves(tmp_path, monkeypatch):
    from app.config import Config
    from app.crypto import load_data_key
    monkeypatch.delenv("GASTROMED_DATA_KEY", raising=False)
    with pytest.raises(RuntimeError):
        Config(ENV="consultorio", SECRET_KEY="corta", DATABASE_PATH=str(tmp_path / "x.db"))
    cfg = Config(ENV="consultorio", SECRET_KEY="k" * 40, DATABASE_PATH=str(tmp_path / "x.db"))
    with pytest.raises(RuntimeError):
        load_data_key(cfg)  # nunca se genera una clave silenciosamente con datos reales
    assert not (tmp_path / "clave_datos.key").exists()


def test_instalacion_respaldo_y_diagnostico_de_punta_a_punta(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GASTROMED_")}
    env.update(GM_INSTALL_CLINIC="Consultorio de prueba", GM_INSTALL_NAME="Dr. Prueba", GM_INSTALL_EMAIL="dr@prueba.local",
               GM_INSTALL_PASSWORD="Instalacion-Prueba-2026", GM_INSTALL_COPYDIR=str(tmp_path / "usb"))
    (tmp_path / "usb").mkdir()
    (tmp_path / "escritorio").mkdir()
    args = ["--datos", str(tmp_path / "datos"), "--respaldos", str(tmp_path / "respaldos"), "--escritorio", str(tmp_path / "escritorio")]
    r = subprocess.run([sys.executable, "windows/configurar.py", *args], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    env_file = tmp_path / "datos" / "gastromed.env"
    first = env_file.read_text(encoding="utf-8")
    assert "GASTROMED_ENV=consultorio" in first and "GASTROMED_DATA_KEY=" in first
    assert any(p.name.startswith("GastroMed - CLAVES") for p in (tmp_path / "escritorio").iterdir())
    # Re-ejecutar (actualización) no cambia claves ni crea usuarios nuevos
    r = subprocess.run([sys.executable, "windows/configurar.py", *args], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0 and env_file.read_text(encoding="utf-8") == first
    env2 = {k: v for k, v in env.items() if not k.startswith("GM_INSTALL_")}
    env2["GASTROMED_ENV_FILE"] = str(env_file)
    for _ in range(3):
        r = subprocess.run([sys.executable, "scripts/respaldo.py", "automatico"], cwd=ROOT, env=env2, capture_output=True, text=True)
        assert r.returncode == 0 and "creado y verificado" in r.stdout, r.stdout + r.stderr
    assert len(list((tmp_path / "usb").glob("*.gmbak"))) >= 1
    r = subprocess.run([sys.executable, "scripts/diagnostico.py"], cwd=ROOT, env=env2, capture_output=True, text=True)
    assert r.returncode == 0 and "TODO CORRECTO" in r.stdout, r.stdout


def test_retencion_de_respaldos(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    from respaldo import prune
    for i in range(35):
        (tmp_path / f"gastromed-202610{i:02d}-000000.gmbak").write_bytes(b"x")
    (tmp_path / "otro-archivo.txt").write_text("no tocar")
    assert prune(tmp_path, 30) == 5
    left = sorted(p.name for p in tmp_path.glob("*.gmbak"))
    assert len(left) == 30 and left[0] == "gastromed-20261005-000000.gmbak"
    assert (tmp_path / "otro-archivo.txt").exists()


def test_lanzadores_windows_bien_formados():
    for f in [ROOT / "INSTALAR.bat", *(ROOT / "windows").glob("*.bat")]:
        raw = f.read_bytes()
        assert raw.isascii(), f.name
        assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), f"{f.name}: debe usar CRLF"
    ps = (ROOT / "windows" / "instalar.ps1").read_bytes()
    assert ps.startswith(b"\xef\xbb\xbf"), "instalar.ps1 necesita BOM UTF-8 para PowerShell 5.1"
    assert b"requirements-dev.txt" in ps and b"tzdata" in (ROOT / "requirements.txt").read_bytes()
