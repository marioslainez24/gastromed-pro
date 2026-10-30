# -*- mode: python ; coding: utf-8 -*-
# Construcción de GastroMedPro.exe (un solo archivo, sin instalar Python). Se ejecuta en Windows:
#   pyinstaller build/GastroMedPro.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("../app/templates", "app/templates"), ("../app/static", "app/static"), ("../migrations", "migrations")]
binaries, hiddenimports = [], []
for pkg in ("reportlab", "tzdata"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h
hiddenimports += collect_submodules("app") + collect_submodules("waitress")

a = Analysis(["../gastromed_exe.py"], pathex=[".."], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["tkinter", "pytest", "pypdf"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="GastroMedPro", icon="icon.ico",
          console=True, upx=False, version="version_info.txt")
