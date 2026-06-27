"""
utils/__init__.py
------------------
後方互換のために、サブモジュールの全公開シンボルを再エクスポートする。

既存コードの `from utils import sanitize_user_input` 等はそのまま動作する。
新規コードでは直接サブモジュールをインポートすることを推奨:
    from utils.sanitizer import sanitize_user_input
    from utils.ollama_client import call_ollama_with_json_retry
    from utils.industry_utils import INDUSTRY_KEYS, normalize_industry_fit
    from utils.interview_helpers import polish_interviewer_japanese, format_theme_history
    from utils.version import APP_VERSION
"""

# sanitizer
from utils.sanitizer import (  # noqa: F401
    MAX_USER_INPUT_LENGTH,
    MAX_LONG_INPUT_LENGTH,
    USER_INPUT_BOUNDARY_NOTE,
    sanitize_user_input,
    wrap_user_content,
)

# ollama_client
from utils.ollama_client import (  # noqa: F401
    _clean_json_raw,
    validate_json_schema,
    call_ollama_with_json_retry,
    call_ollama_with_json_array_retry,
    call_ollama_with_text_retry,
)

# industry_utils
from utils.industry_utils import (  # noqa: F401
    INDUSTRY_KEYS,
    normalize_industry_fit,
)

# interview_helpers
from utils.interview_helpers import (  # noqa: F401
    polish_interviewer_japanese,
    format_theme_history,
)

# version
from utils.version import (  # noqa: F401
    APP_VERSION,
    get_version,
)

# prompts パッケージからの再エクスポート（後方互換）
from prompts.guards import HALLUCINATION_GUARD, REFINE_HALLUCINATION_GUARD  # noqa: F401
from prompts.interviewer import INTERVIEWER_JAPANESE_STYLE  # noqa: F401
