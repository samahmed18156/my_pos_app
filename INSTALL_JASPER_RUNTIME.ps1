$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "jasper_runtime"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

$base = "https://repo.maven.apache.org/maven2"
$artifacts = @(
  "net/sf/jasperreports/jasperreports/6.21.3/jasperreports-6.21.3.jar",
  "net/sf/jasperreports/jasperreports-metadata/6.21.3/jasperreports-metadata-6.21.3.jar",
  "net/sf/jasperreports/jasperreports-fonts/6.21.3/jasperreports-fonts-6.21.3.jar",
  "commons-beanutils/commons-beanutils/1.9.4/commons-beanutils-1.9.4.jar",
  "commons-digester/commons-digester/2.1/commons-digester-2.1.jar",
  "commons-logging/commons-logging/1.1.1/commons-logging-1.1.1.jar",
  "commons-collections/commons-collections/3.2.2/commons-collections-3.2.2.jar",
  "org/apache/commons/commons-collections4/4.2/commons-collections4-4.2.jar",
  "com/github/librepdf/openpdf/1.3.32/openpdf-1.3.32.jar",
  "org/jfree/jcommon/1.0.23/jcommon-1.0.23.jar",
  "org/jfree/jfreechart/1.0.19/jfreechart-1.0.19.jar",
  "org/eclipse/jdt/ecj/3.21.0/ecj-3.21.0.jar",
  "com/fasterxml/jackson/core/jackson-core/2.15.3/jackson-core-2.15.3.jar",
  "com/fasterxml/jackson/core/jackson-annotations/2.15.3/jackson-annotations-2.15.3.jar",
  "com/fasterxml/jackson/core/jackson-databind/2.15.3/jackson-databind-2.15.3.jar",
  "com/fasterxml/jackson/dataformat/jackson-dataformat-xml/2.15.3/jackson-dataformat-xml-2.15.3.jar",
  "com/fasterxml/jackson/module/jackson-module-jaxb-annotations/2.15.3/jackson-module-jaxb-annotations-2.15.3.jar",
  "org/codehaus/woodstox/stax2-api/4.2.1/stax2-api-4.2.1.jar",
  "com/fasterxml/woodstox/woodstox-core/6.5.1/woodstox-core-6.5.1.jar",
  "org/apache/xmlgraphics/batik-gvt/1.17/batik-gvt-1.17.jar",
  "org/apache/xmlgraphics/batik-svg-dom/1.17/batik-svg-dom-1.17.jar",
  "org/apache/xmlgraphics/batik-svggen/1.17/batik-svggen-1.17.jar",
  "org/apache/xmlgraphics/batik-bridge/1.17/batik-bridge-1.17.jar",
  "org/apache/xmlgraphics/batik-anim/1.17/batik-anim-1.17.jar",
  "org/apache/xmlgraphics/batik-awt-util/1.17/batik-awt-util-1.17.jar",
  "org/apache/xmlgraphics/batik-parser/1.17/batik-parser-1.17.jar",
  "org/apache/xmlgraphics/batik-constants/1.17/batik-constants-1.17.jar",
  "org/apache/xmlgraphics/batik-css/1.17/batik-css-1.17.jar",
  "org/apache/xmlgraphics/batik-dom/1.17/batik-dom-1.17.jar",
  "org/apache/xmlgraphics/batik-ext/1.17/batik-ext-1.17.jar",
  "org/apache/xmlgraphics/batik-i18n/1.17/batik-i18n-1.17.jar",
  "org/apache/xmlgraphics/batik-script/1.17/batik-script-1.17.jar",
  "org/apache/xmlgraphics/batik-shared-resources/1.17/batik-shared-resources-1.17.jar",
  "org/apache/xmlgraphics/batik-util/1.17/batik-util-1.17.jar",
  "xml-apis/xml-apis/1.4.01/xml-apis-1.4.01.jar",
  "xml-apis/xml-apis-ext/1.3.04/xml-apis-ext-1.3.04.jar"
)

foreach ($rel in $artifacts) {
    $name = Split-Path $rel -Leaf
    $dest = Join-Path $Runtime $name
    $url = "$base/$rel"
    Write-Host "Downloading $name ..."
    Invoke-WebRequest -Uri $url -OutFile $dest
    $bytes = [System.IO.File]::ReadAllBytes($dest)
    if ($bytes.Length -lt 4 -or $bytes[0] -ne 0x50 -or $bytes[1] -ne 0x4B) {
        throw "Downloaded file is not a valid JAR/ZIP archive: $name (size $($bytes.Length) bytes)"
    }
    Write-Host "  OK: $name ($($bytes.Length) bytes)"
}

# Find Java exactly, including the Temurin installation already confirmed on this PC.
$java = $null
$cmd = Get-Command java.exe -ErrorAction SilentlyContinue
if ($cmd) { $java = $cmd.Source }
if (-not $java) {
    $candidates = @(
      "$env:ProgramFiles\Eclipse Adoptium\jre-17.0.20.101-hotspot\bin\java.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $java = $c; break }
    }
}
if (-not $java) {
    $java = (Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Recurse -Filter java.exe -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty FullName)
}
if (-not $java) { throw "Java was not found." }

# Save exact runtime + Java path so BKPOS does not depend on PATH.
$config = @{
    home = $Runtime
    java = $java
} | ConvertTo-Json
Set-Content -Path (Join-Path $Root "mipos_jasper_config.json") -Value $config -Encoding UTF8

Write-Host ""
Write-Host "BKPOS JasperReports runtime installed."
Write-Host "Java: $java"
Write-Host "Runtime: $Runtime"
Write-Host ""
$cp = Join-Path $Runtime "*"
Write-Host "Testing JasperViewer..."
& $java -cp $cp net.sf.jasperreports.view.JasperViewer --help 2>&1 | Select-Object -First 8
Write-Host ""
Write-Host "Restart BKPOS and try View Selected Document."


