@echo off
rem Fukufuku no Shima English Translation - Windows build script
rem Usage: build.cmd [path\to\original.iso] [--xdelta]
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3 is required: https://www.python.org/downloads/ & pause & exit /b 1)
python tools\build.py %*
pause
