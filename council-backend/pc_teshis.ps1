# PC KASMA TESHISI - SADECE OKUR, hicbir seyi kapatmaz/silmez.
# Calistir (council-backend klasorunde):  powershell -ExecutionPolicy Bypass -File .\pc_teshis.ps1
# Cikti ayrica _pc_teshis_<tarih>.txt dosyasina yazilir.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$rapor = Join-Path $PSScriptRoot ("_pc_teshis_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmm"))
function Yaz($m) { Write-Host $m; Add-Content -Path $rapor -Value $m -Encoding UTF8 }
function Bas($b) { Yaz ""; Yaz "=== $b ===" }
function Kisalt($s, $n) { if ($null -eq $s) { return "" }; if ($s.Length -gt $n) { return $s.Substring(0, $n) + "..." } else { return $s } }

Bas "1) BELLEK"
$os = Get-CimInstance Win32_OperatingSystem
$toplam = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1); $bos = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Yaz ("RAM: {0} GB toplam, {1} GB bos (%{2} dolu)" -f $toplam, $bos, [math]::Round(100 * (1 - $bos / $toplam)))

Bas "2) EN COK BELLEK KULLANAN 12 ISLEM"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 12 |
    ForEach-Object { Yaz ("{0,-26} PID {1,-7} {2,8} MB   CPU {3}" -f $_.ProcessName, $_.Id, [math]::Round($_.WorkingSet64 / 1MB), [math]::Round($_.CPU)) }

Bas "3) PYTHON / NODE / FFMPEG ISLEMLERI (komut satiriyla)"
Get-CimInstance Win32_Process | Where-Object { $_.Name -match "^(python|pythonw|node|ffmpeg)\.exe$" } |
    ForEach-Object {
        $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        $mb = if ($p) { [math]::Round($p.WorkingSet64 / 1MB) } else { 0 }
        Yaz ("PID {0,-7} {1,-12} {2,6} MB  {3}" -f $_.ProcessId, $_.Name, $mb, (Kisalt $_.CommandLine 150))
    }

Bas "4) CHROME"
$ch = Get-Process chrome -ErrorAction SilentlyContinue
if ($ch) { Yaz ("Chrome: {0} islem, toplam {1} MB" -f $ch.Count, [math]::Round(($ch | Measure-Object WorkingSet64 -Sum).Sum / 1MB)) } else { Yaz "Chrome calismiyor" }

Bas "5) GPU (nvidia-smi varsa)"
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    (& nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader) | ForEach-Object { Yaz $_ }
    (& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader) | ForEach-Object { Yaz ("GPU uygulamasi: " + $_) }
} else { Yaz "nvidia-smi bulunamadi (NVIDIA degil ya da PATH'te yok)" }

Bas "6) DINLEYEN BILINEN PORTLAR (kim tutuyor)"
$portlar = @{ 8123 = "ana Aura ses sunucusu"; 8124 = "Sign Council ses sunucusu"; 8790 = "canli yayin paneli"; 8791 = "telefon komuta paneli";
              8795 = "Aura Influencer (baska proje)"; 8796 = "Karar Merkezi"; 8800 = "Mission Control" }
foreach ($k in ($portlar.Keys | Sort-Object)) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $k -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { $pr = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
              Yaz ("{0}  ACIK  PID {1} {2,-10} {3} MB   ({4})" -f $k, $c.OwningProcess, $pr.ProcessName, [math]::Round($pr.WorkingSet64 / 1MB), $portlar[$k]) }
    else { Yaz ("{0}  bos    ({1})" -f $k, $portlar[$k]) }
}

Bas "7) ZAMANLANMIS GOREVLER (Sign / Aura / Council)"
Get-ScheduledTask | Where-Object { $_.TaskName -match "Sign|Aura|Council" } |
    ForEach-Object { $i = Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath
                     Yaz ("{0,-26} {1,-9} son: {2}  sonuc: {3}  sonraki: {4}" -f $_.TaskName, $_.State, $i.LastRunTime, $i.LastTaskResult, $i.NextRunTime) }

Bas "8) WINDOWS ILE ACILAN PROGRAMLAR"
Get-CimInstance Win32_StartupCommand | ForEach-Object { Yaz ("{0,-30} {1}" -f (Kisalt $_.Name 30), (Kisalt $_.Command 110)) }

Bas "9) DISK"
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } |
    ForEach-Object { Yaz ("{0}: {1} GB bos / {2} GB toplam" -f $_.Name, [math]::Round($_.Free / 1GB), [math]::Round(($_.Used + $_.Free) / 1GB)) }

Bas "10) council-backend EN BUYUK KLASORLER (ilk 12)"
Get-ChildItem -Directory -Force | ForEach-Object {
    $s = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    [pscustomobject]@{ Ad = $_.Name; MB = [math]::Round($s / 1MB) }
} | Sort-Object MB -Descending | Select-Object -First 12 | ForEach-Object { Yaz ("{0,-28} {1,8} MB" -f $_.Ad, $_.MB) }

Bas "11) DOSYA SAYILARI"
$tn = (Get-ChildItem "assets\thumbnails" -File -ErrorAction SilentlyContinue | Measure-Object).Count
Yaz "assets\thumbnails dosya sayisi: $tn"
$gunler = (Get-ChildItem "_engine" -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
Yaz "_engine alt klasor sayisi: $gunler"
$out = (Get-ChildItem "output" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
Yaz "output dosya sayisi: $out"

Bas "12) GIT (cok sayida izlenmeyen dosya git/IDE'yi yavaslatir)"
$st = git status --porcelain 2>$null
$n = ($st | Measure-Object).Count
$u = ($st | Where-Object { $_ -like "??*" } | Measure-Object).Count
Yaz "git status satiri: $n  (izlenmeyen: $u)"

Yaz ""
Yaz "Rapor dosyasi: $rapor"
Yaz "Bu ciktiyi Claude'a yapistir. Hicbir sey kapatilmadi."
