# BKPOS JasperViewer setup

Java is required first. The PC can use Eclipse Temurin 17.

If BKPOS says:

> Java was found, but JasperReports/JasperViewer was not found.

run `INSTALL_JASPER_VIEWER.bat`.

It downloads JasperStarter 3.6.2 from SourceForge and opens its Windows installer. JasperStarter bundles the JasperReports libraries, and BKPOS will automatically search common JasperStarter installation folders for the JasperReports JARs.

After installation:
1. Close BKPOS completely.
2. Restart BKPOS.
3. Open Customer Accounts / Debtors.
4. Select the invoice.
5. Click VIEW SELECTED DOCUMENT.

The BKPOS database is not replaced by this setup.


## Phase 20 runtime installer
The runtime installer downloads JasperReports 6.21.3 and its required runtime dependencies directly from Maven Central. It validates JAR files by their ZIP/JAR signature, so small legitimate artifacts such as jasperreports-metadata are accepted. The installer does not modify the POS database.
