@echo off
rem ============================================================
rem  Open Human  beta v0.1  --  double-click this file to start.
rem ============================================================
rem  ASCII + CRLF only. cmd.exe reads .bat in the OEM codepage, so UTF-8
rem  Chinese in here would turn into garbage commands. The Chinese menu lives
rem  in scripts\launch.ps1 (that file is UTF-8 with BOM).
rem
rem  Double-click  = ask which model to load (default 2B)
rem  start.bat 1   = always 1B  (lighter, faster)
rem  start.bat 2   = always 2B  (smarter, default)
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Open Human
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\launch.ps1" %*
if errorlevel 1 pause
