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
