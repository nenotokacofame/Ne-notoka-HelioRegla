# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


BASE = Path(SPECPATH).resolve()
APP = BASE / "app"

datos = [
    (str(BASE / "assets"), "assets"),
    (str(BASE / "docs"), "docs"),
    (str(BASE / "licencias_terceros"), "licencias_terceros"),
    (str(BASE / "LICENSE"), "."),
    (str(BASE / "THIRD_PARTY_NOTICES.txt"), "."),
    (str(BASE / "README.md"), "."),
    (str(BASE / "CHANGELOG.md"), "."),
]

a = Analysis(
    [str(APP / "main.py")],
    pathex=[str(APP)],
    binaries=[],
    datas=datos,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ne-notoka HelioRegla",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / "assets" / "icono_ne_notoka.ico"),
    version=str(BASE / "instalador" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Ne-notoka HelioRegla",
)
