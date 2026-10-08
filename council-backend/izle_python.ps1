# PYTHON SUREC IZLEYICI - SADECE OKUR. python/pythonw sureclerinin DOGUSUNU ve OLUMUNU yakalar.
# Calistir:  powershell -ExecutionPolicy Bypass -File .\izle_python.ps1 [-Saniye 180]
# Durdurmak icin Ctrl+C. Cikti ayrica _izle_python_<tarih>.txt dosyasina yazilir.
param([int]$Saniye = 180)
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$log = Join-Path $PSScriptRoot ("_izle_python_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
function Yaz($m) { $s = "{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $m; Write-Host $s; Add-Content -Path $log -Value $s -Encoding UTF8 }
function Kisalt($s, $n) { if ($null -eq $s) { return "" }; if ($s.Length -gt $n) { return $s.Substring(0, $n) + "..." } else { return $s } }
function Anlik { Get-CimInstance Win32_Process | Where-Object { $_.Name -match "^(python|pythonw)\.exe$" } }
$gorulen = @{}
foreach ($p in Anlik) { $gorulen[$p.ProcessId] = $p }
Yaz ("Basladi. Mevcut python surecleri: " + (($gorulen.Keys | Sort-Object) -join ", "))
$bitis = (Get-Date).AddSeconds($Saniye)
while ((Get-Date) -lt $bitis) {
    $simdi = @{}
    foreach ($p in Anlik) { $simdi[$p.ProcessId] = $p }
    foreach ($id in $simdi.Keys) {
        if (-not $gorulen.ContainsKey($id)) {
            $p = $simdi[$id]
            $par = Get-Process -Id $p.ParentProcessId -ErrorAction SilentlyContinue
            $gp = Get-Process -Id $id -ErrorAction SilentlyContinue
            $mb = if ($gp) { [math]::Round($gp.WorkingSet64 / 1MB) } else { 0 }
            Yaz ("DOGDU  PID {0}  ust PID {1} ({2})  {3} MB  {4}" -f $id, $p.ParentProcessId, $(if ($par) { $par.ProcessName } else { "OLMUS" }), $mb, (Kisalt $p.CommandLine 160))
        }
    }
    foreach ($id in @($gorulen.Keys)) {
        if (-not $simdi.ContainsKey($id)) { Yaz ("OLDU   PID {0}  {1}" -f $id, (Kisalt $gorulen[$id].CommandLine 120)) }
    }
    # bellek ornegi: buyuk python sureclerini kaydet
    foreach ($id in $simdi.Keys) {
        $gp = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($gp -and $gp.WorkingSet64 -gt 1GB) { Yaz ("BUYUK  PID {0}  {1} MB  portlar: {2}" -f $id, [math]::Round($gp.WorkingSet64 / 1MB),
            ((Get-NetTCPConnection -OwningProcess $id -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.LocalPort }) -join ",")) }
    }
    $gorulen = $simdi
    Start-Sleep -Seconds 2
}
Yaz "Bitti. Kayit: $log"
