@echo off
echo ===================================================
echo  Git Auth Reset Tool
echo ===================================================
echo.
echo [1/3] Clearing Windows Credentials for GitHub...
cmdkey /delete:LegacyGeneric:target=git:https://github.com > nul 2>&1
cmdkey /delete:git:https://github.com > nul 2>&1
cmdkey /delete:LegacyGeneric:target=https://github.com > nul 2>&1
cmdkey /delete:https://github.com > nul 2>&1

echo [2/3] Rejecting cached credentials...
(echo protocol=https & echo host=github.com) | git credential reject
(echo protocol=https & echo host=github.com & echo username=winwin0726) | git credential reject

echo [3/3] Target setup: hagisq/winwincrawler2
echo.
echo ===================================================
echo  Auth reset complete!
echo  Please press ANY KEY to run git push.
echo  When the popup appears, click [Sign in with your browser]
echo  to authorize under your current browser account: hagisq
echo ===================================================
echo.
pause
echo.
echo Running git push -u origin main -f ...
echo.
git push -u origin main -f
echo.
echo.
echo Push task finished! Press any key to close this window.
pause
