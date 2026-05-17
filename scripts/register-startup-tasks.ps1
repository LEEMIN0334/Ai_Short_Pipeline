$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $RepoRoot.Path ".local_storage\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Register-RepoStartupTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName,
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [string]$LogName,
        [string[]]$ScriptArguments = @()
    )

    $quotedArgs = @()
    foreach ($arg in $ScriptArguments) {
        $quotedArgs += "'" + ($arg -replace "'", "''") + "'"
    }

    $logPath = Join-Path $LogDir $LogName
    $command = "& '$ScriptPath' $($quotedArgs -join ' ') *>> '$logPath'"

    try {
        $action = New-ScheduledTaskAction `
            -Execute "powershell.exe" `
            -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$command`"" `
            -WorkingDirectory $RepoRoot.Path
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet `
            -MultipleInstances IgnoreNew `
            -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Days 0) `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -Hidden

        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Description "AI Shorts Pipeline startup task managed from repo scripts." `
            -Force | Out-Null

        Remove-StartupShortcut -TaskName $TaskName

        [PSCustomObject]@{
            Name = $TaskName
            Mode = "scheduled_task"
            Path = $TaskName
        }
        return
    }
    catch {
        New-StartupShortcut `
            -TaskName $TaskName `
            -Command $command
    }
}

function Remove-StartupShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName
    )

    $startupDir = [Environment]::GetFolderPath("Startup")
    $shortcutPath = Join-Path $startupDir "$TaskName.lnk"
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
    }
}

function New-StartupShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName,
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    $startupDir = [Environment]::GetFolderPath("Startup")
    $shortcutPath = Join-Path $startupDir "$TaskName.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command `"$Command`""
    $shortcut.WorkingDirectory = $RepoRoot.Path
    $shortcut.WindowStyle = 7
    $shortcut.Save()

    [PSCustomObject]@{
        Name = $TaskName
        Mode = "startup_shortcut"
        Path = $shortcutPath
    }
}

$registered = @()
$registered += Register-RepoStartupTask `
    -TaskName "AI Shorts Dashboard" `
    -ScriptPath (Join-Path $RepoRoot.Path "scripts\dashboard.ps1") `
    -LogName "startup-dashboard.log" `
    -ScriptArguments @("-HostAddress", "0.0.0.0", "-Port", "3000")

$registered += Register-RepoStartupTask `
    -TaskName "AI Shorts Agent Worker" `
    -ScriptPath (Join-Path $RepoRoot.Path "scripts\agent-worker.ps1") `
    -LogName "startup-agent-worker.log"

$registered += Register-RepoStartupTask `
    -TaskName "OpenClaw Gateway" `
    -ScriptPath (Join-Path $RepoRoot.Path "scripts\openclaw-gateway.ps1") `
    -LogName "startup-openclaw-gateway.log"

$registered += Register-RepoStartupTask `
    -TaskName "AI Shorts Telegram Bot" `
    -ScriptPath (Join-Path $RepoRoot.Path "scripts\telegram-bot.ps1") `
    -LogName "startup-telegram-bot.log" `
    -ScriptArguments @("-BotRole", "pm")

$registered += Register-RepoStartupTask `
    -TaskName "AI Shorts Research Telegram Bot" `
    -ScriptPath (Join-Path $RepoRoot.Path "scripts\telegram-bot.ps1") `
    -LogName "startup-telegram-research-bot.log" `
    -ScriptArguments @("-BotRole", "research")

$registered += Register-RepoStartupTask `
    -TaskName "AI Shorts Developer Telegram Bot" `
    -ScriptPath (Join-Path $RepoRoot.Path "scripts\telegram-bot.ps1") `
    -LogName "startup-telegram-developer-bot.log" `
    -ScriptArguments @("-BotRole", "developer")

$registered | Format-Table -AutoSize
