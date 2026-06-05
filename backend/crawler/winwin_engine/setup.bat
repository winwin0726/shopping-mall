@echo off
echo ===================================================
echo 🚀 Winwin Crawler 3.3 초기 세팅을 시작합니다...
echo ===================================================

echo.
echo [1/3] Python 패키지 의존성을 설치합니다...
pip install -r requirements.txt

echo.
echo [2/3] Playwright(웹 자동화)용 크로미움 브라우저를 설치합니다...
playwright install chromium

echo.
echo [3/3] 프론트엔드 종속성을 설치합니다 (선택사항)...
cd web-ui
call npm install
cd ..

echo.
echo ===================================================
echo ✅ 모든 세팅이 완료되었습니다! 
echo 이제 'run.bat'를 더블클릭하여 프로그램을 실행하세요.
echo ===================================================
pause
