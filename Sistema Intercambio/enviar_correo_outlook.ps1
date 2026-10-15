# enviar_correo_outlook.ps1 -- Entrega un correo a Outlook de este equipo
# (COM) y espera a que salga. Lo llama alertas_oportunidades.py (2026-10-14).
#
# Recibe la ruta de un JSON {para: [...], asunto, html}: asi ningun texto de
# Mercado Publico pasa por la linea de comandos. Escribe "enviado" si salio de
# la bandeja de salida, o "bandeja-de-salida" si quedo ahi (Outlook lo envia
# al sincronizar, por ejemplo cuando se abre). Cualquier error: codigo 1.
param([Parameter(Mandatory = $true)][string]$Ruta)
$ErrorActionPreference = 'Stop'

$m = Get-Content -Raw -Encoding UTF8 -LiteralPath $Ruta | ConvertFrom-Json
$outlook = New-Object -ComObject Outlook.Application
$ns = $outlook.GetNamespace("MAPI")
$correo = $outlook.CreateItem(0)
$correo.To = ($m.para -join ";")
$correo.Subject = $m.asunto
$correo.HTMLBody = $m.html
$correo.Send()

# Si Outlook estaba cerrado, COM lo abre sin ventana y puede cerrarse antes de
# enviar: se fuerza la sincronizacion y se espera hasta 60 s a que salga.
$salida = $ns.GetDefaultFolder(4)
for ($i = 0; $i -lt 30; $i++) {
    if ($salida.Items.Count -eq 0) { Write-Output "enviado"; exit 0 }
    try { $ns.SendAndReceive($false) } catch { }
    Start-Sleep -Seconds 2
}
Write-Output "bandeja-de-salida"
exit 0
