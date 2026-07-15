@echo off
setlocal
chcp 65001 >nul
title MDB BFF - Serveur de developpement
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "FLASK_APP=run.py"
set "FLASK_ENV=development"

echo.
echo  =========================================
echo   MDB BFF - Dossier Constructeur Qualite
echo   Serveur de developpement Flask (SQLite)
echo  =========================================
echo.

if not exist "%PY%" goto :no_venv

echo  [1/3] Mise a jour du schema de base de donnees...
"%PY%" -m flask db upgrade
if errorlevel 1 goto :db_error

echo  [2/3] Verification des comptes et modeles (idempotent)...
"%PY%" -m flask seed

echo  [3/3] Demarrage du serveur : http://127.0.0.1:5000
echo.
echo  Comptes de connexion  -  mot de passe initial : BFF-init-2026!
echo    - stephane.paumelle@ait-stein.com     Admin
echo    - brice.girard@bffrance.com           Approbateur
echo    - corentin.duval-arnould@bffrance.com Redacteur
echo.
echo  Langues : ajoutez  ?lang=en  (ou de / it) a l'URL.
echo  Arret du serveur : Ctrl+C dans cette fenetre.
echo.

start "" /min cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"
"%PY%" -m flask run
goto :end

:no_venv
echo  [ERREUR] Environnement virtuel introuvable : %PY%
echo           Creez-le puis installez les dependances :
echo             python -m venv .venv
echo             .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
echo.
pause
exit /b 1

:db_error
echo.
echo  [ERREUR] Echec de la migration de base de donnees.
echo           Verifiez DATABASE_URL dans le fichier .env
echo.
pause
exit /b 1

:end
echo.
echo  Serveur arrete.
pause
endlocal
