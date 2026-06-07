@echo off
chcp 65001 >nul
REM ============================================================
REM  LUXAI 쇼핑몰 - 웹 테스트(임시 공개) 시작 스크립트
REM  Cloudflare(7844 포트)가 회사망에서 막혀 pinggy(443/SSH) 사용.
REM  * 처음 1회: frontend 에서 'npm run build' 를 먼저 해두세요.
REM ============================================================
cd /d "%~dp0"

echo [1/3] 백엔드(8002) 시작...
start "LUXAI Backend (8002)" backend\venv\Scripts\python.exe -m uvicorn backend.main:app --port 8002
ping 127.0.0.1 -n 4 >nul

echo [2/3] 프론트(3000, 프로덕션) 시작...
start "LUXAI Frontend (3000)" cmd /c "cd frontend && npm run start"
ping 127.0.0.1 -n 7 >nul

echo [3/3] 공개 터널(pinggy, 443) 시작...
start "LUXAI Tunnel (pinggy)" ssh -p 443 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -R 0:localhost:3000 a.pinggy.io

echo.
echo ============================================================
echo  "LUXAI Tunnel" 창에 표시되는  https://....pinggy-free.link
echo  주소가 외부 공개 URL 입니다. 그 주소로 접속하세요.
echo  (무료 세션은 약 60분. 끊기면 이 배치를 다시 실행 → 새 주소.)
echo ============================================================
pause
