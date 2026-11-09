@echo off
setlocal
cd /d "%~dp0"
rem Changeling Cosmetics Realtime runs in Changeling CopyCat Realtime's environment with Changeling Cosmetics' code:
rem both next to this folder (as in Changeling Studio). Missing ones are fetched here.
set "STUDIO=%~dp0.."
for %%A in (Cosmetics CopyCat-Realtime) do (
    if not exist "%STUDIO%\Changeling-%%A" (
        echo Getting Changeling %%A ...
        git clone https://github.com/CursedPrograms/Changeling-%%A "%STUDIO%\Changeling-%%A" || goto :error
    )
)
set "PY=%STUDIO%\Changeling-CopyCat-Realtime\venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Setting up Changeling CopyCat Realtime first, once: its environment and its models. Close its window when it opens.
    call "%STUDIO%\Changeling-CopyCat-Realtime\run.bat" --no-virtual
)
"%PY%" cosmetics_live.py %*
exit /b %ERRORLEVEL%

:error
echo.
echo Setup failed, see the messages above.
pause
exit /b 1
