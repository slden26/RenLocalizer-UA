$path = 'd:\Documents\MyRepoGit\locales\english.json'
$content = Get-Content -Raw -Path $path
$enc = New-Object System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllText($path, $content, $enc)
Write-Output 'NO_BOM_DONE'