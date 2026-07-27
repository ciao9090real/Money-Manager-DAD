# -*- mode: python ; coding: utf-8 -*-

fido2_hiddenimports = [
    'fido2.client',
    'fido2.client.windows',
    'fido2.server',
    'fido2.webauthn',
]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/assets/fonts', 'app/assets/fonts')],
    hiddenimports=fido2_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MoneyManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
