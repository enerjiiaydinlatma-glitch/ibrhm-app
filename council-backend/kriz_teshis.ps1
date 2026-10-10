# KRIZ TESHIS - ekran kararmasi / donma / cokme icin KANIT toplar. SALT OKUNUR: hicbir sey kapatmaz, silmez, degistirmez.
# Kullanim:  powershell -ExecutionPolicy Bypass -File .\kriz_teshis.ps1
# Cikti: ekrana + _kriz_teshis_<tarih>.txt  (dosyanin icerigini yeni sohbete yapistir)
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$out = Join-Path $PSScriptRoot ("_kriz_teshis_" + $stamp + ".txt")
function Yaz($m) { Write-Host $m; Add-Content -Path $out -Value $m -Encoding UTF8 }
function Baslik($m) { Yaz ""; Yaz ("=== " + $m + " ===") }
Set-Content -Path $out -Value ("KRIZ TESHIS " + (Get-Date)) -Encoding UTF8

Baslik "1) SON 3 GUNDE KRITIK OLAYLAR (ekran/surucu/donanim/kapanma)"
$bas = (Get-Date).AddDays(-3)
$filtreler = @(
  @{ Ad = "Ekran surucusu yanit vermedi/yeniden basladi (nvlddmkm/Display 4101)"; F = @{ LogName = "System"; ProviderName = "Display"; StartTime = $bas } },
  @{ Ad = "Beklenmeyen kapanma (Kernel-Power 41)"; F = @{ LogName = "System"; ProviderName = "Microsoft-Windows-Kernel-Power"; Id = 41; StartTime = $bas } },
  @{ Ad = "Mavi ekran kaydi (BugCheck 1001)"; F = @{ LogName = "System"; ProviderName = "Microsoft-Windows-WER-SystemErrorReporting"; StartTime = $bas } },
  @{ Ad = "Donanim hatasi (WHEA-Logger)"; F = @{ LogName = "System"; ProviderName = "Microsoft-Windows-WHEA-Logger"; StartTime = $bas } },
  @{ Ad = "Beklenmeyen kapanma (EventLog 6008)"; F = @{ LogName = "System"; ProviderName = "EventLog"; Id = 6008; StartTime = $bas } },
  @{ Ad = "Disk hatalari (disk/ntfs/volmgr)"; F = @{ LogName = "System"; ProviderName = @("disk","Ntfs","volmgr","stornvme"); Level = @(1,2,3); StartTime = $bas } },
  @{ Ad = "Uygulama cokmeleri/donmalari (1000/1002)"; F = @{ LogName = "Application"; Id = @(1000,1002); StartTime = $bas } }
)
foreach ($f in $filtreler) {
  Yaz ("--- " + $f.Ad)
  try {
    $ev = Get-WinEvent -FilterHashtable $f.F -MaxEvents 8 -ErrorAction Stop
    foreach ($e in $ev) {
      $msg = ($e.Message -replace "\s+", " ")
      if ($msg.Length -gt 230) { $msg = $msg.Substring(0, 230) }
      Yaz ("  " + $e.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss") + "  Id=" + $e.Id + "  " + $msg)
    }
  } catch { Yaz "  (kayit yok / okunamadi)" }
}

Baslik "2) EKRAN KARTI VE SURUCU"
try {
  Get-CimInstance Win32_VideoController | ForEach-Object {
    Yaz ("  " + $_.Name + " | surucu " + $_.DriverVersion + " | tarih " + $_.DriverDate + " | durum " + $_.Status + " | cozunurluk " + $_.CurrentHorizontalResolution + "x" + $_.CurrentVerticalResolution)
  }
} catch { Yaz "  (okunamadi)" }
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
  Yaz "--- nvidia-smi (sicaklik, bellek, guc, kisitlama)"
  try { & nvidia-smi --query-gpu=name,driver_version,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,clocks_throttle_reasons.active --format=csv 2>&1 | ForEach-Object { Yaz ("  " + $_) } } catch { Yaz "  (hata)" }
  try { & nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>&1 | ForEach-Object { Yaz ("  " + $_) } } catch { }
} else { Yaz "  nvidia-smi bulunamadi" }

Baslik "3) BELLEK / DISK"
try {
  $os = Get-CimInstance Win32_OperatingSystem
  $top = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1); $bos = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
  Yaz ("  RAM: " + $top + " GB toplam, " + $bos + " GB bos")
  Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { Yaz ("  Disk " + $_.DeviceID + " bos " + [math]::Round($_.FreeSpace / 1GB, 1) + " GB / " + [math]::Round($_.Size / 1GB, 1) + " GB") }
} catch { Yaz "  (okunamadi)" }

Baslik "4) EN COK KAYNAK KULLANAN ISLEMLER"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 12 | ForEach-Object { Yaz ("  " + $_.ProcessName.PadRight(26) + " PID " + $_.Id.ToString().PadRight(7) + [math]::Round($_.WorkingSet64 / 1MB) + " MB") }

Baslik "5) PYTHON / WEBVIEW / SES SUNUCUSU ISLEMLERI (komut satiriyla)"
try {
  Get-CimInstance Win32_Process | Where-Object { $_.Name -match "python|pythonw|msedgewebview2|cloudflared|node|ffmpeg" } | ForEach-Object {
    $c = $_.CommandLine; if ($c -and $c.Length -gt 200) { $c = $c.Substring(0, 200) }
    Yaz ("  PID " + $_.ProcessId + "  " + $_.Name + "  " + $c)
  }
} catch { Yaz "  (okunamadi)" }

Baslik "6) BILINEN PORTLARI KIM TUTUYOR"
foreach ($p in 8123, 8124, 8795, 8800, 8765, 8766) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($c) { foreach ($x in $c) { $pr = Get-Process -Id $x.OwningProcess -ErrorAction SilentlyContinue; Yaz ("  :" + $p + "  ACIK  PID " + $x.OwningProcess + "  " + $pr.ProcessName + "  baslangic " + $pr.StartTime) } }
  else { Yaz ("  :" + $p + "  bos") }
}

Baslik "7) WINDOWS DEFENDER (zararli yazilim kontrolu)"
try {
  $d = Get-MpComputerStatus
  Yaz ("  Gercek zamanli koruma: " + $d.RealTimeProtectionEnabled + " | imza guncelleme: " + $d.AntivirusSignatureLastUpdated + " | son hizli tarama: " + $d.QuickScanEndTime)
} catch { Yaz "  (Defender durumu okunamadi)" }
try {
  $t = Get-MpThreatDetection | Sort-Object InitialDetectionTime -Descending | Select-Object -First 10
  if ($t) { foreach ($x in $t) { Yaz ("  TESPIT " + $x.InitialDetectionTime + "  ThreatID " + $x.ThreatID + "  " + (($x.Resources) -join "; ")) } } else { Yaz "  Kayitli tehdit tespiti yok" }
} catch { Yaz "  (tehdit gecmisi okunamadi)" }

Baslik "8) WINDOWS ILE ACILANLAR VE ZAMANLANMIS GOREVLER (Microsoft disi)"
try {
  Get-CimInstance Win32_StartupCommand | ForEach-Object { Yaz ("  BASLANGIC  " + $_.Name + "  ->  " + $_.Command) }
} catch { Yaz "  (okunamadi)" }
try {
  Get-ScheduledTask | Where-Object { $_.TaskPath -notmatch "Microsoft" } | ForEach-Object {
    $i = Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath -ErrorAction SilentlyContinue
    Yaz ("  GOREV  " + $_.TaskName + "  durum " + $_.State + "  son " + $i.LastRunTime + "  sonuc " + $i.LastTaskResult)
  }
} catch { Yaz "  (okunamadi)" }

Baslik "9) SON 3 GUNDE DEGISEN DOSYALAR (council-backend, yalniz kod/ayar; isimler)"
try {
  Get-ChildItem -Path $PSScriptRoot -File -Include *.py,*.bat,*.ps1,*.json,*.md -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-3) -and $_.FullName -notmatch "_arsiv|__pycache__|output|assets" } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 40 | ForEach-Object { Yaz ("  " + $_.LastWriteTime.ToString("MM-dd HH:mm") + "  " + $_.Name) }
} catch { Yaz "  (okunamadi)" }

Baslik "10) GIT DURUMU"
try { Yaz ("  dal: " + (git rev-parse --abbrev-ref HEAD)); git log --oneline -3 | ForEach-Object { Yaz ("  " + $_) }; Yaz "  --- git status (izlenen dosyalardaki degisiklikler)"; git status --short --untracked-files=no | ForEach-Object { Yaz ("  " + $_) } } catch { Yaz "  (git okunamadi)" }

Yaz ""
Yaz ("TAMAM. Rapor dosyasi: " + $out)
Yaz "Bu dosyanin icerigini yeni sohbete yapistir. Hicbir sey kapatilmadi/silinmedi."
