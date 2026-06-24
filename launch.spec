# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata, collect_all

# StreamlitのJS/CSS静的ファイルを全収集
st_datas, st_binaries, st_hiddenimports = collect_all('streamlit')

# importlib.metadata が必要なパッケージのメタデータを収集
datas_meta = []
for pkg in [
    'streamlit',
    'ollama',
    'altair',
    'click',
    'packaging',
    'pillow',
    'protobuf',
    'pyarrow',
    'pydeck',
    'requests',
    'rich',
    'toml',
    'tornado',
    'tzlocal',
    'watchdog',
]:
    try:
        datas_meta += copy_metadata(pkg)
    except Exception:
        pass

a = Analysis(
    ['launch.py'],
    pathex=[],
    binaries=st_binaries,
    datas=st_datas + datas_meta + [
        ('version.txt', '.'),
        # ルートのPythonファイル
        ('app.py', '.'),
        ('rag.py', '.'),
        ('interview_engine.py', '.'),
        ('mock_interview_engine.py', '.'),
        ('session_io.py', '.'),
        ('favorites.py', '.'),
        ('utils.py', '.'),
        ('pr_generation.py', '.'),
        ('question_prediction.py', '.'),
        ('personality_assessment.py', '.'),
        ('persona_engine.py', '.'),
        ('answer_assist.py', '.'),
        ('company_matrix.py', '.'),
        ('industry_engine.py', '.'),
        ('summary_generation.py', '.'),
        # パッケージ・フォルダ
        ('components', 'components'),
        ('page_modules', 'page_modules'),
        ('prompts', 'prompts'),
        ('db', 'db'),
        ('state', 'state'),
        ('.streamlit', '.streamlit'),
    ],
    hiddenimports=st_hiddenimports + [
        # ルートモジュール
        'streamlit',
        'ollama',
        'rag',
        'interview_engine',
        'mock_interview_engine',
        'session_io',
        'favorites',
        'utils',
        'pr_generation',
        'question_prediction',
        'personality_assessment',
        'persona_engine',
        'answer_assist',
        'company_matrix',
        'industry_engine',
        'summary_generation',
        # componentsパッケージ
        'components',
        'components.sidebar',
        # page_modulesパッケージ
        'page_modules',
        'page_modules.career_page',
        'page_modules.company_matrix_page',
        'page_modules.history_page',
        'page_modules.personality_page',
        'page_modules.predict_questions_page',
        'page_modules.interview',
        'page_modules.interview.company_pr_section',
        'page_modules.interview.helpers',
        'page_modules.interview.interview_ui',
        'page_modules.interview.page',
        'page_modules.interview.predicted_questions_section',
        'page_modules.interview.pr_evaluation_section',
        'page_modules.interview.pr_generation_section',
        'page_modules.interview.summary_section',
        'page_modules.mock_interview',
        'page_modules.mock_interview.evaluation_section',
        'page_modules.mock_interview.helpers',
        'page_modules.mock_interview.interview_chat',
        'page_modules.mock_interview.interview_flow',
        'page_modules.mock_interview.page',
        'page_modules.mock_interview.persona_selector',
        # promptsパッケージ
        'prompts',
        'prompts.answer_assist',
        'prompts.guards',
        'prompts.interviewer',
        'prompts.mock_interview',
        # dbパッケージ
        'db',
        'db.database',
        'db.knowledge_base_repository',
        'db.personality_repository',
        'db.session_repository',
        'db.settings_repository',
        # stateパッケージ
        'state',
        'state.definitions',
        'state.initializer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tests',
    ],
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
    name='launch',
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
