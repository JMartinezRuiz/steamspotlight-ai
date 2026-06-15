@echo off
setlocal
set "PROJ=%~dp0"

if exist "%PROJ%.venv\Scripts\activate.bat" (
    call "%PROJ%.venv\Scripts\activate.bat"
) else if exist "%PROJ%venv\Scripts\activate.bat" (
    call "%PROJ%venv\Scripts\activate.bat"
) else (
    echo No virtual environment found.
    echo Create one with:
    echo   py -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

python "%PROJ%main.py" %*
endlocal

