@echo off
chcp 65001 >nul 2>&1
title Smyshnikov ComfyUI Hub — первичная настройка

setlocal
cd /d "%~dp0.."

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [!] Python не найден. Установите Python 3.10+ и добавьте в PATH.
  echo.
  pause
  exit /b 1
)

echo.
echo  ====================================================
echo    Smyshnikov ComfyUI Hub
echo    Первичная настройка
echo  ====================================================
echo.

python desktop\launcher.py --configure

echo.
echo  Дальше: desktop\start.bat
echo  Сменить путь позже: desktop\configure.bat
echo.
pause
endlocal
