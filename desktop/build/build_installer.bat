@echo off
setlocal
cd /d "%~dp0..\.."

echo [1/2] PyInstaller...
python desktop\build\build.py --pyinstaller
if errorlevel 1 exit /b 1

echo [2/2] Inno Setup...
set ISCC=
for %%I in (
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  "C:\Program Files\Inno Setup 6\ISCC.exe"
) do if exist %%I set ISCC=%%~I

if not defined ISCC (
  echo Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php
  echo PyInstaller output is in desktop\dist\SmyshnikovPresetDownloader\
  exit /b 1
)

"%ISCC%" desktop\build\installer.iss
echo Done: desktop\dist\SmyshnikovComfyUIHub-setup.exe
endlocal
