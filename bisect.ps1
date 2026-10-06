$lines = Get-Content run_dev.ps1
for ($i = 1; $i -le $lines.Length; $i++) {
    $sub = $lines[0..($i-1)]
    Set-Content temp.ps1 $sub
    $err = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path temp.ps1).Path,
        [ref]$null,
        [ref]$err
    )
    if ($err.Count -gt 0) {
        $firstMissingClosing = $err | Where-Object { $_.Message -match "Missing closing" }
        if ($firstMissingClosing) {
            Write-Host "Breaks at line $i : $($firstMissingClosing[0].Message)"
            break
        }
    }
}
