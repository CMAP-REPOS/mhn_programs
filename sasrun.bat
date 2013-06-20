@echo off
REM sasrun.bat
REM   cheither & npeterson, last revised 06/01/2013
REM
REM    This is called by various Python scripts to execute a specified SAS program.
REM    SAS paths are defined (now that all pcs should be on Windows 7) in order to send the appropriate SAS command. 
REM    The ERRORLEVEL variable is used to flag instances when SAS issues a Warning or Error.
REM    Each script that calls this file supplies the following arguments: 
REM        %1: SAS program name
REM        %2: directory path
REM        %3: SAS log file name
REM        %4: SAS list file name
REM #################################################

set saspath="C:\Program Files\SASHome\SASFoundation\9.3\sas.exe"
set saspath1="C:\Program Files\SAS\SASFoundation\9.2(32-bit)\sas.exe"
set saspath2="C:\Program Files\SAS\SASFoundation\9.2\sas.exe"

if not exist %saspath% (set saspath=%saspath1%)
if not exist %saspath% (set saspath=%saspath2%)
if not exist %saspath% (goto badsas)

REM - Run SAS
%saspath% -sysin %1 -sysparm %2 -log %3 -print %4
goto end

:badsas
REM - SAS Executable Not Found
@echo SAS Executable Not Found - Manually Update >>%4
goto last

:end
REM - Write Error Message to SAS .LST File if SAS did not Terminate Successfully
if %ERRORLEVEL% GTR 0 echo errorlevel=%ERRORLEVEL% >>%4
:last
