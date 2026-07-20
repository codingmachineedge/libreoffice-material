# Windows headless evidence-contract regression

`Validate-EvidenceContract.ps1` is a dependency-free PowerShell 5.1-compatible
regression for the schema-v2 Windows headless candidate manifest. It proves that
a complete synthetic passed candidate validates, and that mismatched embedded
build IDs, non-Boolean impostors, invalid inventory IDs, private paths, process
or session mismatches, forced cleanup, missing/traversing artifacts, PNG/hash or
a11y mismatches, absent focused nodes, and incomplete acceptance reviews are
rejected. The fixture writes real minimal PNG/IHDR and a11y JSON files so both
candidate and accepted validation exercise file binding without UI automation.

Run it without launching LibreOffice or the low-level MCP server:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\qa\windows-headless-evidence\Validate-EvidenceContract.ps1
```

The regression validates the manifest contract and runner wiring only. It does
not produce or accept UI evidence.
