<#
.SYNOPSIS
  Shopify ürün CSV'sinden fiyat önizlemesi (önce/sonra) üretir.

.DESCRIPTION
  - Yalnızca YEREL dosyaları okur/yazar. İnternete bağlanmaz, siteyi değiştirmez.
  - Orijinal CSV'ye dokunmaz.
  - Varsayılan olarak sadece önizleme dosyası üretir. Siz onaylamadan
    içe aktarılacak CSV üretilmez (-ImportDosyasiOlustur gerekir).
  - Yalnızca "Variant Price" sütununu değiştirir. Kargo, Almanya pazarı
    (Shopify Markets) fiyatları ve diğer sütunlar olduğu gibi kalır.

.PARAMETER Girdi
  Shopify yönetim panelinden dışa aktarılan ürün CSV'si (Products > Export).

.PARAMETER ZamYuzdesi
  Tüm ürünlere uygulanacak yüzde. Örn: 15 -> %15 artış, -10 -> %10 indirim.

.PARAMETER FiyatListesi
  İsteğe bağlı. Başlıkları "Handle,YeniFiyat" olan CSV. Listedeki ürünlerin
  fiyatı doğrudan bu değerle değiştirilir; -ZamYuzdesi ile birlikte
  verilirse listede olmayan ürünlere yüzde uygulanır.

.PARAMETER Yuvarla
  Ondalık basamak sayısı (varsayılan 0 -> tam TL).

.PARAMETER ImportDosyasiOlustur
  Verilirse, Shopify'a içe aktarılabilecek yeni CSV de üretilir.
  Siz önizlemeyi onayladıktan sonra kullanın.

.EXAMPLE
  .\Fiyat-Onizleme.ps1 -Girdi .\products_export.csv -ZamYuzdesi 15

.EXAMPLE
  .\Fiyat-Onizleme.ps1 -Girdi .\products_export.csv -FiyatListesi .\yeni_fiyatlar.csv

.EXAMPLE
  .\Fiyat-Onizleme.ps1 -Girdi .\products_export.csv -ZamYuzdesi 15 -ImportDosyasiOlustur
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]  [string] $Girdi,
    [Parameter(Mandatory = $false)] [Nullable[double]] $ZamYuzdesi = $null,
    [Parameter(Mandatory = $false)] [string] $FiyatListesi,
    [Parameter(Mandatory = $false)] [int] $Yuvarla = 0,
    [Parameter(Mandatory = $false)] [switch] $ImportDosyasiOlustur
)

$ErrorActionPreference = 'Stop'
$inv = [System.Globalization.CultureInfo]::InvariantCulture

if ($null -eq $ZamYuzdesi -and -not $FiyatListesi) {
    throw "-ZamYuzdesi veya -FiyatListesi parametrelerinden en az biri gerekli."
}
if (-not (Test-Path -LiteralPath $Girdi)) { throw "Girdi dosyası bulunamadı: $Girdi" }

$satirlar = Import-Csv -LiteralPath $Girdi -Encoding UTF8
if (-not $satirlar) { throw "CSV boş." }

foreach ($kolon in 'Handle', 'Variant Price') {
    if ($satirlar[0].PSObject.Properties.Name -notcontains $kolon) {
        throw "CSV'de '$kolon' sütunu yok. Shopify ürün dışa aktarımı olduğundan emin olun."
    }
}

# Elle verilen fiyat listesi (Handle -> YeniFiyat)
$elleFiyat = @{}
if ($FiyatListesi) {
    foreach ($r in (Import-Csv -LiteralPath $FiyatListesi -Encoding UTF8)) {
        $deger = ($r.YeniFiyat -replace ',', '.').Trim()
        $elleFiyat[$r.Handle] = [double]::Parse($deger, $inv)
    }
}

$onizleme = New-Object System.Collections.Generic.List[object]
$uyarilar = New-Object System.Collections.Generic.List[string]

foreach ($s in $satirlar) {
    $eskiMetin = ($s.'Variant Price' -replace ',', '.').Trim()
    if ([string]::IsNullOrWhiteSpace($eskiMetin)) { continue }   # görsel satırı vb.

    $eski = [double]::Parse($eskiMetin, $inv)
    $yeni = $null

    if ($elleFiyat.ContainsKey($s.Handle)) {
        $yeni = $elleFiyat[$s.Handle]
    }
    elseif ($null -ne $ZamYuzdesi) {
        $yeni = $eski * (1 + ([double]$ZamYuzdesi / 100))
    }
    else {
        continue   # sadece liste verildi ve bu ürün listede yok
    }

    $yeni = [math]::Round($yeni, $Yuvarla, [MidpointRounding]::AwayFromZero)
    $fark = if ($eski -ne 0) { [math]::Round((($yeni - $eski) / $eski) * 100, 2) } else { 0 }

    # Karşılaştırma fiyatı yeni fiyattan düşük/eşit kalırsa uyar
    $ks = ($s.'Variant Compare At Price' -replace ',', '.').Trim()
    if ($ks -and ([double]::Parse($ks, $inv) -le $yeni)) {
        $uyarilar.Add("$($s.Handle): 'Compare At' ($ks) yeni fiyattan ($yeni) düşük/eşit; indirim etiketi bozulur.")
    }

    $onizleme.Add([pscustomobject]@{
        Handle      = $s.Handle
        Baslik      = $s.Title
        SKU         = $s.'Variant SKU'
        EskiFiyat   = $eski.ToString('0.00', $inv)
        YeniFiyat   = $yeni.ToString('0.00', $inv)
        FarkYuzde   = $fark
    })

    $s.'Variant Price' = $yeni.ToString('0.00', $inv)
}

if ($onizleme.Count -eq 0) { throw "Güncellenecek ürün bulunamadı." }

$zaman = Get-Date -Format 'yyyyMMdd-HHmmss'
$klasor = Split-Path -Parent (Resolve-Path -LiteralPath $Girdi)
$onizlemeDosya = Join-Path $klasor "fiyat_onizleme_$zaman.csv"
$onizleme | Export-Csv -LiteralPath $onizlemeDosya -NoTypeInformation -Encoding UTF8

$onizleme | Format-Table Handle, Baslik, EskiFiyat, YeniFiyat, FarkYuzde -AutoSize
Write-Host "`nÜrün/varyant sayısı : $($onizleme.Count)"
Write-Host "Önizleme dosyası     : $onizlemeDosya"
foreach ($u in $uyarilar) { Write-Warning $u }

if ($ImportDosyasiOlustur) {
    $importDosya = Join-Path $klasor "shopify_import_$zaman.csv"
    $satirlar | Export-Csv -LiteralPath $importDosya -NoTypeInformation -Encoding UTF8
    Write-Host "Import dosyası       : $importDosya"
    Write-Host "Not: Shopify > Products > Import ekranında 'Overwrite existing products' seçeneğini kullanın."
    Write-Host "     Bu betik siteye hiçbir şey göndermedi; yüklemeyi siz yapacaksınız."
}
else {
    Write-Host "`nSite DEĞİŞTİRİLMEDİ. Önizlemeyi onaylarsanız aynı komuta -ImportDosyasiOlustur ekleyin."
}
