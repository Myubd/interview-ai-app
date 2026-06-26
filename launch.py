import os
import sys
import glob
import shutil
import socket
import subprocess
import time
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


def _kill_existing_streamlit(port: int = 8501) -> None:
    """起動前に同じポートをLISTENしている既存プロセスを終了する。

    二重起動や前回の異常終了でプロセスが残留している場合に
    "Internal Server Error" が出るのを防ぐ。
    自分自身のPID・PID=0 は誤って終了しないようスキップする。
    """
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
        )
        my_pid = os.getpid()
        killed = False
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid == 0 or pid == my_pid:
                    continue
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                )
                killed = True

        if killed:
            # OSがポートを解放するまで待つ（最大3秒）
            for _ in range(30):
                time.sleep(0.1)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex(("127.0.0.1", port)) != 0:
                        break  # ポートが空いた
    except Exception:
        pass


def main():
    _cleanup_old_meipass()
    _kill_existing_streamlit()

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
