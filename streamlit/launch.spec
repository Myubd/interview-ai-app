# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata, collect_all

st_datas, st_binaries, st_hiddenimports = collect_all('streamlit')

datas_meta = []
for pkg in [
    'streamlit', 'ollama', 'altair', 'click', 'packaging', 'pillow',
    'protobuf', 'pyarrow', 'pydeck', 'requests', 'rich', 'toml',
    'tornado', 'tzlocal', 'watchdog',
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
        ('updater.py', '.'),
        ('app.py', '.'),
        ('interview_engine.py', '.'),
        ('mock_interview_engine.py', '.'),
        ('favorites.py', '.'),
        ('pr_generation.py', '.'),
        ('question_prediction.py', '.'),
        ('personality_assessment.py', '.'),
        ('persona_engine.py', '.'),
        ('answer_assist.py', '.'),
        ('company_matrix.py', '.'),
        ('industry_engine.py', '.'),
        ('summary_generation.py', '.'),
        ('components', 'components'),
        ('db', 'db'),
        ('page_modules', 'page_modules'),
        ('prompts', 'prompts'),
        ('rag', 'rag'),
        ('session_io', 'session_io'),
        ('startup', 'startup'),
        ('state', 'state'),
        ('utils', 'utils'),
        ('.streamlit', '.streamlit'),
    ],
    hiddenimports=st_hiddenimports + [
        'streamlit', 'ollama', 'updater',
        'interview_engine', 'mock_interview_engine', 'favorites',
        'pr_generation', 'question_prediction', 'personality_assessment',
        'persona_engine', 'answer_assist', 'company_matrix',
        'industry_engine', 'summary_generation',
        'components', 'components.sidebar',
        'components.sidebar.navigation', 'components.sidebar.rag_panel',
        'components.sidebar.session_panel', 'components.sidebar.settings',
        'db', 'db.database', 'db.knowledge_base_repository',
        'db.personality_repository', 'db.session_repository', 'db.settings_repository',
        'page_modules', 'page_modules.career_page', 'page_modules.company_matrix_page',
        'page_modules.history_page', 'page_modules.personality_page',
        'page_modules.predict_questions_page',
        'page_modules.interview', 'page_modules.interview.company_pr_section',
        'page_modules.interview.helpers', 'page_modules.interview.interview_ui',
        'page_modules.interview.page', 'page_modules.interview.predicted_questions_section',
        'page_modules.interview.pr_evaluation_section', 'page_modules.interview.pr_generation_section',
        'page_modules.interview.summary_section',
        'page_modules.mock_interview', 'page_modules.mock_interview.evaluation_section',
        'page_modules.mock_interview.helpers', 'page_modules.mock_interview.interview_chat',
        'page_modules.mock_interview.interview_flow', 'page_modules.mock_interview.page',
        'page_modules.mock_interview.persona_selector',
        'prompts', 'prompts.answer_assist', 'prompts.guards',
        'prompts.interviewer', 'prompts.mock_interview',
        'rag', 'rag.core', 'rag.extraction', 'rag.persistence',
        'session_io', 'session_io.db_io', 'session_io.json_io', 'session_io.serializer',
        'startup', 'startup.check_ollama', 'startup.check_update', 'startup.page_config',
        'state', 'state.definitions', 'state.initializer',
        'utils', 'utils.industry_utils', 'utils.interview_helpers',
        'utils.ollama_client', 'utils.sanitizer', 'utils.version',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests'],
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
    icon='app.ico',
)
