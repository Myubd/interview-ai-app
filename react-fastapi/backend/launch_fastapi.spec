# -*- mode: python ; coding: utf-8 -*-
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
    ['launch_fastapi.py'],
    pathex=[],
    binaries=[],
    datas=datas_meta + [
        # バックエンドモジュール
        ('main.py', '.'),
        ('utils.py', '.'),
        ('version_info.py', '.'),
        ('version.txt', '.'),
        ('api', 'api'),
        ('db', 'db'),
        ('llm', 'llm'),
        ('rag', 'rag'),
        ('services', 'services'),
        ('shared', 'shared'),
        # 共通データ基盤(local-ai-core)との連携。
        # core_sync/bootstrap.py が `Path(__file__).resolve().parent.parent /
        # "plugin_manifest.json"` のようにファイルパスで直接読むため、
        # PyInstallerの自動import解析だけでは拾われず、明示的にdatasへ
        # 追加する必要がある(拾われないと起動時に例外で即終了する)。
        ('plugin_manifest.json', '.'),
        ('core_sync', 'core_sync'),
        # local_ai_core: submoduleのルート(backend/local_ai_core/、__init__.py
        # を持たないため名前空間パッケージ扱いになる)ではなく、1つ下にある
        # 本物のパッケージ本体(backend/local_ai_core/local_ai_core/、
        # bootstrap.py・llm/・memory/ 等一式が入っている)を
        # "local_ai_core" という名前でそのままコピーする。
        # PyInstallerの依存解析(collect_submodules・pathex等)に頼ると、
        # submoduleルートとの名前衝突により local_ai_core.llm 等の
        # サブモジュールが検出されず、起動直後にModuleNotFoundErrorで
        # 落ちる事故が実際に起きたため、確実な生ファイルコピー方式にしている。
        ('local_ai_core/local_ai_core', 'local_ai_core'),
        # フロントエンド（React ビルド済み）
        ('../frontend/dist', 'frontend_dist'),
        # アイコン（インストーラーのショートカット用）
        ('app.ico', '.'),
        # Ollama は launch_fastapi.py が起動時にダウンロード・インストールするため同梱不要
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
        'api', 'api.routes',
        'api.routes.health', 'api.routes.mock_interview',
        'api.routes.sessions', 'api.routes.knowledge_base', 'api.routes.settings',
        'db', 'db.database', 'db.knowledge_base_repository',
        'db.personality_repository', 'db.session_repository', 'db.settings_repository',
        'llm', 'llm.base', 'llm.ollama_provider',
        'rag', 'rag.core', 'rag.extraction', 'rag.persistence',
        'services', 'services.interview_service', 'services.career_advisor_service',
        # 共通データ基盤(core_sync / local_ai_core)は上のdatasで生ファイルとして
        # 同梱しているため、ここでのhiddenimports指定は不要。
        # ただし local_ai_core.identity.device_identity が使う cryptography の
        # hazmat配下(C拡張ベースのAESGCM実装)は、PyInstallerの自動検出に
        # 乗らないことがある既知の問題のため、明示しておく。
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
