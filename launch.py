import os
import sys
import glob
import shutil
import streamlit.web.cli as stcli


def _cleanup_old_meipass() -> None:
    """古いPyInstaller一時フォルダを削除する。"""
    current = getattr(sys, "_MEIPASS", None)
    if current is None:
        return  # 開発環境では何もしない

    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    if not temp_dir:
        return

    for folder in glob.glob(os.path.join(temp_dir, "_MEI*")):
        if os.path.abspath(folder) == os.path.abspath(current):
            continue  # 自分自身はスキップ
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass


def main():
    _cleanup_old_meipass()

    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    app_path = os.path.join(base_path, "app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false"
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
