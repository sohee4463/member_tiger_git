@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: 날짜 및 시간 가져오기
for /f "tokens=1-5 delims=/-:. " %%a in ("%date% %time%") do (
    set YEAR=%%a
    set MONTH=%%b
    set DAY=%%c
    set HOUR=%%d
    set MIN=%%e
)
set COMMIT_MSG=Auto-commit: %YEAR%-%MONTH%-%DAY% %HOUR%:%MIN%

:: 사용자 안내 출력
echo 🔄 커밋 중입니다...

:: Git 명령 실행 (출력 숨기기)
git add . > nul 2>&1
git commit -m "%COMMIT_MSG%" > nul 2>&1
git push origin main > nul 2>&1

:: 완료 메시지
echo ✅ 업로드 및 푸시 완료!
echo 💡 커밋 메시지: %COMMIT_MSG%

pause
endlocal


