@echo off
setlocal

:: Name of the environment variable to check
set "ENV_VAR_NAME=TRAMPOLINE_V2_TEST_ENV"

:: Expected value
set "EXPECTED_VALUE=teapot_v2"

:: Get the value of the environment variable
set ACTUAL_VALUE=%TRAMPOLINE_V2_TEST_ENV%

if "%ACTUAL_VALUE%"=="" (
    echo Error: Environment variable '%TRAMPOLINE_V2_TEST_ENV%' is not set.
    exit /b 1
)

:: Assert that the value matches the expected value
if "%ACTUAL_VALUE%"=="%EXPECTED_VALUE%" (
    echo Success: '%TRAMPOLINE_V2_TEST_ENV%' is set to the expected value.
) else (
    echo Error: '%ENV_VAR_NAME%' is set to '%ACTUAL_VALUE%', but expected '%EXPECTED_VALUE%'.
    exit /b 1
)

exit /b 0
