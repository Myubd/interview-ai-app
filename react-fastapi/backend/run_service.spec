# -*- mode: python ; coding: utf-8 -*-
#
# launch_fastapi.spec(単体exe配布・方式B)との違い:
#   - エントリポイントが run_service.py(Ollama管理・ブラウザ起動をしない
#     軽量版。gateway統合exeではlaunch_gateway.pyがOllamaを1回だけ管理する)
#   - フロントエンド(../frontend/dist)は同梱しない。gateway統合exeでは
#     LifeSupportOS.exe(gateway側)に ../frontend/dist-gateway を同梱し、
#     gatewayが /career で配信するため、ここでは不要。
#   - service_auth.py を追加(launch_fastapi.spec は2026-08のStep1追加時に
#     更新し忘れていたバグがあったため、ここでは最初から入れておく)。
#
# それ以外(local_ai_coreの同梱方法・hiddenimports)は、実際に起きた
# ModuleNotFoundError等を踏まえて作られた launch_fastapi.spec の内容を
# そのまま踏襲する。
import os
from PyInstaller.utils.hooks import copy_metadata

datas_meta = []
for pkg in [
    'fastapi', 'uvicorn', 'starlette', 'ollama', 'pydantic',
    'anyio', 'httpx', 'numpy', 'cryptography',
]:
    try:
        datas_meta += copy_metadata(pkg)
    except Exception:
        pass

a = Analysis(
    ['run_service.py'],
    pathex=[],
    binaries=[],
    datas=datas_meta + [
        ('main.py', '.'),
        ('utils.py', '.'),
        ('version_info.py', '.'),
        ('version.txt', '.'),
        ('service_auth.py', '.'),
        ('api', 'api'),
        ('db', 'db'),
        ('llm', 'llm'),
        ('rag', 'rag'),
        ('services', 'services'),
        ('shared', 'shared'),
        ('plugin_manifest.json', '.'),
        ('core_sync', 'core_sync'),
        ('local_ai_core/local_ai_core', 'local_ai_core'),
        ('app.ico', '.'),
    ],
    hiddenimports=[
        'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan', 'uvicorn.lifespan.on',
        'fastapi', 'fastapi.staticfiles', 'fastapi.responses',
        'starlette.staticfiles', 'starlette.responses',
        'anyio', 'anyio._backends._asyncio',
        'ollama',
        'main', 'utils', 'service_auth',
        'api', 'api.routes',
        'api.routes.health', 'api.routes.mock_interview',
        'api.routes.sessions', 'api.routes.knowledge_base', 'api.routes.settings',
        'db', 'db.database', 'db.knowledge_base_repository',
        'db.personality_repository', 'db.session_repository', 'db.settings_repository',
        'llm', 'llm.base', 'llm.ollama_provider',
        'rag', 'rag.core', 'rag.extraction', 'rag.persistence',
        'services', 'services.interview_service', 'services.career_advisor_service',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='interview_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    # NOTE: launch_fastapi.spec と同じ理由でconsole=Falseにしていない。
    # run_service.py の hide_console_window() が起動直後に隠すため、
    # 見た目上はconsole=Falseと同じ体験になる。
    icon=os.path.join(SPECPATH, 'app.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='interview_backend',
)
