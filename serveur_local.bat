@echo off
rem NB : pas de "enabledelayedexpansion" — il avalerait le "!" du mot de
rem passe initial affiche plus bas (BFF-init-2026!).
setlocal
chcp 65001 >nul
title MDB BFF - Serveur local partage (Waitress)
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "WAITRESS=.venv\Scripts\waitress-serve.exe"
set "PORT=5000"

echo.
echo  ==================================================
echo   MDB BFF - Dossier Constructeur Qualite
echo   Serveur local partage sur le reseau BFF (pilote)
echo  ==================================================
echo.

if not exist "%PY%" goto :no_venv
if not exist "%WAITRESS%" goto :no_waitress

echo  [1/3] Mise a jour du schema de base de donnees...
"%PY%" -m flask db upgrade
if errorlevel 1 goto :db_error

echo  [2/3] Verification des comptes et modeles (idempotent)...
"%PY%" -m flask seed

rem --- Detection de l'adresse IP de ce PC sur le reseau local ---
rem NB : pas de caret devant les pipes DANS les guillemets (cmd les
rem transmettrait tels quels a PowerShell, qui echouerait en silence).
rem Le repli ne doit contenir ni "<" ni ">" (cmd y verrait une redirection).
set "LANIP="
for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1 -ExpandProperty IPv4Address).IPAddress" 2^>nul') do set "LANIP=%%I"
if not defined LANIP set "LANIP=IP-de-ce-PC_voir-ipconfig"

echo  [3/3] Demarrage du serveur sur le port %PORT%...
echo.
echo  --------------------------------------------------
echo   Depuis CE PC              : http://127.0.0.1:%PORT%
echo   Depuis un autre poste BFF : http://%LANIP%:%PORT%
echo  --------------------------------------------------
echo.
echo  Comptes  -  mot de passe initial : BFF-init-2026!
echo    - stephane.paumelle@ait-stein.com      Admin
echo    - brice.girard@bffrance.com            Approbateur
echo    - corentin.duval-arnould@bffrance.com  Redacteur
echo    (les 7 comptes BFF sont crees par l'etape [2/3])
echo.
echo  Langues : bouton dans le menu, ou ajoutez ?lang=en (de / it) a l'URL.
echo  1er lancement : si Windows demande d'AUTORISER l'acces reseau -^> Autoriser
echo                  (reseaux prives), sinon les collegues ne verront pas le site.
echo  Note : le PDF du dossier complet (assemblage) necessite Redis ; les PDF
echo         unitaires de formulaires fonctionnent sans.
echo  Arret du serveur : fermez cette fenetre ou Ctrl+C.
echo.

start "" /min cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:%PORT%"
"%WAITRESS%" --listen=0.0.0.0:%PORT% --threads=8 run:app
goto :end

:no_venv
echo  [ERREUR] Environnement virtuel introuvable : %PY%
echo           Creez-le puis installez les dependances :
echo             python -m venv .venv
echo             .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1

:no_waitress
echo  [ERREUR] Waitress introuvable : %WAITRESS%
echo           Installez les dependances :
echo             "%PY%" -m pip install -r requirements.txt
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
