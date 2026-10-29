@echo off
rem Open Human - double-click to start.
rem No packaging, no service: this script only brings up "oh serve" from .venv.
rem Keep this file ASCII and CRLF: cmd.exe reads .cmd in the OEM codepage, so
rem UTF-8 Chinese here turns into garbage commands.
rem
rem This shell has three jobs:
rem   1) keep .venv usable after the folder moves (see :fixvenv)
rem   2) run the server in this window (python, foreground, Ctrl+C stops it)
rem   3) open the app window with cmd.exe as the parent. python cannot do it on
rem      this machine: a browser started from python gets killed a second later.
rem      python publishes "data\window.cmd" when the server is ready, the helper
rem      started below runs it. See BUILD.md section 14.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Open Human

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if /i "%~1"=="--window" goto window

if not exist ".venv\Scripts\python.exe" goto nopython
call :fixvenv

if exist "data\window.cmd" del /q "data\window.cmd" 2>nul
set "OPENHUMAN_SHELL_WINDOW=1"
start "" /min cmd /c ""%~f0" --window"

".venv\Scripts\python.exe" -m openhuman.cli serve %*
set "code=%ERRORLEVEL%"
if "%code%"=="7" exit /b 0

echo.
echo [open human] stopped ^(code %code%^).
pause
exit /b %code%

:fixvenv
rem A venv records an ABSOLUTE path to its base interpreter. Unzip this folder on
rem another machine (or just move it) and .venv\Scripts\python.exe stops
rem starting. Rewrite that one line on every start: cheap, and the zip becomes
rem relocatable. The base interpreter is the single folder under vendor\python.
if not exist ".venv\pyvenv.cfg" exit /b 0
set "PYBASE="
for /d %%d in ("vendor\python\*") do set "PYBASE=%%~fd"
if not defined PYBASE exit /b 0
findstr /v /b /i "home =" ".venv\pyvenv.cfg" > ".venv\pyvenv.tmp" 2>nul
> ".venv\pyvenv.new" echo home = %PYBASE%
type ".venv\pyvenv.tmp" >> ".venv\pyvenv.new"
del /q ".venv\pyvenv.tmp" 2>nul
rem Never replace with something empty: a broken pyvenv.cfg means nothing starts.
for %%a in (".venv\pyvenv.new") do if %%~za LSS 20 exit /b 0
move /y ".venv\pyvenv.new" ".venv\pyvenv.cfg" >nul

rem Same trap, one level deeper: "uv sync" installs this project editable and
rem writes the SOURCE path into a .pth. Absolute there means a copy of the folder
rem imports the original one (or nothing at all). Three levels up from
rem .venv\Lib\site-packages is the project root, so this line stays true anywhere.
if not exist ".venv\Lib\site-packages" exit /b 0
> ".venv\Lib\site-packages\_editable_impl_openhuman.pth" echo ..\..\..\src
exit /b 0

:window
rem Helper. Waits for python to publish the launch script, then opens the window.
rem 90 seconds is slack: uvicorn is up in about a second, the model keeps loading
rem in the background and the page shows that itself.
set /a tries=0
:wait
if exist "data\window.cmd" goto run
set /a tries+=1
if %tries% geq 90 exit /b 0
ping -n 2 127.0.0.1 >nul
goto wait

:run
call "data\window.cmd"
del /q "data\window.cmd" 2>nul
exit /b 0

:nopython
echo.
echo [open human] .venv not found.
echo Run this once in this folder:
echo     vendor\uv\uv.exe sync
echo.
pause
exit /b 1
