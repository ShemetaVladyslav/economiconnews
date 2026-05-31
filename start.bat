@echo off
echo.
echo  ================================================
echo    EconomiconNews - Запуск сервера
echo  ================================================
echo.
echo  Сайт буде доступний: http://localhost:5000
echo  Адмін:  admin@economiconnews.ua
echo  Пароль: Admin2026!
echo.
echo  Натисніть Ctrl+C щоб зупинити
echo  ================================================
echo.
cd /d "%~dp0"
python server.py
pause
