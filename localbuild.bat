@echo off
chcp 65001 > nul
echo ================================
echo  フルビルド開始（PyInstaller + Inno Setup）
echo ================================
:: ===============================
:: 0. 前提チェック
:: ===============================
if not exist launch.spec (
    echo [ERROR] launch.spec が見つかりません
    pause
    exit /b
)
if not exist InterviewApp.iss (
    echo [ERROR] Inno Setup (.iss) が見つかりません
    pause
    exit /b
)
:: ===============================
:: 1. クリーンアップ
:: ===============================
echo [1/5] 古いビルド削除中...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
:: ===============================
:: 2. PyInstaller実行
:: ===============================
echo [2/5] PyInstallerビルド中...
pyinstaller launch.spec
if errorlevel 1 (
    echo ================================
    echo  PyInstaller失敗
    echo ================================
    pause
    exit /b
)
if not exist dist\launch.exe (
    echo [ERROR] launch.exe が作成されていません
    pause
    exit /b
)
:: ===============================
:: 3. Inno Setup実行
:: ===============================
echo [3/5] インストーラー作成中...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo [ERROR] Inno Setup が見つかりません
    echo 以下のパスを確認してください：
    echo   C:\Program Files (x86)\Inno Setup 6\ISCC.exe
    echo   C:\Program Files\Inno Setup 6\ISCC.exe
    pause
    exit /b
)
%ISCC% InterviewApp.iss
if errorlevel 1 (
    echo ================================
    echo  Inno Setup失敗
    echo ================================
    pause
    exit /b
)
:: ===============================
:: 4. 成果物確認
:: ===============================
echo [4/5] 成果物確認中...
if exist output\InterviewAppSetup.exe (
    echo ================================
    echo  完全成功！
    echo ================================
    echo  output\InterviewAppSetup.exe
    echo ================================
) else (
    echo [ERROR] setup.exe が見つかりません
)
:: ===============================
:: 5. 完了
:: ===============================
echo [5/5] 完了
pause
