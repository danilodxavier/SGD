# OCR com o mecanismo nativo do Windows (Windows.Media.Ocr), executado localmente.
# Entrada (variáveis de ambiente):
#   AGENTE_OCR_LIST  arquivo texto com um caminho de imagem por linha (UTF-8)
#   AGENTE_OCR_OUT   arquivo JSON de saída
#   AGENTE_OCR_LANG  idioma (ex.: pt-BR)
#   AGENTE_OCR_PROBE se definido, apenas lista os idiomas disponíveis
# Não altera configurações do sistema; apenas lê as imagens indicadas.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($operation, [Type]$resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $null = $task.Wait(-1)
    return $task.Result
}

if ($env:AGENTE_OCR_PROBE) {
    $langs = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag })
    [Console]::Out.Write((ConvertTo-Json -InputObject $langs -Compress))
    exit 0
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($env:AGENTE_OCR_LANG))
if ($null -eq $engine) { throw ('Idioma de OCR indisponivel: ' + $env:AGENTE_OCR_LANG) }

$results = @()
foreach ($path in [System.IO.File]::ReadAllLines($env:AGENTE_OCR_LIST, [System.Text.Encoding]::UTF8)) {
    if (-not $path.Trim()) { continue }
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocr = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = @($ocr.Lines | ForEach-Object { $_.Text })
        $results += [pscustomobject]@{ path = $path; lines = $lines; error = $null }
        $stream.Dispose()
    } catch {
        $results += [pscustomobject]@{ path = $path; lines = @(); error = $_.Exception.Message }
    }
}
$json = ConvertTo-Json -InputObject @($results) -Depth 4
[System.IO.File]::WriteAllText($env:AGENTE_OCR_OUT, $json, (New-Object System.Text.UTF8Encoding $false))
