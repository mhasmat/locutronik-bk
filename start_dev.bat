@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ==========================================
echo   Locutronik - Inicio de desarrollo
echo ==========================================
echo.

REM --- 1. Verificar que ngrok este en el PATH ---
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ngrok no esta en el PATH.
    echo Verifica que C:\ngrok este agregado al Path de Windows.
    pause
    exit /b 1
)

REM --- 2. Verificar que la config de ngrok exista ---
if not exist "%LocalAppData%\ngrok\ngrok.yml" (
    echo [ERROR] ngrok no esta configurado.
    echo Ejecuta primero: ngrok config add-authtoken TU_AUTHTOKEN
    pause
    exit /b 1
)

REM --- 3. Definir la ruta del frontend (AJUSTA ESTA LINEA si es distinta) ---
set "FRONTEND_DIR=C:\Users\Marto\Locutronik-ft"

REM --- 4. Verificar que la carpeta del frontend exista ---
if not exist "%FRONTEND_DIR%" (
    echo [ERROR] No se encontro la carpeta del frontend en:
    echo     %FRONTEND_DIR%
    echo Edita este .bat y ajusta la variable FRONTEND_DIR.
    pause
    exit /b 1
)

REM --- 5. Matar procesos previos de ngrok ---
taskkill /IM ngrok.exe /F >nul 2>&1

REM --- 6. Iniciar ngrok en ventana minimizada ---
echo [1/6] Iniciando tunel de ngrok...
start "ngrok" /MIN ngrok http 8000

REM --- 7. Esperar a que ngrok levante la API local ---
echo [2/6] Esperando a que ngrok este listo...
timeout /t 6 /nobreak >nul

REM --- 8. Obtener la URL publica y actualizar .env ---
echo [3/6] Obteniendo URL publica y actualizando .env...

powershell -NoProfile -Command ^
  "$ErrorActionPreference = 'Stop';" ^
  "try {" ^
  "  $tunnels = Invoke-RestMethod -Uri 'http://localhost:4040/api/tunnels' -TimeoutSec 10;" ^
  "  $url = $tunnels.tunnels[0].public_url;" ^
  "  if (-not $url) { throw 'No se obtuvo public_url' };" ^
  "  $envPath = Join-Path (Get-Location) '.env';" ^
  "  if (-not (Test-Path $envPath)) { throw '.env no encontrado en la raiz del proyecto' };" ^
  "  $content = Get-Content $envPath -Raw;" ^
  "  if ($content -match 'BACKEND_URL=') {" ^
  "    $content = $content -replace 'BACKEND_URL=.*', ('BACKEND_URL=' + $url);" ^
  "  } else {" ^
  "    $content = $content.TrimEnd() + [Environment]::NewLine + 'BACKEND_URL=' + $url + [Environment]::NewLine;" ^
  "  }" ^
  "  Set-Content -Path $envPath -Value $content -NoNewline;" ^
  "  Write-Host ('  [OK] BACKEND_URL actualizado a: ' + $url);" ^
  "  Write-Host ('  [URL] Webhook MP: ' + $url + '/api/payments/webhook/');" ^
  "} catch {" ^
  "  Write-Host ('  [WARN] No se pudo actualizar .env: ' + $_.Exception.Message);" ^
  "}"

REM --- 9. Iniciar Django, Celery Worker y Celery Beat ---
echo.
echo [4/6] Iniciando Django, Celery Worker y Celery Beat...

start "Django" cmd /k "env\Scripts\activate && python manage.py runserver"
timeout /t 2 /nobreak >nul

start "Celery Worker" cmd /k "env\Scripts\activate && celery -A config worker --loglevel=info --pool=solo"
timeout /t 2 /nobreak >nul

start "Celery Beat" cmd /k "env\Scripts\activate && celery -A config beat --loglevel=info"

REM --- 10. Iniciar el frontend (Vite) ---
echo.
echo [5/6] Iniciando frontend (Vite)...
start "Frontend (Vite)" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

REM --- 11. Resumen final ---
echo.
echo [6/6] Entorno iniciado correctamente.
echo.
echo   - ngrok:          ventana minimizada (dashboard: http://localhost:4040)
echo   - Django:         ventana "Django"
echo   - Celery Worker:  ventana "Celery Worker"
echo   - Celery Beat:    ventana "Celery Beat"
echo   - Frontend:       ventana "Frontend (Vite)"
echo.
echo   Accesos rapidos:
echo     - Backend admin:  http://127.0.0.1:8000/admin/
echo     - Frontend:       http://localhost:5173/
echo.
echo IMPORTANTE: si vas a probar pagos, actualiza la URL del webhook
echo en el panel de Mercado Pago con la URL actual de ngrok que se
echo muestra arriba. La URL cambia cada vez que reinicias este script.
echo.
echo Para detener todo: cerra las ventanas y ejecuta
echo     taskkill /IM ngrok.exe /F
echo.
pause