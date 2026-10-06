$err = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path "run_dev.ps1").Path, [ref]$null, [ref]$err)
if ($err.Count -gt 0) {
    $err | ForEach-Object {
        Write-Host ("Line {0}: {1}" -f $_.Extent.StartLineNumber, $_.Message)
    }
} else {
    Write-Host "No errors!"
}
