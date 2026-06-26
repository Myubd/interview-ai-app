@echo off
setlocal enabledelayedexpansion
REM 簡易版 - エンコーディング問題対応

echo.
echo ============================
echo  Git Workflow
echo ============================
echo 1. Push only (no tag)
echo 2. Release (manual version)
echo 3. Release (auto version bump)
echo ============================
echo.

set /p MODE="Select (1, 2 or 3): "

if "%MODE%"=="1" goto NORMAL
if "%MODE%"=="2" goto RELEASE_MANUAL
if "%MODE%"=="3" goto RELEASE_AUTO
echo Invalid selection.
pause
exit /b

:NORMAL
echo.
echo --- Push only mode ---
echo.

if exist version.txt (
    for /f "tokens=*" %%i in (version.txt) do (
        echo Current version: %%i
    )
)
echo.

git add .
set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=update
git commit -m "%MSG%"
git push origin main
if errorlevel 1 (
    echo ERROR: push failed.
    pause
    exit /b 1
)

echo.
echo SUCCESS: Done
echo.
pause
exit /b 0

:RELEASE_MANUAL
echo.
echo --- Release mode (manual version) ---
echo.

set /p VERSION="Version (e.g. v3.2.2): "
if "%VERSION%"=="" (
    echo ERROR: Version is empty.
    pause
    exit /b 1
)

if not "%VERSION:~0,1%"=="v" set VERSION=v%VERSION%

git add .
set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=release %VERSION%
git commit -m "%MSG%"
git push origin main
if errorlevel 1 (
    echo ERROR: push failed.
    pause
    exit /b 1
)

git tag %VERSION%
if errorlevel 1 (
    echo ERROR: Tag %VERSION% already exists.
    pause
    exit /b 1
)

git push origin %VERSION%
if errorlevel 1 (
    echo ERROR: Tag push failed.
    pause
    exit /b 1
)

echo.
echo SUCCESS: Tag %VERSION% released
echo GitHub Actions triggered
echo.
pause
exit /b 0

:RELEASE_AUTO
echo.
echo --- Release mode (auto version bump) ---
echo.

if not exist version.txt (
    echo ERROR: version.txt not found
    pause
    exit /b 1
)

for /f "tokens=*" %%i in (version.txt) do set CURRENT_FULL=%%i
for /f "tokens=1 delims=+" %%i in ("%CURRENT_FULL%") do set CURRENT_VERSION=%%i

echo Current version: %CURRENT_VERSION%
echo.
echo =====================
echo Increment type:
echo   1. Patch (1.0.0 - 1.0.1)
echo   2. Minor (1.0.0 - 1.1.0)
echo   3. Major (1.0.0 - 2.0.0)
echo =====================
echo.

set /p BUMP_TYPE="Select (1, 2 or 3): "

if "%BUMP_TYPE%"=="1" (
    call :calc_patch NEW_VERSION !CURRENT_VERSION!
) else if "%BUMP_TYPE%"=="2" (
    call :calc_minor NEW_VERSION !CURRENT_VERSION!
) else if "%BUMP_TYPE%"=="3" (
    call :calc_major NEW_VERSION !CURRENT_VERSION!
) else (
    echo ERROR: Invalid selection
    pause
    exit /b 1
)

set VERSION=v%NEW_VERSION%

echo.
echo Calculated new version: %VERSION%
echo.

for /f "tokens=*" %%i in ('git rev-parse --short HEAD 2^>nul') do set COMMIT_HASH=%%i
if "%COMMIT_HASH%"=="" set COMMIT_HASH=unknown

echo %NEW_VERSION%+%COMMIT_HASH% > version.txt
echo Updated version.txt: %NEW_VERSION%+%COMMIT_HASH%
echo.

git add .
set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=release %VERSION%
git commit -m "%MSG%"
git push origin main
if errorlevel 1 (
    echo ERROR: push failed
    pause
    exit /b 1
)

git tag %VERSION%
if errorlevel 1 (
    echo ERROR: Tag %VERSION% already exists
    pause
    exit /b 1
)

git push origin %VERSION%
if errorlevel 1 (
    echo ERROR: Tag push failed
    pause
    exit /b 1
)

echo.
echo SUCCESS: Tag %VERSION% released
echo GitHub Actions triggered
echo.
pause
exit /b 0

:calc_patch
setlocal
set CURRENT=%~2
for /f "tokens=1,2,3 delims=." %%a in ("%CURRENT%") do (
    set MAJOR=%%a
    set MINOR=%%b
    set PATCH=%%c
)
set /a PATCH=%PATCH%+1
endlocal & set %~1=%MAJOR%.%MINOR%.%PATCH%
exit /b

:calc_minor
setlocal
set CURRENT=%~2
for /f "tokens=1,2,3 delims=." %%a in ("%CURRENT%") do (
    set MAJOR=%%a
    set MINOR=%%b
    set PATCH=%%c
)
set /a MINOR=%MINOR%+1
set PATCH=0
endlocal & set %~1=%MAJOR%.%MINOR%.%PATCH%
exit /b

:calc_major
setlocal
set CURRENT=%~2
for /f "tokens=1,2,3 delims=." %%a in ("%CURRENT%") do (
    set MAJOR=%%a
    set MINOR=%%b
    set PATCH=%%c
)
set /a MAJOR=%MAJOR%+1
set MINOR=0
set PATCH=0
endlocal & set %~1=%MAJOR%.%MINOR%.%PATCH%
exit /b
