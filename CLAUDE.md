# CLAUDE.md — frappe-erpnext (SWE-Pioneers fork)

Changes on top of upstream `frappe/erpnext` (version-16).

## Arabic i18n
- `erpnext/locale/ar.po` completed to **100% of app-owned strings** (Libyan-appropriate MSA), tagged
  `ai-translated; needs-native-review`. Built/filled via the parent repo's `scripts/i18n` pipeline
  (`generate-pot-file` sync for full doctype/field coverage). See the parent `SWE-Pioneers/frappe`
  `CLAUDE.md` for the pipeline + the runtime `.mo` compile mechanics.
- Desk/portal app — RTL is handled by the Frappe framework; no app-level RTL change.

## Deploy
Built from `~/build/erpnext-custom` on the VPS (Containerfile repointed to this fork + per-app
`compile-po-to-mo`). Rebuild with `--no-cache`; see the parent `CLAUDE.md` for the `.mo` compile +
persist gotchas.
