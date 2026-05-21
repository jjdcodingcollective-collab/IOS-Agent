# Changelog

All notable changes to ios-agent are documented here.

## [0.1.0] — 2026-05-21

First public release. Converts TypeScript/React web apps to Capacitor-based
iOS Xcode projects with complete App Store compliance scaffolding.

### What ships

#### Core pipeline

- `python -m wrapper preflight <path>` — scan a source tree for App Store
  compliance blockers before touching anything. Exit 0 = clear,
  1 = Layer-A blockers, 2 = scan error.
- `python -m wrapper convert <path>` — local conversion: privacy manifest,
  Xcode project, three-layer report (`report.md` + `report.json`).
- `python -m wrapper convert-from-github <url>` — GitHub round-trip: clone,
  convert, commit to `ios-conversion` branch, optional push + `--open-pr`.

#### App Store compliance scanners (six, all data-driven)

| Scanner | Guideline | Layer |
|---------|-----------|-------|
| Required-reason API (UserDefaults, FileTimestamp, SystemBootTime, DiskSpace, ActiveKeyboards) | Privacy manifest | A blocker |
| ATT / IDFA — 19 patterns (direct + analytics SDKs) | 5.1.2 | A blocker |
| SIWA parity — 19 third-party SSO trigger patterns | 4.8 | A blocker |
| Usage string completeness audit | OS crash prevention | A blocker |
| ATS configuration (http:// URLs, allowsArbitraryLoads) | 4.5.4 | B review |
| Minimum functionality heuristic | 4.2 | B review |
| Encryption export (18 crypto-import patterns) | Export compliance | B review |

#### Generated outputs (per conversion)

- `PrivacyInfo.xcprivacy` — Apple privacy manifest, auto-populated from
  scanner findings with developer-override support (`privacy-overrides.yaml`).
- `project.yml` — XcodeGen spec (run `xcodegen generate` to produce the
  `.xcodeproj`).
- `App/Info.plist` — pre-filled with `NS*UsageDescription` placeholders for
  every detected permission-gated capability.
- `App/AppDelegate.swift`, `App/Assets.xcassets`, `App/LaunchScreen.storyboard`
- `report.md` + `report.json` — three-layer report: Layer A blockers,
  Layer B manual review, Layer C learnings.

#### Data catalogues (versioned, editable)

- `config/apple-required-reason-apis.yaml` — required-reason API categories
  + ATT + encryption export patterns.
- `config/apple-entitlements.yaml` — 12 capabilities, 30+ patterns,
  SIWA parity trigger field.
- `config/compatibility-matrix.yaml` — source × target mode gate
  (`web × wrap` is the only active combination).

### Notes

- No third-party runtime dependencies — stdlib only (no PyYAML, no jsonschema).
- Python 3.11+ required.
- XcodeGen must be installed separately (`brew install xcodegen`).
- `web × wrap` is the only supported combination in this release.
  The compatibility matrix gate blocks all other combinations unless
  `--allow-unsupported` is passed.
- The Definition of Done for "supported: true" requires an actual App Store
  approval of a tool-converted reference app. See `docs/mvp-scope.md`.
- 379 tests green on Python 3.11.

[0.1.0]: https://github.com/jjdcodingcollective/ios-agent/releases/tag/v0.1.0
