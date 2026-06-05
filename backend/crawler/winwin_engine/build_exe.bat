@echo off
echo =======================================
echo WinWinCrawler 3.3 Build Script
echo =======================================

echo [1/3] Building React Frontend...
cd web-ui
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed!
    exit /b %errorlevel%
)
cd ..

echo [2/3] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist\WinWinCrawler rmdir /s /q dist\WinWinCrawler

echo [3/3] Building PyInstaller Executable...
pyinstaller main_web.spec --clean
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed!
    exit /b %errorlevel%
)

echo =======================================
echo Build Successful!
echo =======================================
