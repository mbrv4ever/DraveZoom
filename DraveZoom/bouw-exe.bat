@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DraveZoom - exe bouwen

set "PYEXE="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYEXE (
        py -%%V -c "import sys" >nul 2>&1 && set "PYEXE=py -%%V"
    )
)
if not defined PYEXE (
    python -c "import sys" >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
    echo Geen geschikte Python gevonden. Installeer Python 3.10 t/m 3.13.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Geen .venv. Draai eerst run.bat of herstel.bat.
    pause
    exit /b 1
)
echo PyInstaller controleren/installeren...
".venv\Scripts\python.exe" -m pip install --only-binary=:all: pyinstaller
if errorlevel 1 ( echo Kon PyInstaller niet installeren. & pause & exit /b 1 )

echo Bouwen ^(een enkel .exe-bestand^)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean dravezoom.spec
if errorlevel 1 ( echo. & echo Bouwen mislukt. & pause & exit /b 1 )

echo.
echo Klaar: dist\DraveZoom.exe
pause
endlocal
