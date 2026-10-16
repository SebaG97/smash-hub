param([ValidateSet('install','up','down','migrate','bootstrap','test','logs')][string]$Action = 'up')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked([scriptblock]$Command) {
  & $Command
  if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)" }
}
switch ($Action) {
  'install' { Invoke-Checked { docker compose build } }
  'up' { Invoke-Checked { docker compose up -d --build --wait } }
  'down' { Invoke-Checked { docker compose down } }
  'migrate' { Invoke-Checked { docker compose run --rm api alembic upgrade head } }
  'bootstrap' { Invoke-Checked { docker compose run --rm api python -m app.bootstrap } }
  'logs' { Invoke-Checked { docker compose logs -f } }
  'test' {
    try { Invoke-Checked { docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from api } }
    finally { docker compose -f compose.test.yaml down -v }
  }
}
