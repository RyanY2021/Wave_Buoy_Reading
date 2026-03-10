@echo off
setlocal

set "ROOT_DIR=%~dp0"
pushd "%ROOT_DIR%"

set "CONFIG_PATH=%ROOT_DIR%plot_config.ini"
if not "%~1"=="" set "CONFIG_PATH=%~1"

echo Using config: "%CONFIG_PATH%"
python plot_displacement.py --config "%CONFIG_PATH%"
set "EXIT_CODE=%ERRORLEVEL%"

popd
echo.
echo Script finished with exit code %EXIT_CODE%.
:WAIT_EXIT
set /p "USER_EXIT_CMD=Type Q and press Enter to close: "
if /I not "%USER_EXIT_CMD%"=="Q" goto WAIT_EXIT
exit /b %EXIT_CODE%
