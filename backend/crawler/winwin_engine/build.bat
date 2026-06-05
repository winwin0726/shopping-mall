@echo off
echo ==============================================
echo WinWinCrawler PyInstaller 빌드 스크립트 (폴더형)
echo ==============================================

:: 파이참/VSCode 환경에서 실행될 때 안전하게 경로 이동
cd /d "%~dp0"

echo [1] PyInstaller 모듈이 존재하는지 확인합니다...
python -m pip install pyinstaller

echo.
echo [2] 기존 빌드 찌꺼기 폴더 초기화 중...
rmdir /s /q build
rmdir /s /q dist\WinWinCrawler

echo.
echo [3] PyInstaller 빌드 시작...
pyinstaller main.spec --clean --noconfirm

echo.
echo ==============================================
echo 빌드가 완료되었습니다! 
echo 실행 파일은 dist\WinWinCrawler\WinWinCrawler.exe 에 있습니다.
echo ==============================================
pause
