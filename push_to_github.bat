@echo off
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo Установите Git: https://git-scm.com/download/win
  echo Добавьте Git в PATH и запустите этот скрипт снова.
  pause
  exit /b 1
)

if not exist .git (
  git init
  git remote add origin https://github.com/rishat11/Dating.git
)

git add .
git status
set /p OK="Закоммитить и запушить? (y/n): "
if /i not "%OK%"=="y" exit /b 0

git commit -m "Dating bot: aiogram 3, Destiny Index, i18n, geolocation, settings, Redis, rate limit, audit"
git branch -M main
git push -u origin main

echo.
echo Готово.
pause
