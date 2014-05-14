@echo off
REM    sasrun.bat
REM    Author: cheither & npeterson
REM    Revised: 5/14/14
REM    ------------------------------------------------------------------------
REM    This is called by various Python scripts to execute a specified SAS
REM    program. SAS 9.3 path is hardcoded in order to send the appropriate SAS
REM    command. The ERRORLEVEL variable is used to flag instances when SAS
REM    issues a Warning or Error.
REM
REM    Each script that calls this file must supply the following arguments:
REM        %1: full path to SAS script
REM        %2: script parameters as $-separated string
REM        %3: full path to output .log file
REM        %4: full path to output .lst file


REM - Set SAS path (SAS 9.3+ required for handling .xlsx files)
set SASPATH="C:\Program Files\SASHome\SASFoundation\9.3\sas.exe"
if not exist %SASPATH% (goto BADSAS)

REM - Run SAS
%SASPATH% -sysin %1 -sysparm %2 -log %3 -print %4
goto ERRCHECK

:BADSAS
REM - SAS executable not found
echo SAS executable not found - manually update sasrun.bat > %4
goto END

:ERRCHECK
REM - Write errorlevel to .lst file if SAS did not terminate successfully
if %ERRORLEVEL% gtr 0 echo errorlevel=%ERRORLEVEL% > %4
goto END

:END
