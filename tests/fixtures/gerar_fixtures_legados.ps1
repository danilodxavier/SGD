# Gera os arquivos FICTÍCIOS usados em tests\test_legacy.py, salvos pelo próprio Microsoft Office
# (Word, Excel e PowerPoint via COM). Só é necessário para recriar as fixtures; os testes não usam o Office.
#   powershell -NoProfile -File tests\fixtures\gerar_fixtures_legados.ps1 -App word -WordFormat 0   (DOC)
#   ... -App word -WordFormat 6 (RTF) | -App word -WordFormat 23 (ODT) | -App word -Password senha123
#   ... -App excel | -App powerpoint
# Observação: o conteúdo é editado por Range (não por Selection), o que funciona mesmo com o Office em
# modo de funcionalidade reduzida.
param([ValidateSet('word', 'excel', 'powerpoint')][string]$App, [int]$WordFormat = 0, [string]$Password)
$ErrorActionPreference = 'Stop'
$final = Join-Path $PSScriptRoot 'legados'
New-Item -ItemType Directory -Force $final | Out-Null
# o Office salva numa pasta temporária (sem espaços no caminho) e os arquivos são copiados ao final
$out = Join-Path $env:TEMP ('fixtures_office_' + $App)
New-Item -ItemType Directory -Force $out | Out-Null

if ($App -eq 'word') {
    # Cada formato é salvo em um processo separado do Word (-WordFormat): com o Office em modo de
    # funcionalidade reduzida, salvar vários formatos na mesma sessão pode travar.
    $name = @{ 0 = 'contrato_legado.doc'; 6 = 'contrato_legado.rtf'; 23 = 'contrato_legado.odt' }[$WordFormat]
    if ($Password) { $name = 'protegido.doc' }
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {
        $doc = $word.Documents.Add()
        $doc.Content.Text = (@(
            'CONTRATO Nº 077/2021',
            'PROCESSO Nº 23188.000777/2021-07',
            'O INSTITUTO FEDERAL DE EXEMPLO e a empresa GAMA CLIMATIZAÇÃO LTDA, inscrita no CNPJ sob o nº 11.222.333/0001-81, doravante denominada CONTRATADA, celebram o presente contrato.',
            'CLÁUSULA PRIMEIRA – DO OBJETO',
            '1.1. O presente contrato tem por objeto a manutenção preventiva e corretiva de aparelhos de ar-condicionado.',
            'CLÁUSULA SEGUNDA – DA VIGÊNCIA E DO VALOR',
            '2.1. A vigência será de 12 (doze) meses, com início em 01/04/2021 e término em 31/03/2022.',
            '2.2. O valor global do contrato é de R$ 45.600,00 (quarenta e cinco mil e seiscentos reais).',
            'Cuiabá-MT, 25 de março de 2021.'
        ) -join "`r")
        $end = $doc.Content; $end.Collapse(0)
        $table = $doc.Tables.Add($end, 3, 4)
        $cells = @(@('Item', 'Descrição', 'Quantidade', 'Valor Unitário'),
                   @('1', 'Manutenção preventiva mensal', '12', '2.800,00'),
                   @('2', 'Recarga de gás refrigerante', '20', '600,00'))
        for ($r = 0; $r -lt 3; $r++) { for ($c = 0; $c -lt 4; $c++) { $table.Cell($r + 1, $c + 1).Range.Text = $cells[$r][$c] } }
        $end = $doc.Content; $end.Collapse(0)
        $null = $doc.Hyperlinks.Add($end, 'https://exemplo.gov.br/contratos', '', '', 'Portal de Contratos')
        $target = Join-Path $out $name
        if ($Password) { $doc.SaveAs2($target, 0, $false, $Password) } else { $doc.SaveAs2($target, $WordFormat) }
        $doc.Close(0)
    } finally { $word.Quit() }
}

if ($App -eq 'excel') {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    try {
        $wb = $excel.Workbooks.Add()
        $ws = $wb.Worksheets.Item(1)
        $ws.Name = 'Itens'
        $ws.Range('A1').Value2 = 'Planilha de itens do Contrato 077/2021'
        $rows = @(@('Item', 'Descrição', 'Unidade', 'Quantidade', 'Valor Unitário', 'Valor Total'),
                  @(1, 'Manutenção preventiva mensal', 'serviço', 12, 2800, 33600),
                  @(2, 'Recarga de gás refrigerante', 'unidade', 20, 600, 12000))
        for ($r = 0; $r -lt 3; $r++) { for ($c = 0; $c -lt 6; $c++) {
            $v = $rows[$r][$c]
            $cell = $ws.Cells.Item($r + 3, $c + 1)
            if ($v -is [int]) { $cell.Value2 = [double]$v } else { $cell.Value2 = [string]$v }
        } }
        $ws.Range('A7').Value2 = 'Data de referência'
        $ws.Range('B7').Formula = '=DATE(2021,4,1)'
        $ws.Range('B7').NumberFormat = 'dd/mm/yyyy'
        $ws2 = $wb.Worksheets.Add([Type]::Missing, $ws)
        $ws2.Name = 'Observações'
        $ws2.Range('A1').Value2 = 'Fiscalização exercida conforme portaria.'
        $wb.CheckCompatibility = $false
        $wb.SaveAs((Join-Path $out 'planilha_legada.xls'), 56)          # Excel 97-2003
        $wb.SaveAs((Join-Path $out 'planilha_legada.ods'), 60)          # OpenDocument
        $wb.SaveAs((Join-Path $out 'protegido.xls'), 56, 'senha123')    # senha de abertura
        $wb.Close($false)
    } finally { $excel.Quit() }
}

if ($App -eq 'powerpoint') {
    $ppt = New-Object -ComObject PowerPoint.Application
    try {
        $pres = $ppt.Presentations.Add(0)  # sem janela
        $s1 = $pres.Slides.Add(1, 1)
        $s1.Shapes.Item(1).TextFrame.TextRange.Text = 'Relatório de Fiscalização'
        $s1.Shapes.Item(2).TextFrame.TextRange.Text = 'Contrato nº 077/2021 – manutenção de ar-condicionado'
        $s2 = $pres.Slides.Add(2, 2)
        $s2.Shapes.Item(1).TextFrame.TextRange.Text = 'Ocorrências do período'
        $s2.Shapes.Item(2).TextFrame.TextRange.Text = "Atraso na recarga de gás em 15/06/2021`rNotificação enviada à contratada"
        $box = $s2.Shapes.AddTextbox(1, 50, 400, 500, 40)
        $box.TextFrame.TextRange.Text = 'Fiscal: servidor fictício de exemplo'
        $pres.SaveAs((Join-Path $out 'apresentacao_legada.ppt'), 1)     # PowerPoint 97-2003
        $pres.SaveAs((Join-Path $out 'apresentacao.pptx'), 24)          # PowerPoint 2007+
        $pres.Close()
    } finally { $ppt.Quit() }
}

Get-ChildItem $out -File | Copy-Item -Destination $final -Force
Remove-Item $out -Recurse -Force
