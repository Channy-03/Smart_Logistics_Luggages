@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where git >nul 2>nul || (echo [!] Git is not installed. Install from https://git-scm.com and run again. & pause & exit /b 1)
for /f "delims=" %%a in ('git config --global user.name') do set GN=%%a
for /f "delims=" %%a in ('git config --global user.email') do set GE=%%a
if "%GN%"=="" (set /p GN=Your name for commits: & call git config --global user.name "%%GN%%")
if "%GE%"=="" (set /p GE=Email of your GitHub account: & call git config --global user.email "%%GE%%")
echo.
echo Commits will be made as: %GN% ^<%GE%^>
echo If this is not you, close this window and fix "git config --global user.name / user.email".
pause
if exist work rmdir /s /q work
git clone https://github.com/Channy-03/Smart_Logistics_Luggages.git work || (echo [!] Clone failed. & pause & exit /b 1)
xcopy /e /i /y files work >nul
cd work
for /f "usebackq tokens=1,*" %%i in ("..\groups.txt") do (
  git add %%j
  git commit -q -F "..\msg\%%i.txt"
)
echo.
git log --format="%%h %%an  %%s" -n 8
echo.
git checkout -q -b docs/problem-results-kyungjin
git push -u origin docs/problem-results-kyungjin || (echo [!] Push failed. Ask Minchan to invite you as a collaborator, accept the invite email, then run again. & pause & exit /b 1)
echo.
echo Done. Open this link and click "Create pull request":
echo https://github.com/Channy-03/Smart_Logistics_Luggages/compare/main...docs/problem-results-kyungjin?expand=1
pause
