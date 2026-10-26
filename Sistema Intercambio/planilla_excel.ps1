# planilla_excel.ps1 -- Escribe en la Planilla de Ingreso de Requerimientos con
# el mismo Excel que usa el equipo (COM), nunca con openpyxl: así se conservan
# la tabla «Proyectos», las validaciones, el formato condicional y lo que
# openpyxl borra (xl/metadata.xml, xl/richData; ver requerimientos.py).
#
# Lo llama planilla_escritura.py:
#   powershell -NoProfile -File planilla_excel.ps1 -Entrada <json> -Salida <json>
# Entrada: { ruta, hoja, tabla, operaciones: [...] }. Cada operación:
#   { op: "fijar", fila, titulo, numero }   el N° de esa fila pasa de fórmula a número fijo.
#       La fila se confirma por su título (columna F); si ya no calza (alguien la movió), se busca
#       ese título en la tabla y se usa solo si aparece una vez.
#   { op: "nueva", numero, valores: { "B": "...", ... }, fechas: { "I": "AAAA-MM-DD" } }
#       una fila al final de la lista (la primera vacía de la tabla, o una nueva), con el N° fijo.
#       Si ese N° ya está en la columna A, no se escribe nada.
# Salida: { estado: "ok"|"ocupada"|"error", detalle, resultados: [{ i, ok, fila, detalle }] }.

param([Parameter(Mandatory = $true)][string]$Entrada, [Parameter(Mandatory = $true)][string]$Salida)

$ErrorActionPreference = 'Stop'
Add-Type -Namespace QuempinPlanilla -Name Win -MemberDefinition '[DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int pid);'

function Escribir-Salida($obj) {
    $json = $obj | ConvertTo-Json -Depth 6 -Compress
    [System.IO.File]::WriteAllText($Salida, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function Texto($v) { if ($null -eq $v) { '' } else { ([string]$v).Trim() } }

$pedido = [System.IO.File]::ReadAllText($Entrada, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$resultados = New-Object System.Collections.ArrayList
$xl = $null; $wb = $null; $pidExcel = 0
try {
    $xl = New-Object -ComObject Excel.Application
    [void][QuempinPlanilla.Win]::GetWindowThreadProcessId([IntPtr]$xl.Hwnd, [ref]$pidExcel)
    $xl.Visible = $false
    $xl.DisplayAlerts = $false
    $xl.AskToUpdateLinks = $false
    $xl.EnableEvents = $false
    $wb = $xl.Workbooks.Open($pedido.ruta, 0, $false)
    # Un archivo de OneDrive se abre como el documento de SharePoint (coautoría) y Open puede volver antes
    # de que el libro esté listo: se espera a que esté en la lista de libros abiertos y tenga sus hojas
    $nombre = [System.IO.Path]::GetFileName($pedido.ruta)
    $listo = $false
    for ($t = 0; -not $listo -and $t -lt 120; $t++) {
        foreach ($w in $xl.Workbooks) { if ($w.Name -eq $nombre) { $wb = $w } }
        try { $listo = $wb -and $wb.Worksheets -and $wb.Worksheets.Count -gt 0 } catch { $listo = $false }
        if (-not $listo) { Start-Sleep -Milliseconds 500 }
    }
    if (-not $listo) { throw "Excel no abrió la planilla en 60 segundos" }
    if ($wb.ReadOnly) {
        Escribir-Salida @{ estado = 'ocupada'; detalle = 'La planilla se abrió solo para lectura: alguien la tiene abierta sin coautoría.'; resultados = @() }
        return
    }
    $hoja = $wb.Worksheets.Item($pedido.hoja)
    $tabla = $hoja.ListObjects.Item($pedido.tabla)
    $primera = $tabla.Range.Row          # la fila de encabezados
    $ultima = $primera + $tabla.Range.Rows.Count - 1
    $datos = $hoja.Range("A$($primera):Q$($ultima)").Value2
    $alto = $ultima - $primera + 1
    function Celda($fila, $col) { $datos[($fila - $primera + 1), $col] }

    $i = -1
    foreach ($o in $pedido.operaciones) {
        $i++
        try {
            if ($o.op -eq 'fijar') {
                $fila = [int]$o.fila
                if ((Texto (Celda $fila 6)) -ne (Texto $o.titulo)) {
                    $hallas = @()
                    for ($k = 2; $k -le $alto; $k++) { if ((Texto $datos[$k, 6]) -eq (Texto $o.titulo)) { $hallas += ($primera + $k - 1) } }
                    if ($hallas.Count -ne 1) { [void]$resultados.Add(@{ i = $i; ok = $false; fila = $fila; detalle = "la fila $fila ya no es «$($o.titulo)» y ese título aparece $($hallas.Count) veces" }); continue }
                    $fila = $hallas[0]
                }
                $hoja.Cells.Item($fila, 1).Value2 = [double]$o.numero
                [void]$resultados.Add(@{ i = $i; ok = $true; fila = $fila; detalle = "N° $($o.numero) fijo" })
            }
            elseif ($o.op -eq 'nueva') {
                $numero = [double]$o.numero
                $ocupada = $false
                $ultimaLlena = $primera
                for ($k = 2; $k -le $alto; $k++) {
                    $a = $datos[$k, 1]
                    if ($a -is [double] -and $a -eq $numero) { $ocupada = $true }
                    if ((Texto $datos[$k, 2]) -ne '' -or (Texto $datos[$k, 6]) -ne '') { $ultimaLlena = $primera + $k - 1 }
                }
                if ($ocupada) { [void]$resultados.Add(@{ i = $i; ok = $false; fila = 0; detalle = "el N° $($o.numero) ya está en la planilla" }); continue }
                $fila = $ultimaLlena + 1
                if ($fila -gt $ultima) { [void]$tabla.ListRows.Add(); $ultima++ }
                $hoja.Cells.Item($fila, 1).Value2 = $numero
                foreach ($p in $o.valores.PSObject.Properties) {
                    $col = [int]$hoja.Range("$($p.Name)1").Column
                    # Texto y número en líneas distintas: PowerShell recuerda el tipo de la primera escritura de
                    # cada línea y la siguiente de otro tipo falla («la conversión especificada no es válida»)
                    $celda = $hoja.Cells.Item($fila, $col)
                    if ($p.Value -is [string]) { $celda.Value2 = [string]$p.Value }
                    else { $celda.Value2 = [double]$p.Value }
                }
                if ($o.fechas) {
                    foreach ($p in $o.fechas.PSObject.Properties) {
                        $col = [int]$hoja.Range("$($p.Name)1").Column
                        $celda = $hoja.Cells.Item($fila, $col)
                        # El formato de fecha de la última fila de arriba que tiene una fecha en esa columna
                        for ($k = $fila - 1; $k -gt $primera; $k--) {
                            $arriba = $hoja.Cells.Item($k, $col)
                            if ($arriba.Value2 -is [double] -and ([string]$arriba.NumberFormat) -match '[dmy]') { $celda.NumberFormat = $arriba.NumberFormat; break }
                        }
                        $formatos = [string[]]@('yyyy-MM-dd', "yyyy-MM-dd'T'HH:mm")
                        $celda.Value2 = ([datetime]::ParseExact([string]$p.Value, $formatos, [System.Globalization.CultureInfo]::InvariantCulture, 'None')).ToOADate()
                    }
                }
                [void]$resultados.Add(@{ i = $i; ok = $true; fila = $fila; detalle = "N° $($o.numero) en la fila $fila" })
            }
            else { [void]$resultados.Add(@{ i = $i; ok = $false; fila = 0; detalle = "operación desconocida: $($o.op)" }) }
        }
        catch { [void]$resultados.Add(@{ i = $i; ok = $false; fila = 0; detalle = "$($_.Exception.Message) (línea $($_.InvocationInfo.ScriptLineNumber))" }) }
    }
    if (@($resultados | Where-Object { $_.ok }).Count -gt 0) { $wb.Save() }
    Escribir-Salida @{ estado = 'ok'; detalle = ''; resultados = $resultados }
}
catch {
    Escribir-Salida @{ estado = 'error'; detalle = "$($_.Exception.Message) (línea $($_.InvocationInfo.ScriptLineNumber))"; resultados = $resultados }
}
finally {
    if ($wb) { try { $wb.Close($false) } catch {} ; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) }
    if ($xl) { try { $xl.Quit() } catch {} ; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    # Un Excel que no se cerró dejaría la planilla tomada
    if ($pidExcel) { Start-Sleep -Milliseconds 500; Get-Process -Id $pidExcel -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue }
}
