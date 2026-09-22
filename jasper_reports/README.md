# BKPOS JasperViewer integration

BKPOS keeps all invoice, customer, stock and payment logic in the existing
Python application. This folder is only the report/preview layer.

## What it does

After a completed sale, if a JasperReports runtime is configured, BKPOS:

1. Builds a filled JasperPrint XML (`.jrpxml`) receipt from the already-saved sale.
2. Launches the standard `net.sf.jasperreports.view.JasperViewer` in a separate Java process.
3. Continues to the existing Epson thermal-print path and existing PDF-copy path.

JRPXML is an official JasperReports representation of a filled `JasperPrint`, and
JasperViewer supports viewing reports stored as XML. See the JasperReports
viewer documentation for the standard viewer behavior.

## Configure JasperViewer on Windows

Install/obtain a JasperReports runtime containing the JasperReports JARs and
make sure Java is installed.

Then set either:

```text
MIPOS_JASPER_HOME=C:\path\to\jasperreports-runtime
```

where the folder contains JasperReports JARs (or a `lib` subfolder), **or**:

```text
MIPOS_JASPER_CLASSPATH=C:\path\to\jasperreports.jar;C:\path\to\dependency1.jar;...
```

BKPOS also auto-detects Java, common JasperReports runtime folders, and
`jasperviewer.bat`, `jasperviewer.cmd`, or `jasperviewer.exe`. If auto-detection
does not find the runtime, run `CONFIGURE_JASPER_VIEWER.bat` from the project folder.

The launcher uses the standard JasperViewer command form:

```text
java -cp "<all JasperReports jars>" net.sf.jasperreports.view.JasperViewer -F<file>.jrpxml -XML
```

## Important

The ZIP does **not** silently bundle a Java/JasperReports distribution. That
keeps the BKPOS Python application portable and avoids mixing a third-party
Java runtime into the POS business logic. Once a Jasper runtime is configured,
the same completed sale automatically opens in JasperViewer.

A future step can add a Code128 barcode image and richer company settings
(VAT number, legal name, address and phone) without changing checkout logic.
