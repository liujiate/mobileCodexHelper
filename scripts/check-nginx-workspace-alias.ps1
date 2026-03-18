$workspace = Split-Path -Parent $PSScriptRoot
$runtimeRoot = if ($env:MOBILE_CODEX_RUNTIME_DIR) {
  $env:MOBILE_CODEX_RUNTIME_DIR
} else {
  Join-Path $workspace '.runtime'
}
$asciiAlias = if ($env:MOBILE_CODEX_ASCII_ALIAS) {
  $env:MOBILE_CODEX_ASCII_ALIAS
} else {
  Join-Path $env:SystemDrive 'mobileCodexHelper_ascii'
}
$aliasTarget = Split-Path -Parent $runtimeRoot
$runtimeLeaf = Split-Path -Leaf $runtimeRoot

if (-not (Test-Path $asciiAlias)) {
  New-Item -ItemType Junction -Path $asciiAlias -Target $aliasTarget | Out-Null
}

$nginxRoot = Join-Path (Join-Path $asciiAlias $runtimeLeaf) 'nginx'
New-Item -ItemType Directory -Force -Path (Join-Path $nginxRoot 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $nginxRoot 'temp') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $nginxRoot 'conf') | Out-Null

[PSCustomObject]@{
  Workspace = $workspace
  RuntimeRoot = $runtimeRoot
  AsciiAlias = $asciiAlias
  NginxRoot = $nginxRoot
} | Format-List
