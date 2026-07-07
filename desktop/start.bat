@echo off
chcp 65001 >nul 2>&1
title Smyshnikov ComfyUI Hub

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

if not exist "desktop\config.json" (
  echo.
  echo  config.json не найден — откроется мастер настройки.
  echo  Или заранее: desktop\setup.bat
  echo.
)

python desktop\launcher.py %*

if errorlevel 1 (
  echo.
  echo  [!] Лаунчер завершился с ошибкой. См. лог в %%APPDATA%%\SmyshnikovDownloader\logs\hub.log
  echo.
  pause
)

endlocal
