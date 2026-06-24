@echo off
echo ============================
echo  Git Workflow
echo ============================
echo 1. Push only (no tag)
echo 2. Release (tag + GitHub Actions)
echo ============================
set /p MODE="Select (1 or 2): "
if "%MODE%"=="1" goto NORMAL
if "%MODE%"=="2" goto RELEASE
echo Invalid selection.
pause
exit /b

:NORMAL
echo --- Push only mode ---
git add .
set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=update
git commit -m "%MSG%"
git push origin main
if errorlevel 1 (
    echo [ERROR] push failed.
    pause
    exit /b
)
echo --- Done (main updated) ---
pause
exit /b

:RELEASE
echo --- Release mode ---
set /p VERSION="Version (e.g. v1.0.0): "
if "%VERSION%"=="" (
    echo [ERROR] Version is empty.
    pause
    exit /b
)
if not "%VERSION:~0,1%"=="v" set VERSION=v%VERSION%
git add .
set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=release %VERSION%
git commit -m "%MSG%"
git push origin main
if errorlevel 1 (
    echo [ERROR] push failed. Tag will not be created.
    pause
    exit /b
)
git tag %VERSION% 2>nul
if errorlevel 1 (
    echo [ERROR] Tag %VERSION% already exists.
    pause
    exit /b
)
git push origin %VERSION%
if errorlevel 1 (
    echo [ERROR] Tag push failed.
    pause
    exit /b
)
echo --- GitHub Actions triggered ---
echo --- Installer will be built automatically ---
pause
exit /b
