@echo off
chcp 65001 >nul
echo ============================================
echo   DB 초기화 및 AI 쇼핑몰 통합 재구동 스크립트
echo ============================================
echo.

:: 스크립트 실행 디렉토리로 이동
cd /d "%~dp0"

echo 기존 8001번 포트(FastAPI) 점유 프로세스 강제 종료 중...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr "0.0.0.0:8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo 기존 3000번 포트(Next.js) 점유 프로세스 강제 종료 중...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr "0.0.0.0:3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul

echo 기존 sql_app.db 데이터베이스 파일 삭제 초기화 중...
if exist "%~dp0sql_app.db" (
    del /f /q "%~dp0sql_app.db"
    echo 완료! 기존 DB가 초기화되었습니다.
) else (
    echo 기존 DB 파일이 없습니다. 바로 다음 단계로 진행합니다.
)
echo.

echo 수정된 start_servers.bat을 호출하여 서버를 구동합니다.
call "%~dp0start_servers.bat"
