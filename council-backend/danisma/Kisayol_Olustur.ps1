# Masaustune "Danisma Odasi" kisayolu olusturur (OneDrive'a tasinmis masaustunu da bulur).
$bat = Join-Path $PSScriptRoot "Danisma_Baslat.bat"
if (-not (Test-Path $bat)) { Write-Host "Danisma_Baslat.bat bulunamadi: $bat"; Read-Host "Kapatmak icin Enter"; exit 1 }
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Danisma Odasi.lnk"
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = $bat
$s.WorkingDirectory = $PSScriptRoot
$s.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$s.Description = "Aura Danisma Odasi"
$s.Save()
Write-Host "Kisayol olusturuldu: $lnk"
Read-Host "Kapatmak icin Enter"
