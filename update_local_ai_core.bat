@echo off
rem Switch the console code page to UTF-8 (see release.bat for why).
chcp 65001 >nul
setlocal enabledelayedexpansion

rem このリポジトリから見た local_ai_core submodule の相対パス
set SUBMODULE_PATH=react-fastapi\backend\local_ai_core

echo.
echo ========================================
echo   Update local_ai_core submodule
echo ========================================
echo.

if not exist "%SUBMODULE_PATH%\.git" (
    echo ERROR: "%SUBMODULE_PATH%" が見つからないか、submoduleとして
    echo        初期化されていません。リポジトリ直下でこのスクリプトを
    echo        実行しているか確認してください。
    pause
    exit /b 1
)

pushd "%SUBMODULE_PATH%"

echo [1/5] Checking for local changes inside local_ai_core...
for /f %%A in ('git status --porcelain ^| find /c /v ""') do set DIRTY_COUNT=%%A
if not "%DIRTY_COUNT%"=="0" (
    echo.
    echo WARNING: local_ai_core 内にコミットされていない変更があります:
    git status --short
    echo.
    echo   このまま進めると、それらの変更は失われる可能性があります。
    echo   ローカルでの変更を保存したい場合は、先にこの中で
    echo   commit ^& push してから、あらためてこのスクリプトを
    echo   実行してください。
    echo.
    set /p FORCE=そのまま最新版で上書きしますか？ (y/n): 
    if /i not "!FORCE!"=="y" ( popd & echo Cancelled. & pause & exit /b 0 )
    git restore .
)

echo [2/5] Fetching latest from origin/main...
git fetch origin main
if errorlevel 1 ( popd & echo Fetch failed. & pause & exit /b 1 )

for /f %%i in ('git rev-parse HEAD') do set BEFORE=%%i
for /f %%i in ('git rev-parse origin/main') do set AFTER=%%i

if "%BEFORE%"=="%AFTER%" (
    echo.
    echo Already up to date. Nothing to update.
    popd
    pause
    exit /b 0
)

echo [3/5] Pulling origin/main...
git pull origin main
if errorlevel 1 ( popd & echo Pull failed. & pause & exit /b 1 )

for /f "tokens=*" %%i in ('git log -1 --format^=%%s') do set LATEST_MSG=%%i

popd

echo.
echo [4/5] local_ai_core is now at:
echo   %AFTER% (%LATEST_MSG%)
echo.

git add "%SUBMODULE_PATH%"
git status --short "%SUBMODULE_PATH%"
echo.

set /p CONFIRM=このバージョンを interview_app 側でコミット・pushしますか？ (y/n): 
if /i not "%CONFIRM%"=="y" (
    git restore --staged "%SUBMODULE_PATH%"
    echo Cancelled ^(submoduleの参照更新はステージから外しました^).
    pause
    exit /b 0
)

echo [5/5] Committing and pushing...
rem release.bat と同じ理由(コミットメッセージに特殊文字が含まれていても
rem cmd.exeのパーサーが壊れないようにするため)、-m ではなく一時ファイル
rem 経由の -F を使う。
set "COMMIT_MSG_FILE=%TEMP%\update_lac_commit_msg_%RANDOM%.txt"
> "%COMMIT_MSG_FILE%" echo(chore: update local_ai_core submodule (%LATEST_MSG%)
git commit -F "%COMMIT_MSG_FILE%"
del "%COMMIT_MSG_FILE%" >nul 2>&1
if errorlevel 1 ( echo Commit failed. & pause & exit /b 1 )

git push origin main
if errorlevel 1 ( echo Push failed. & pause & exit /b 1 )

echo.
echo ========================================
echo   Done. local_ai_core submodule updated.
echo ========================================
echo.
pause
