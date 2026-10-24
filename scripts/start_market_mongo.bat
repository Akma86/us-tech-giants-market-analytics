@echo off
REM ==============================================================================
REM Script: start_market_mongo.bat
REM Description: Launches a dedicated, isolated MongoDB instance on port 27018
REM              using this project's local data directory.
REM Author: Akmal Yaasir Fauzaan
REM Project: US Tech Giants Market Analytics
REM ==============================================================================

set "MONGO_BIN=C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe"
if not exist "%MONGO_BIN%" (
    for /f "tokens=*" %%i in ('where mongod 2^>nul') do set "MONGO_BIN=%%i"
)

set "PROJECT_DIR=%~dp0.."
set "DB_PATH=%PROJECT_DIR%\data\database\mongodb_market_data"
set "LOG_PATH=%PROJECT_DIR%\data\database\mongod_27018.log"

if not exist "%DB_PATH%" mkdir "%DB_PATH%"

echo ==============================================================================
echo STARTING DEDICATED MARKET ANALYTICS MONGODB INSTANCE
echo Port: 27018
echo Database Directory: %DB_PATH%
echo Connection URI: mongodb://localhost:27018/
echo ==============================================================================

"%MONGO_BIN%" --dbpath "%DB_PATH%" --port 27018 --logpath "%LOG_PATH%"
