@echo off
chcp 65001 >nul
title LUXAI 쇼핑몰 통합 접속기
:menu
cls
echo ====================================================
2: echo           LUXAI Premium 쇼핑몰 통합 접속기
3: echo ====================================================
4: echo.
5: echo   [1] 쇼핑몰 메인 접속 (http://localhost:3000)
6: echo   [2] 어드민 대시보드 접속 (http://localhost:3000/admin)
7: echo   [3] 백엔드 API Swagger Docs 접속 (http://localhost:8001/docs)
8: echo   [4] 종료
9: echo.
10: echo ====================================================
11: echo.
12: 
13: choice /c 1234 /n /m "접속하고 싶은 번호를 선택하세요 (1~4): "
14: 
15: if errorlevel 4 goto exit
16: if errorlevel 3 goto api
17: if errorlevel 2 goto admin
18: if errorlevel 1 goto main
19: 
20: :main
21: echo 쇼핑몰 메인 화면으로 접속합니다...
22: start http://localhost:3000
23: timeout /t 2 >nul
24: goto menu
25: 
26: :admin
27: echo 어드민 대시보드로 접속합니다...
28: start http://localhost:3000/admin
29: timeout /t 2 >nul
30: goto menu
31: 
32: :api
33: echo 백엔드 API 문서로 접속합니다...
34: start http://localhost:8001/docs
35: timeout /t 2 >nul
36: goto menu
37: 
38: :exit
39: echo 접속기를 종료합니다.
40: exit
