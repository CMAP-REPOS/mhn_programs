@echo off
::  sasrun.bat
::  Author: cheither & npeterson
::  Revised: 5/14/14
::  ---------------------------------------------------------------------------
::  This is called by various Python scripts to execute a specified SAS
::  program. SAS 9.3 path is hardcoded in order to send the appropriate SAS
::  command. The ERRORLEVEL variable is used to flag instances when SAS
::  issues a Warning or Error.
::
::  Each script that calls this file must supply the following arguments:
::    1. full path to SAS script
::    2. script parameters as $-separated string
::    3. full path to output .log file
::    4. full path to output .lst file


:: Set SAS path (SAS 9.3+ required for handling .xlsx files)
set SASPATH="C:\Program Files\SASHome\SASFoundation\9.3\sas.exe"
if not exist %SASPATH% goto BADSAS

:: Run SAS
%SASPATH% -sysin %1 -sysparm %2 -log %3 -print %4

:: Write errorlevel to .lst file if SAS did not terminate successfully
if %ERRORLEVEL% gtr 0 echo SAS script failed with errorlevel=%ERRORLEVEL%. Check %3. > %4
goto END

:BADSAS
:: SAS executable not found
echo SAS executable not found. Modify sasrun.bat. > %4
goto END

:END
