# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

datas_meta = []
for pkg in [
    'fastapi', 'uvicorn', 'starlette', 'ollama', 'pydantic',
    'anyio', 'httpx', 'numpy',
]:
    try:
        datas_meta += copy_metadata(pkg)
    except Exception:
        pass

a = Analysis(
    ['launch_fastapi.py'],
    pathex=[],
    binaries=[],
    datas=datas_meta + [
        # バックエンドモジュール
        ('main.py', '.'),
        ('utils.py', '.'),
        ('answer_assist.py', '.'),
        ('industry_engine.py', '.'),
        ('mock_interview_engine.py', '.'),
        ('persona_engine.py', '.'),
        ('api', 'api'),
        ('db', 'db'),
        ('llm', 'llm'),
        ('prompts', 'prompts'),
        ('rag', 'rag'),
        ('services', 'services'),
        ('shared', 'shared'),
        # フロントエンド（React ビルド済み）
        ('../frontend/dist', 'frontend_dist'),
        # アイコン（インストーラーのショートカット用）
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
        'main', 'utils',
        'answer_assist', 'industry_engine', 'mock_interview_engine', 'persona_engine',
        'api', 'api.routes',
        'api.routes.health', 'api.routes.mock_interview',
        'api.routes.sessions', 'api.routes.knowledge_base', 'api.routes.settings',
        'db', 'db.database', 'db.knowledge_base_repository',
        'db.personality_repository', 'db.session_repository', 'db.settings_repository',
        'llm', 'llm.base', 'llm.ollama_provider',
        'prompts', 'prompts.answer_assist', 'prompts.guards',
        'prompts.interviewer', 'prompts.mock_interview',
        'rag', 'rag.core', 'rag.extraction', 'rag.persistence',
        'services', 'services.interview_service',
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
    name='launch_fastapi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(SPECPATH, 'app.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='launch_fastapi',
)
