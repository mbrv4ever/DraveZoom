@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DraveZoom

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

if not exist ".venv\Scripts\pythonw.exe" (
    echo Eenmalige installatie ^(even geduld^)...
    %PYEXE% -m venv ".venv"
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Installatie mislukt. Draai herstel.bat of start-debug.bat.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" "dravezoom.py" %*
endlocal
