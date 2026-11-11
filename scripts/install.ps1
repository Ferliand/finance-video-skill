<#
.SYNOPSIS
  Pasang skill ke Claude Code, Antigravity, dan/atau Pi di Windows PowerShell.
.EXAMPLE
  .\scripts\install.ps1 -All
  .\scripts\install.ps1 -Antigravity
  .\scripts\install.ps1 -All -Project C:\proyek\saya
#>
[CmdletBinding()]
param(
    [switch]$Claude,
    [switch]$Antigravity,
    [switch]$Pi,
    [switch]$All,
    [switch]$Link,
    [string]$Project
)

$ErrorActionPreference = "Stop"
$Name = "finance-video-script"
$SkillSrc = Join-Path $PSScriptRoot "..\skills\$Name"
$SkillSrc = [System.IO.Path]::GetFullPath($SkillSrc)

if (-not (Test-Path (Join-Path $SkillSrc "SKILL.md"))) {
    Write-Error "SKILL.md tidak ditemukan di $SkillSrc"
}

$targets = @()
if ($All) {
    $targets = @("claude", "antigravity", "pi")
} else {
    if ($Claude) { $targets += "claude" }
    if ($Antigravity) { $targets += "antigravity" }
    if ($Pi) { $targets += "pi" }
}

if ($targets.Count -eq 0) {
    Write-Error "Pilih minimal satu target: -Claude, -Antigravity, -Pi, atau -All"
}

function Get-DestDir([string]$target) {
    if ($Project) {
        switch ($target) {
            "claude"      { return Join-Path $Project ".claude\skills" }
            "antigravity" { return Join-Path $Project ".agents\skills" }
            "pi"          { return Join-Path $Project ".pi\skills" }
        }
    } else {
        $homeDir = [Environment]::GetFolderPath("UserProfile")
        switch ($target) {
            "claude"      { return Join-Path $homeDir ".claude\skills" }
            "antigravity" { return Join-Path $homeDir ".gemini\config\skills" }
            "pi"          { return Join-Path $homeDir ".pi\agent\skills" }
        }
    }
}

foreach ($t in $targets) {
    $destParent = Get-DestDir $t
    New-Item -ItemType Directory -Force -Path $destParent | Out-Null
    $dest = Join-Path $destParent $Name
    if (Test-Path $dest) {
        Remove-Item -Recurse -Force $dest
    }
    if ($Link) {
        New-Item -ItemType SymbolicLink -Path $dest -Target $SkillSrc | Out-Null
    } else {
        Copy-Item -Recurse -Force $SkillSrc $dest
    }
    Write-Host "[$t] -> $dest"
}

Write-Host "Selesai. Mulai ulang sesi agen agar skill terdeteksi."
