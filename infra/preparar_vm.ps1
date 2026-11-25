# Prepara la VM de Azure (Windows Server 2022) para correr el bot FTMO como runner propio de GitHub.
# Uso (PowerShell como Administrador, dentro de la VM):
#   irm https://raw.githubusercontent.com/matheustescarolo-lab/bot-nasdaq/main/infra/preparar_vm.ps1 -OutFile C:\preparar_vm.ps1
#   powershell -ExecutionPolicy Bypass -File C:\preparar_vm.ps1
# Pide: el token del runner (GitHub > Settings > Actions > Runners > New self-hosted runner) y la contrasena de botadmin.
# No guarda la contrasena en texto plano: el inicio de sesion automatico usa Autologon de Sysinternals (secreto LSA).

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo = 'https://github.com/matheustescarolo-lab/bot-nasdaq'
$tmp = 'C:\bot-instaladores'; New-Item -ItemType Directory -Force $tmp | Out-Null

function Ultimo($proyecto, $patron) {
    # busca en las ultimas versiones estables (no solo la marcada como "latest") el primer archivo que coincida
    $rs = Invoke-RestMethod "https://api.github.com/repos/$proyecto/releases?per_page=20" -Headers @{ 'User-Agent' = 'preparar-vm' }
    foreach ($r in ($rs | Where-Object { -not $_.prerelease -and -not $_.draft })) {
        $a = $r.assets | Where-Object { $_.name -match $patron } | Select-Object -First 1
        if ($a) { return $a.browser_download_url }
    }
    return $null
}

Write-Host '1/7 Git para Windows (trae bash, que usa el flujo)...' -ForegroundColor Cyan
if (-not (Test-Path 'C:\Program Files\Git\bin\bash.exe')) {
    $u = Ultimo 'git-for-windows/git' '^Git-.*-64-bit\.exe$'
    Invoke-WebRequest $u -OutFile "$tmp\git.exe"
    Start-Process "$tmp\git.exe" -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -Wait
}
$rutas = [Environment]::GetEnvironmentVariable('Path', 'Machine')
foreach ($p in 'C:\Program Files\Git\bin', 'C:\Program Files\Git\cmd') {
    if ($rutas -notlike "*$p*") { $rutas = "$rutas;$p" }
}
[Environment]::SetEnvironmentVariable('Path', $rutas, 'Machine')

Write-Host '2/7 PowerShell 7 (pwsh, que usa el flujo)...' -ForegroundColor Cyan
if (-not (Test-Path 'C:\Program Files\PowerShell\7\pwsh.exe')) {
    $u = Ultimo 'PowerShell/PowerShell' 'win-x64\.msi$'
    if ($u) {
        Invoke-WebRequest $u -OutFile "$tmp\pwsh.msi"
        Start-Process msiexec.exe -ArgumentList '/i', "$tmp\pwsh.msi", '/qn', 'ADD_PATH=1' -Wait
    } else {
        Invoke-Expression "& { $(Invoke-RestMethod https://aka.ms/install-powershell.ps1) } -UseMSI -Quiet"   # instalador oficial de Microsoft
    }
    if (-not (Test-Path 'C:\Program Files\PowerShell\7\pwsh.exe')) { throw 'No se instalo PowerShell 7' }
}

Write-Host '3/7 Energia: nunca suspender ni apagar la pantalla...' -ForegroundColor Cyan
powercfg /change standby-timeout-ac 0; powercfg /change monitor-timeout-ac 0; powercfg /hibernate off
tzutil /s 'Central Standard Time (Mexico)'

Write-Host '4/7 Windows Update: sin reinicios con la sesion abierta y horario activo 6:00-22:00...' -ForegroundColor Cyan
$au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
New-Item -Path $au -Force | Out-Null
Set-ItemProperty $au -Name NoAutoRebootWithLoggedOnUsers -Value 1 -Type DWord
$ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
New-Item -Path $ux -Force | Out-Null
Set-ItemProperty $ux -Name ActiveHoursStart -Value 6 -Type DWord
Set-ItemProperty $ux -Name ActiveHoursEnd -Value 22 -Type DWord

Write-Host '5/7 Runner de GitHub...' -ForegroundColor Cyan
$token = Read-Host 'Pega el token del runner (solo el codigo que va despues de --token)'
$dir = 'C:\actions-runner'; New-Item -ItemType Directory -Force $dir | Out-Null
if (-not (Test-Path "$dir\config.cmd")) {
    $u = Ultimo 'actions/runner' '^actions-runner-win-x64-[\d\.]+\.zip$'
    Invoke-WebRequest $u -OutFile "$tmp\runner.zip"
    Expand-Archive "$tmp\runner.zip" -DestinationPath $dir -Force
}
Push-Location $dir
& .\config.cmd --unattended --replace --url $repo --token $token --name azure-mx --labels ftmo-mx --work _work
Pop-Location

Write-Host '6/7 El runner arranca al iniciar sesion (MT5 necesita una sesion de Windows abierta)...' -ForegroundColor Cyan
$accion = New-ScheduledTaskAction -Execute "$dir\run.cmd" -WorkingDirectory $dir
$disparo = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\botadmin"
$quien = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\botadmin" -LogonType Interactive -RunLevel Highest
$conf = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'GitHub runner (bot FTMO)' -Action $accion -Trigger $disparo -Principal $quien -Settings $conf -Force | Out-Null

Write-Host '7/7 Inicio de sesion automatico de botadmin (al reiniciar, el runner vuelve solo)...' -ForegroundColor Cyan
$seg = Read-Host 'Contrasena de botadmin (la de Azure)' -AsSecureString
$plano = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($seg))
Invoke-WebRequest 'https://download.sysinternals.com/files/AutoLogon.zip' -OutFile "$tmp\autologon.zip"
Expand-Archive "$tmp\autologon.zip" -DestinationPath "$tmp\autologon" -Force
Start-Process "$tmp\autologon\Autologon64.exe" -ArgumentList 'botadmin', $env:COMPUTERNAME, $plano, '/accepteula' -Wait
$plano = $null

Write-Host ''
Write-Host 'LISTO. Reinicia la VM (Restart-Computer). Al volver, el runner "azure-mx" debe aparecer Idle (verde) en GitHub > Settings > Actions > Runners.' -ForegroundColor Green
