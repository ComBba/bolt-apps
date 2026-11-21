@echo off
setlocal EnableExtensions
set "SYSROOT=%SystemRoot%"
if not defined SYSROOT set "SYSROOT=C:\Windows"
set "WHERE_EXE=%SYSROOT%\System32\where.exe"
set "NODE_EXE="
pushd "%SYSROOT%" >nul 2>&1
if exist "%WHERE_EXE%" (
  for /f "usebackq delims=" %%p in (`""%WHERE_EXE%" node.exe 2>nul"`) do (
    if not defined NODE_EXE set "NODE_EXE=%%p"
  )
)
popd >nul 2>&1
if not defined NODE_EXE (
  echo bolt-apps: Node 18 or newer is needed and was not found. Install it from https://nodejs.org, then run this again. 1>&2
  exit /b 127
)
set "NODEVER="
for /f "usebackq delims=" %%v in (`""%NODE_EXE%" -v 2>nul"`) do set "NODEVER=%%v"
set "MAJOR=0"
for /f "tokens=1 delims=.vV" %%m in ("%NODEVER%") do set "MAJOR=%%m"
if %MAJOR% LSS 18 (
  echo bolt-apps: Node 18 or newer is needed; this is Node %NODEVER%. Install a newer one from https://nodejs.org, then run this again. 1>&2
  exit /b 127
)
"%NODE_EXE%" "%~dp0toolkit\bin\bolt-apps.mjs" %*
exit /b %ERRORLEVEL%
