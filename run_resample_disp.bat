@echo off
setlocal

set "ROOT_DIR=%~dp0"
pushd "%ROOT_DIR%"

python resample_disp_txt.py %*
set "EXIT_CODE=%ERRORLEVEL%"

popd
echo.
echo Script finished with exit code %EXIT_CODE%.
:WAIT_EXIT
set /p "USER_EXIT_CMD=Type EXIT and press Enter to close: "
if /I not "%USER_EXIT_CMD%"=="EXIT" goto WAIT_EXIT
exit /b %EXIT_CODE%
