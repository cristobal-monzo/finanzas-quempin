# planilla_excel.ps1 -- Escribe en la Planilla de Ingreso de Requerimientos con
# el mismo Excel que usa el equipo (COM), nunca con openpyxl: así se conservan
# la tabla «Proyectos», las validaciones, el formato condicional y lo que
# openpyxl borra (xl/metadata.xml, xl/richData; ver requerimientos.py).
#
# Lo llama planilla_escritura.py:
#   powershell -NoProfile -File planilla_excel.ps1 -Entrada <json> -Salida <json>
# Entrada: { ruta, hoja, tabla, columnaTitulo: "F", operaciones: [...] }. Cada operación:
#   { op: "fijar", fila, titulo, numero }   el N° de esa fila pasa de fórmula a número fijo.
#       La fila se confirma por su título; si ya no calza (alguien la movió), se busca
#       ese título en la tabla y se usa solo si aparece una vez.
#   { op: "nueva", numero, valores: { "B": "...", ... }, fechas: { "J": "AAAA-MM-DD" }, encabezados: { "B": "Estado" } }
#       una fila al final de la lista (la primera vacía de la tabla, o una nueva), con el N° fijo.
#       Si ese N° ya está en la columna A, no se escribe nada.
#   { op: "editar", numero, titulo, tituloNuevo?, valores, fechas, borrar: ["H"], encabezados }
#       las casillas cambiadas en el Portal, en la fila de ese N° cuyo título es «titulo» (o ya «tituloNuevo»).
#   { op: "estados", lista: ["Evaluación", ...], letra: "B", encabezados: { "B": "Estado" } }
#       la lista desplegable de la columna Estado, el color de «Cerrado» y su línea en el Glosario (2026-11-09).
#       Una sola vez: ya hecha, deja todo igual.
# Las letras las calcula planilla_escritura.py por el encabezado; «encabezados» dice cuál esperaba en cada
# letra, y si alguien movió una columna entretanto la operación no se escribe (se reintenta).
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
    $datos = $tabla.Range.Value2         # [fila de la tabla (1 = encabezados), columna]
    $alto = $ultima - $primera + 1
    $colT = if ($pedido.columnaTitulo) { [int]$hoja.Range("$($pedido.columnaTitulo)1").Column } else { 6 }
    function Celda($fila, $col) { $datos[($fila - $primera + 1), $col] }
    function Columna($letra) { [int]$hoja.Range("$($letra)1").Column }
    # La protección de una hoja tal como está (sin contraseña), para dejarla igual después de quitarla: con los mismos
    # permisos de ordenar, filtrar o dar formato que el equipo le haya dado. Mismo orden que Worksheet.Protect.
    function Proteccion-De($h) {
        $p = $h.Protection
        , @($h.ProtectDrawingObjects, $h.ProtectContents, $h.ProtectScenarios, $false,
            $p.AllowFormattingCells, $p.AllowFormattingColumns, $p.AllowFormattingRows, $p.AllowInsertingColumns,
            $p.AllowInsertingRows, $p.AllowInsertingHyperlinks, $p.AllowDeletingColumns, $p.AllowDeletingRows,
            $p.AllowSorting, $p.AllowFiltering, $p.AllowUsingPivotTables)
    }
    function Proteger-Como($h, $c) {
        [void]$h.Protect([Type]::Missing, $c[0], $c[1], $c[2], $c[3], $c[4], $c[5], $c[6], $c[7], $c[8], $c[9], $c[10], $c[11], $c[12], $c[13], $c[14])
    }

    # Cada letra todavía tiene el encabezado con que se calculó (nadie movió la columna entretanto)
    function Revisar-Encabezados($o) {
        if (-not $o.encabezados) { return }
        foreach ($p in $o.encabezados.PSObject.Properties) {
            $hay = Texto $hoja.Cells.Item($primera, (Columna $p.Name)).Value2
            if ($hay -ne (Texto $p.Value)) { throw "la columna $($p.Name) ya no es «$($p.Value)» (dice «$hay»)" }
        }
    }
    function Escribir-Valores($fila, $o) {
        if ($o.valores) {
            foreach ($p in $o.valores.PSObject.Properties) {
                # Texto y número en líneas distintas: PowerShell recuerda el tipo de la primera escritura de
                # cada línea y la siguiente de otro tipo falla («la conversión especificada no es válida»)
                $celda = $hoja.Cells.Item($fila, (Columna $p.Name))
                if ($p.Value -is [string]) { $celda.Value2 = [string]$p.Value }
                else { $celda.Value2 = [double]$p.Value }
            }
        }
        if ($o.fechas) {
            foreach ($p in $o.fechas.PSObject.Properties) {
                $col = Columna $p.Name
                $celda = $hoja.Cells.Item($fila, $col)
                # El formato de fecha de la última fila de arriba que tiene una fecha en esa columna
                for ($k = $fila - 1; $k -gt $primera; $k--) {
                    $arriba = $hoja.Cells.Item($k, $col)
                    # Con la hoja protegida no se puede dar formato (2026-11-06): la columna ya lo trae
                    if ($arriba.Value2 -is [double] -and ([string]$arriba.NumberFormat) -match '[dmy]') { try { $celda.NumberFormat = $arriba.NumberFormat } catch { }; break }
                }
                $formatos = [string[]]@('yyyy-MM-dd', "yyyy-MM-dd'T'HH:mm")
                $fecha = [datetime]::ParseExact([string]$p.Value, $formatos, [System.Globalization.CultureInfo]::InvariantCulture, 'None')
                # Como fecha (Value) y no como número de serie (Value2): Excel le pone formato de fecha aunque la
                # hoja esté protegida y no deje dar formato (2026-11-06: la fila nueva mostraba «46321»)
                if (([string]$celda.NumberFormat) -match '[dmy]') { $celda.Value2 = $fecha.ToOADate() } else { $celda.Value = $fecha }
            }
        }
        if ($o.borrar) {
            foreach ($letra in $o.borrar) { [void]$hoja.Cells.Item($fila, (Columna $letra)).ClearContents() }
        }
    }

    $i = -1
    foreach ($o in $pedido.operaciones) {
        $i++
        try {
            if ($o.op -eq 'fijar') {
                $fila = [int]$o.fila
                if ((Texto (Celda $fila $colT)) -ne (Texto $o.titulo)) {
                    $hallas = @()
                    for ($k = 2; $k -le $alto; $k++) { if ((Texto $datos[$k, $colT]) -eq (Texto $o.titulo)) { $hallas += ($primera + $k - 1) } }
                    if ($hallas.Count -ne 1) { [void]$resultados.Add(@{ i = $i; ok = $false; fila = $fila; detalle = "la fila $fila ya no es «$($o.titulo)» y ese título aparece $($hallas.Count) veces" }); continue }
                    $fila = $hallas[0]
                }
                $hoja.Cells.Item($fila, 1).Value2 = [double]$o.numero
                [void]$resultados.Add(@{ i = $i; ok = $true; fila = $fila; detalle = "N° $($o.numero) fijo" })
            }
            elseif ($o.op -eq 'nueva') {
                Revisar-Encabezados $o
                $numero = [double]$o.numero
                $ocupada = $false
                $ultimoN = 1
                for ($k = 2; $k -le $alto; $k++) {
                    $a = $datos[$k, 1]
                    if ($a -is [double] -and $a -eq $numero) { $ocupada = $true }
                    if ($a -is [double] -and $a -ge 1) { $ultimoN = $k }
                }
                if ($ocupada) { [void]$resultados.Add(@{ i = $i; ok = $false; fila = 0; detalle = "el N° $($o.numero) ya está en la planilla" }); continue }
                # La primera fila vacía después del último N° (al fondo de la tabla pueden quedar filas sin N°
                # de un orden antiguo: el 2026-10-29 había dos de enero en las filas 1995 y 1996)
                $k = $ultimoN + 1
                while ($k -le $alto -and ((Texto $datos[$k, 2]) -ne '' -or (Texto $datos[$k, $colT]) -ne '' -or $datos[$k, 1] -is [double])) { $k++ }
                if ($k -gt $alto) { [void]$tabla.ListRows.Add(); $ultima++; $fila = $ultima }
                else {
                    $fila = $primera + $k - 1
                    $datos[$k, 1] = $numero      # la siguiente fila nueva de esta vuelta va debajo
                }
                # El N° lo pone la fórmula de la columna (protegida desde el 2026-11-03): no se escribe (2026-11-06)
                Escribir-Valores $fila $o
                try { $hoja.Calculate() } catch { }
                $real = $hoja.Cells.Item($fila, 1).Value2
                if (-not ($real -is [double])) { $real = $null }
                if ($o.exigeNumero -and ($null -eq $real -or $real -ne $numero)) {
                    # Su carpeta y su código ya llevan el N° pedido: se deshace la fila y lo decide una persona
                    $letras = @()
                    if ($o.valores) { $letras += @($o.valores.PSObject.Properties | ForEach-Object { $_.Name }) }
                    if ($o.fechas) { $letras += @($o.fechas.PSObject.Properties | ForEach-Object { $_.Name }) }
                    foreach ($letra in $letras) { [void]$hoja.Cells.Item($fila, (Columna $letra)).ClearContents() }
                    $dio = if ($null -eq $real) { 'ninguno' } else { [string][int]$real }
                    [void]$resultados.Add(@{ i = $i; ok = $false; fila = $fila; detalle = "la fórmula de la Planilla le daba el N° $dio, no el $($o.numero): no se escribió" })
                    continue
                }
                $n = if ($null -eq $real) { $numero } else { $real }
                [void]$resultados.Add(@{ i = $i; ok = $true; fila = $fila; numero = $n; detalle = "N° $n en la fila $fila" })
            }
            elseif ($o.op -eq 'editar') {
                Revisar-Encabezados $o
                $numero = [double]$o.numero
                $titulos = @((Texto $o.titulo), (Texto $o.tituloNuevo)) | Where-Object { $_ -ne '' }
                $hallas = @()
                for ($k = 2; $k -le $alto; $k++) {
                    $a = $datos[$k, 1]
                    if ($a -is [double] -and $a -eq $numero -and ($titulos -contains (Texto $datos[$k, $colT]))) { $hallas += $k }
                }
                if ($hallas.Count -ne 1) { [void]$resultados.Add(@{ i = $i; ok = $false; fila = 0; detalle = "el N° $($o.numero) con título «$($o.titulo)» aparece $($hallas.Count) veces" }); continue }
                $fila = $primera + $hallas[0] - 1
                Escribir-Valores $fila $o
                # Otro cambio a la misma fila en esta vuelta la busca ya con su título nuevo
                if ($o.tituloNuevo) { $datos[$hallas[0], $colT] = [string]$o.tituloNuevo }
                [void]$resultados.Add(@{ i = $i; ok = $true; fila = $fila; detalle = "N° $($o.numero) cambiado en la fila $fila" })
            }
            elseif ($o.op -eq 'estados') {
                Revisar-Encabezados $o
                $col = Columna $o.letra
                # La hoja está protegida sin contraseña. Con la protección puesta, Validation.Delete funciona y Validation.Add
                # no: borraría la lista y no podría reponerla (visto el 2026-11-02 en una copia). Se quita solo para esto y
                # vuelve exactamente como estaba, con los mismos permisos (ordenar, filtrar, dar formato...).
                $protegida = [bool]$hoja.ProtectContents
                $como = Proteccion-De $hoja
                if ($protegida) { [void]$hoja.Unprotect() }
                try {
                    # Las mismas celdas que ya tienen validación en esa columna (medido: B4:B287 y B289 hasta el final de la
                    # hoja); sin ninguna, desde la primera fila de datos hasta el final. SpecialCells no corre en hoja protegida.
                    $desde = $hoja.Range($hoja.Cells.Item($primera + 1, $col), $hoja.Cells.Item($hoja.Rows.Count, $col))
                    $rango = $desde
                    # Por .Application: llamado directo, PowerShell no encuentra la sobrecarga de 2 argumentos (visto el 2026-11-09)
                    try { $rango = $xl.Application.Intersect($hoja.Columns.Item($col).SpecialCells(-4174), $desde) } catch {}
                    if (-not $rango) { $rango = $desde }
                    # La lista que ya tiene: su orden y sus mensajes son los del equipo (2026-11-09, medido en una copia:
                    # «Descartado;Ofertado;Evaluación;Adjudicado;No adjudicado», separada con «;», el separador de listas de
                    # Windows en español). Solo se agrega lo que falta, después del estado que lo precede en «lista».
                    $muestra = $null
                    for ($k = $primera + 1; $k -le $ultima -and -not $muestra; $k++) {
                        try { $v = $hoja.Cells.Item($k, $col).Validation; if ([int]$v.Type -eq 3) { $muestra = $v } } catch {}
                    }
                    $sep = [string]$xl.International(5)                 # xlListSeparator
                    if (-not $sep) { $sep = ',' }
                    $actual = New-Object System.Collections.ArrayList
                    if ($muestra) { foreach ($x in ([string]$muestra.Formula1).Split(@(';', ','), [StringSplitOptions]::RemoveEmptyEntries)) { [void]$actual.Add($x.Trim()) } }
                    $antes = $actual -join $sep
                    for ($j = 0; $j -lt $o.lista.Count; $j++) {
                        $x = [string]$o.lista[$j]
                        if ($actual -contains $x) { continue }
                        $donde = $actual.Count
                        for ($q = $j - 1; $q -ge 0; $q--) { $w = $actual.IndexOf([string]$o.lista[$q]); if ($w -ge 0) { $donde = $w + 1; break } }
                        $actual.Insert($donde, $x)
                    }
                    $nueva = $actual -join $sep
                    $como_v = $null
                    if ($muestra) {
                        $como_v = @{ alerta = $muestra.AlertStyle; vacio = $muestra.IgnoreBlank; flecha = $muestra.InCellDropdown;
                                     verEntrada = $muestra.ShowInput; verError = $muestra.ShowError; tituloEntrada = $muestra.InputTitle;
                                     entrada = $muestra.InputMessage; tituloError = $muestra.ErrorTitle; error = $muestra.ErrorMessage }
                    }
                    if ($nueva -ne $antes) {
                        [void]$rango.Validation.Delete()
                        try {
                            [void]$rango.Validation.Add(3, $(if ($como_v) { $como_v.alerta } else { 1 }), 1, $nueva)      # lista, (detener), entre
                            if ($como_v) {
                                $v = $rango.Validation
                                $v.IgnoreBlank = $como_v.vacio; $v.InCellDropdown = $como_v.flecha; $v.ShowInput = $como_v.verEntrada
                                $v.ShowError = $como_v.verError
                                if ($como_v.tituloEntrada) { $v.InputTitle = $como_v.tituloEntrada }
                                if ($como_v.entrada) { $v.InputMessage = $como_v.entrada }
                                if ($como_v.tituloError) { $v.ErrorTitle = $como_v.tituloError }
                                if ($como_v.error) { $v.ErrorMessage = $como_v.error }
                            }
                        }
                        catch {
                            if ($antes) { [void]$rango.Validation.Add(3, 1, 1, $antes) }
                            throw
                        }
                    }
                    # El color de la fila va por una regla por estado, sobre toda la tabla. Excel lee la fórmula relativa
                    # a la celda activa, por eso se elige la primera de la tabla antes de agregarla.
                    $tablaDatos = $hoja.Range($hoja.Cells.Item($primera + 1, 1), $hoja.Cells.Item($ultima, $tabla.Range.Columns.Count))
                    [void]$hoja.Activate()
                    [void]$hoja.Cells.Item($primera + 1, 1).Select()
                    $formula = '=$' + $o.letra + ($primera + 1) + '="Cerrado"'
                    $ya = $false
                    foreach ($regla in @($tablaDatos.FormatConditions)) { try { if ([string]$regla.Formula1 -eq $formula) { $ya = $true } } catch {} }
                    if (-not $ya) {
                        $regla = $tablaDatos.FormatConditions.Add(2, 0, $formula)      # por expresión
                        $regla.Interior.Color = 0xB4E0C6                               # BGR: verde claro
                    }
                }
                finally {
                    if ($protegida) { Proteger-Como $hoja $como }
                }
                # El Glosario dice qué es cada estado (si no está esa hoja, no es un problema)
                try {
                    $glosario = $wb.Worksheets.Item('Glosario')
                    $linea = $glosario.Range('A1:A40').Find('Estado')
                    if ($linea) {
                        $celda = $glosario.Cells.Item($linea.Row, 2)
                        $texto = [string]$celda.Value2
                        if ($texto -notmatch 'Cerrado') {
                            $bloqueada = [bool]$glosario.ProtectContents
                            $comoG = Proteccion-De $glosario
                            if ($bloqueada) { [void]$glosario.Unprotect() }
                            try { $celda.Value2 = $texto.TrimEnd() + ' Cerrado: adjudicado y ya entregado (su carpeta pasa a «0 Proyectos Entregados»).' }
                            finally { if ($bloqueada) { Proteger-Como $glosario $comoG } }
                        }
                    }
                } catch {}
                [void]$resultados.Add(@{ i = $i; ok = $true; fila = 0; detalle = 'lista de Estado al día' })
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
