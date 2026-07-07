@echo off
chcp 65001 >nul 2>&1
title Smyshnikov ComfyUI Hub — настройка пути

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
echo    Смена пути к ComfyUI
echo  ====================================================
echo.

python desktop\launcher.py --configure

echo.
echo  Готово. Запустите start.bat, если панель ещё не открыта.
echo.
pause
endlocal
