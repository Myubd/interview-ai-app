import os
import sys
import streamlit.web.cli as stcli

def main():
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