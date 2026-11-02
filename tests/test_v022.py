"""v0.22.0: versión para Mac (carpeta de Google Drive de Mac para los respaldos y lanzador)."""
import sys

from app import backup


def test_drive_de_mac_se_detecta(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    mi = tmp_path / "Library" / "CloudStorage" / "GoogleDrive-doctor@example.com" / "Mi unidad"
    mi.mkdir(parents=True)
    (tmp_path / "Library" / "CloudStorage" / "OneDrive-Personal").mkdir()     # no es Google Drive: se ignora
    assert str(mi) in backup.drive_candidates()


def test_sin_drive_no_inventa_carpetas(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert [p for p in backup.drive_candidates() if p.startswith(str(tmp_path))] == []


def test_lanzador_usa_carpeta_del_usuario_fuera_de_windows(tmp_path, monkeypatch):
    import gastromed_exe
    monkeypatch.delenv("GASTROMED_ROOT", raising=False)
    if sys.platform != "win32":
        assert str(gastromed_exe.data_root()).endswith("GastroMed")


def test_datos_copiados_de_windows_se_adaptan_sin_tocar_claves(tmp_path):
    import gastromed_exe as G
    datos, resp = tmp_path / "datos", tmp_path / "respaldos"
    datos.mkdir()
    env = datos / "gastromed.env"
    env.write_text("GASTROMED_ENV=consultorio\nGASTROMED_DATA_KEY=abc=\nGASTROMED_DATABASE_PATH=C:\\GastroMed\\datos\\gastromed.sqlite3\n"
                   "GASTROMED_FILES_DIR=C:\\GastroMed\\datos\\archivos\nGASTROMED_BACKUP_DIR=C:\\GastroMed\\respaldos\n"
                   "GASTROMED_BACKUP_COPY_DIR=G:\\Mi unidad\\GastroMed\n", encoding="utf-8")
    if sys.platform == "win32":
        assert G.adapt_paths(env, datos, resp) is False
        return
    assert G.adapt_paths(env, datos, resp) is True
    txt = env.read_text(encoding="utf-8")
    assert "GASTROMED_DATA_KEY=abc=" in txt and "C:\\" not in txt and "G:\\" not in txt
    assert f"GASTROMED_DATABASE_PATH={datos / 'gastromed.sqlite3'}" in txt and "GASTROMED_BACKUP_COPY_DIR=\n" in txt
    assert G.adapt_paths(env, datos, resp) is False          # la segunda vez ya no hay nada que corregir


def test_datos_propios_no_se_tocan(tmp_path):
    import gastromed_exe as G
    datos = tmp_path / "datos"
    datos.mkdir()
    env = datos / "gastromed.env"
    env.write_text(f"GASTROMED_DATABASE_PATH={datos / 'gastromed.sqlite3'}\n", encoding="utf-8")
    assert G.adapt_paths(env, datos, tmp_path / "respaldos") is False
