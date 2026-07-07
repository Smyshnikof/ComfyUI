@echo off
setlocal
cd /d "%~dp0..\.."
python desktop\build\build.py --portable %*
endlocal
