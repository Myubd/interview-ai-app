@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Interview App Release Tool
echo ========================================
echo.

for /f "tokens=*" %%i in ('git describe --tags --abbrev=0 2^>nul') do set LATEST_TAG=%%i
if "%LATEST_TAG%"=="" set LATEST_TAG=v0.0.0

echo Current tag: %LATEST_TAG%
echo.

set VERSION=%LATEST_TAG:v=%

for /f "tokens=1,2,3 delims=." %%a in ("%VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
    set PATCH=%%c
)

set /a NEXT_MAJOR=%MAJOR%+1
set /a NEXT_MINOR=%MINOR%+1
set /a NEXT_PATCH=%PATCH%+1

set NEW_MAJOR=v%NEXT_MAJOR%.0.0
set NEW_MINOR=v%MAJOR%.%NEXT_MINOR%.0
set NEW_PATCH=v%MAJOR%.%MINOR%.%NEXT_PATCH%

echo Select release type:
echo.
echo   1. Major - Breaking changes   (%LATEST_TAG% -^> %NEW_MAJOR%)
echo   2. Minor - New features       (%LATEST_TAG% -^> %NEW_MINOR%)
echo   3. Patch - Bug fixes          (%LATEST_TAG% -^> %NEW_PATCH%)
echo   0. Cancel
echo.
set /p CHOICE="Enter number: "

if "%CHOICE%"=="1" (
    set NEW_TAG=%NEW_MAJOR%
) else if "%CHOICE%"=="2" (
    set NEW_TAG=%NEW_MINOR%
) else if "%CHOICE%"=="3" (
    set NEW_TAG=%NEW_PATCH%
) else if "%CHOICE%"=="0" (
    echo Cancelled.
    pause
    exit /b 0
) else (
    echo Invalid input.
    pause
    exit /b 1
)

echo.
echo New tag: %NEW_TAG%
echo.

set /p COMMIT_MSG="Commit message (leave blank to skip commit): "

echo.
echo The following will be executed:
if not "%COMMIT_MSG%"=="" echo   git add . ^& git commit -m "%COMMIT_MSG%"
echo   git push origin main
echo   git tag %NEW_TAG%
echo   git push origin %NEW_TAG%
echo.
set /p CONFIRM="Proceed? (y/n): "

if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.

if not "%COMMIT_MSG%"=="" (
    echo [1/4] Committing...
    git add .
    git commit -m "%COMMIT_MSG%"
    if errorlevel 1 echo No changes to commit. Continuing...
) else (
    echo [1/4] Skipping commit.
)

echo [2/4] Pushing main...
git push origin main
if errorlevel 1 ( echo Push failed. & pause & exit /b 1 )

echo [3/4] Creating tag %NEW_TAG%...
git tag %NEW_TAG%
if errorlevel 1 ( echo Tag already exists. & pause & exit /b 1 )

echo [4/4] Pushing tag...
git push origin %NEW_TAG%
if errorlevel 1 ( echo Tag push failed. & pause & exit /b 1 )

echo.
echo ========================================
echo   Released! %NEW_TAG%
echo   https://github.com/Myubd/interview-ai-app/actions
echo ========================================
echo.
pause
