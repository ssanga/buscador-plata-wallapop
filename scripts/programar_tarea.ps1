# Registra en el Programador de tareas de Windows la ejecución diaria del batch.
#   powershell -ExecutionPolicy Bypass -File scripts\programar_tarea.ps1            (03:30 por defecto)
#   powershell -ExecutionPolicy Bypass -File scripts\programar_tarea.ps1 -Hora 05:00
param([string]$Hora = "03:30")

$script = Join-Path $PSScriptRoot "ejecutar_batch.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Hora
# StartWhenAvailable: si el PC estaba apagado a esa hora, se ejecuta al encenderlo.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName "BuscadorPlataWallapop" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Descarga nocturna de monedas de plata en Wallapop" -Force | Out-Null

Write-Host "Tarea 'BuscadorPlataWallapop' programada a diario a las $Hora."
Write-Host "Probarla ahora:  Start-ScheduledTask -TaskName BuscadorPlataWallapop"
