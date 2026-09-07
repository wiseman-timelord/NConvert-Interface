:: Script: `NConvert-Interface.bat`

:: Initialization
@echo off
setlocal enabledelayedexpansion
title NConvert-Interface
color 80
echo Initialization Complete.
timeout /t 1 >nul
mode con cols=80 lines=30
powershell -noprofile -command "& { $w = $Host.UI.RawUI; $b = $w.BufferSize; $b.Height = 6000; $w.BufferSize = $b; }"

:: Detect terminal width using PowerShell
for /f "tokens=*" %%a in ('
    powershell -Command ^
        "Get-Host | Select-Object -ExpandProperty UI | Select-Object -ExpandProperty RawUI | Select-Object -ExpandProperty WindowSize | Select-Object -ExpandProperty Width"
') do set TERMINAL_WIDTH=%%a

:: Define separator length based on terminal width
set SEPARATOR_LENGTH=79
if "%TERMINAL_WIDTH%"=="80" set SEPARATOR_LENGTH=79

:: Define separator strings
call :buildSeparator SEPARATOR_LINE_EQ "="
call :buildSeparator SEPARATOR_LINE_DASH "-"

:: Skip headers and function definitions
goto :main_logic

:: Function to build a separator string of specified length and character
:buildSeparator
set "target_var=%~1"
set "char=%~2"
set "line="
for /l %%i in (1,1,%SEPARATOR_LENGTH%) do set "line=!line!%char%"
set "%target_var%=%line%"
goto :eof

:: Function to print a header
:printHeader
echo !SEPARATOR_LINE_EQ!
echo    %~1
echo !SEPARATOR_LINE_EQ!
goto :eof

:: Function to print a separator for prompts
:printSeparator
echo !SEPARATOR_LINE_DASH!
goto :eof

:: Main Logic
:main_logic
:: DP0 TO SCRIPT BLOCK, DO NOT, MODIFY or MOVE: START
set "ScriptDirectory=%~dp0"
set "ScriptDirectory=%ScriptDirectory:~0,-1%"
cd /d "%ScriptDirectory%"
echo Dp0'd to Script.
:: DP0 TO SCRIPT BLOCK, DO NOT, MODIFY or MOVE: END

:: CHECK ADMIN BLOCK
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Error: Admin Required!
    timeout /t 2 >nul
    echo Right Click, Run As Administrator.
    timeout /t 2 >nul
    goto :end_of_file
)
echo Status: Administrator
timeout /t 1 >nul

:: VERIFY PYTHON IS AVAILABLE ON PATH
echo Checking Python availability...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found on PATH.
    echo Please ensure Python 3.10-3.12 is installed and added to your system PATH.
    echo You can download Python from: https://www.python.org/downloads/
    timeout /t 3 >nul
    goto :end_of_file
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
    echo Python %%V detected on PATH.
)
echo.

:: Main Code Begin
:main_menu
REM cls
call :printHeader "NConvert-Interface"
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo     1. Run NConvert-Interface
echo.
echo     2. Install Requirements
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
echo.
call :printSeparator
set /p choice=Selection; Menu Options = 1-2, Exit NConvert-Interface = X: 

if "!choice!"=="1" (
    echo Selected: Run NConvert-Interface
    timeout /t 1 >nul
    goto run_nconvert
) else if "!choice!"=="2" (
    echo Selected: Install Requirements
    timeout /t 1 >nul
    goto run_installer
) else if /i "!choice!"=="X" (
    echo Selected: Exit NConvert-Interface
    timeout /t 1 >nul
    goto :end_of_file
) else (
    echo Invalid option. Please try again.
    pause
    goto :main_menu
)

:run_nconvert
cls
call :printHeader "Run NConvert-Interface"
echo.

:: Check VENV exists before trying to activate
if not exist ".\VENV\Scripts\activate.bat" (
    echo Error: Virtual environment not found at .\VENV\
    echo Please run the installer first ^(option 2^).
    echo.
    pause
    goto :main_menu
)

:: Activate the virtual environment
echo Activating virtual environment...
call .\VENV\Scripts\activate.bat
echo Launching NConvert Gradio Batch...
echo.

:: Run the Python script (now using VENV python)
python .\launcher.py

:: Check if program exited with error
if errorlevel 1 (
    echo.
    echo Error: Program failed to run properly.
    echo Please run the installer option again from the main menu.
)

:: Deactivate the virtual environment
call deactivate

REM pause
goto :main_menu

:: Run Python installer
:run_installer
cls
call :printHeader "Run Installation"
echo.
echo Launching Python installer...
echo Using system Python ^(installer creates VENV internally^)
echo.

:: Check if installer.py exists
if not exist ".\installer.py" (
    echo Error: installer.py not found in script directory!
    echo Please ensure installer.py is present and try again.
    echo.
    pause
    goto :main_menu
)

:: Run the Python installer with SYSTEM python (not venv)
:: The installer itself creates .\VENV and installs packages into it
echo Running installer.py...
echo.
python .\installer.py

:: Capture installer exit code BEFORE anything else can overwrite ERRORLEVEL
set "INSTALLER_EXIT=%ERRORLEVEL%"
echo.

:: Deactivate venv if it was somehow left active
call deactivate 2>nul

:: Check installer exit code (using saved value)
if !INSTALLER_EXIT! GEQ 1 (
    echo Installation encountered errors.
    echo Please review the output above.
) else (
    echo Installation completed successfully.
)

echo.
pause
goto :main_menu

:end_of_file
cls
call :printHeader "Exit NConvert-Interface"
echo.
timeout /t 1 >nul
echo Exiting NConvert-Interface
timeout /t 1 >nul
echo All processes finished.
timeout /t 1 >nul
exit /b