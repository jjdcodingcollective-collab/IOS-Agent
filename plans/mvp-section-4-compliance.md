# Plan: MVP §4.x Compliance Items

**Status:** Complete — 2026-05-20 (Steps 4.3, 4.8, 4.5, 4.9, 4.2 shipped; §4.6 stretch deferred)
**Prerequisite:** Tier 1 complete (Steps 1–8 shipped); smoke test passed 2026-05-20.
**Test baseline:** 260 green → **363 green** after all steps (240 converter + 123 wrapper).

---

## Summary

Five compliance gaps remain between what the Tier 1 pipeline produces and a
submission-ready App Store binary. All reuse the existing scanner/report
substrate (Steps 6–8) — there is no new architectural work, only new
detectors, new generators, and new report categories.

Each step ships independently and incrementally raises the compliance bar.
Steps are ordered from highest rejection risk to lowest.

---

## Scope (from `docs/mvp-scope.md` "Wrap" in-scope list)

| Gap | Apple rule | Current state | Target state |
|-----|-----------|---------------|--------------|
| §4.3 ATT prompt detection | App Tracking Transparency — Guideline 5.1.2 | Not detected | Scanner detects IDFA/ATT patterns; Layer-A blocker if found without `NSUserTrackingUsageDescription` |
| §4.8 SIWA parity | Sign in with Apple — Guideline 4.8 | Only flags explicit `@capacitor-community/apple-sign-in` import; misses third-party SSO | Scanner detects Google/Facebook/Twitter/GitHub OAuth patterns; Layer-A SIWA blocker if found without SIWA |
| §4.5 Usage strings completeness | `Info.plist` NS*UsageDescription — hard OS crash if missing | Placeholder strings emitted when entitlement scanner fires; no audit of pre-existing strings | Audit all emitted usage strings; flag empty/placeholder strings as Layer-A; ensure Capacitor plugin patterns cover common third-party SDKs |
| §4.9 ATS configuration | App Transport Security — Guideline 4.5.4 | `NSAllowsArbitraryLoads: false` hardcoded in `Info.plist.tmpl` | Scanner detects hardcoded HTTP URLs / `allowsArbitraryLoads` overrides in source; Layer-B warning if found |
| §4.2 Minimum functionality | Guideline 4.2 — app must have sufficient native feature density | Not checked | Heuristic: flag if source has zero Capacitor plugins and zero native API calls (pure static web page wrapped as app) |
| §4.6 Encryption export | ITSAppUsesNonExemptEncryption — `false` hardcoded | `false` hardcoded (safe default) | Scanner detects crypto imports (WebCrypto, SubtleCrypto, non-exempt libs); emit Layer-B note if found so developer can make an informed declaration |

---

## Step-by-step build plan

### Step 4.3 — ATT / IDFA detector ✅ `88ea21e`

**Why first:** IDFA use without ATT consent is the #1 cause of rejection for
apps that "accidentally" include ad SDKs or analytics (e.g. Firebase Analytics
imports IDFA transitively). A false negative here means App Store rejection.

**Files to create/modify:**

- `config/apple-required-reason-apis.yaml` — add ATT section: patterns for
  `requestTrackingAuthorization`, `ATTrackingManager`, `advertisingIdentifier`,
  Firebase Analytics imports, Facebook Audience Network imports.
- `converter/compliance/att_scanner.py` — new module. Scans for ATT/IDFA
  patterns. Returns `AttFinding` dataclass with file, line, pattern,
  `NSUserTrackingUsageDescription` present/absent.
- `converter/compliance/tests/test_att_scanner.py` — ≥10 tests.
- `wrapper/compliance_step.py` — wire `att_scanner` into post-convert pipeline.
- `wrapper/xcode_step.py` — if ATT findings present, inject
  `NSUserTrackingUsageDescription` placeholder into `Info.plist`; emit
  Layer-A blocker if string is placeholder.
- `wrapper/preflight.py` — add ATT check to `run_preflight()`.

**Acceptance:**
1. A source file containing `ATTrackingManager.requestTrackingAuthorization`
   produces a Layer-A blocker in `report.json`.
2. A source file importing `@react-native-firebase/analytics` produces a
   Layer-A blocker.
3. A clean source produces no ATT findings.
4. `preflight` exit code 1 when ATT blocker present.

---

### Step 4.8 — SIWA parity (third-party SSO detector) ✅ `3ecba52`

**Why second:** Guideline 4.8 is a binary rule — if any third-party login
exists, SIWA *must* be offered. The current scanner only detects explicit
SIWA plugin imports, not the third-party SSO that *triggers* the requirement.

**Files to create/modify:**

- `config/apple-entitlements.yaml` — add third-party SSO patterns under the
  existing `com.apple.developer.applesignin` entry:
  `@react-oauth/google`, `@react-native-google-signin/google-signin`,
  `firebase/auth` (GoogleAuthProvider, FacebookAuthProvider, GithubAuthProvider,
  TwitterAuthProvider), `react-native-fbsdk-next`, `passport-*`, generic
  `signInWithPopup` / `signInWithRedirect` patterns.
- `converter/compliance/entitlement_scanner.py` — extend pattern matching;
  distinguish "has third-party SSO but no SIWA" from "has SIWA explicitly"
  to produce the correct Layer-A message.
- `converter/compliance/tests/test_entitlement_scanner.py` — add ≥8 new
  tests for SSO-triggers-SIWA-requirement cases.

**Acceptance:**
1. Source importing `@react-oauth/google` without SIWA → Layer-A blocker
   with message explaining Guideline 4.8 requirement.
2. Source importing `@capacitor-community/apple-sign-in` alone → no blocker
   (SIWA present).
3. Source with neither → no SIWA finding.

---

### Step 4.5 — Usage string completeness audit ✅ `3ad7064`

**Why third:** Usage strings are already partially handled (entitlement scanner
fires when Capacitor plugins are detected). This step adds an *audit pass* that
catches strings that were emitted as placeholder text and haven't been replaced.

**Files to create/modify:**

- `converter/compliance/usage_string_auditor.py` — new module. Reads the
  generated `Info.plist` after conversion; finds any `NS*UsageDescription`
  whose value matches a known placeholder pattern (`TODO`, `ios-agent`,
  `<describe`, empty string). Emits Layer-A finding per offending key.
- `converter/compliance/tests/test_usage_string_auditor.py` — ≥8 tests.
- `wrapper/xcode_step.py` — run auditor after `Info.plist` is written;
  merge findings into `XcodeStepResult`.

**Acceptance:**
1. Generated `Info.plist` with `NSCameraUsageDescription = "TODO: describe use"`
   → Layer-A blocker.
2. Generated `Info.plist` with a real description → no finding.
3. Missing key entirely when Camera plugin was detected → Layer-A blocker
   (already covered by entitlement scanner; regression test).

---

### Step 4.9 — ATS configuration scanner ✅ `980005c`

**Why fourth:** `NSAllowsArbitraryLoads: false` is already the safe default in
our template. This step detects when the *source* contains hardcoded `http://`
URLs or server-side fetch calls to non-HTTPS endpoints, which would silently
fail at runtime under ATS.

**Files to create/modify:**

- `converter/compliance/ats_scanner.py` — new module. Scans TS/JS source for:
  - Hardcoded `http://` (not `https://`) string literals in fetch/axios/XHR calls.
  - `allowsArbitraryLoads: true` in any config JSON.
  - Emits Layer-B (manual review) finding per occurrence — not a hard blocker
    since `http://` can be legitimate for localhost dev addresses.
- `converter/compliance/tests/test_ats_scanner.py` — ≥8 tests.
- `wrapper/compliance_step.py` — wire into post-convert pipeline.

**Acceptance:**
1. Source with `fetch('http://api.example.com')` → Layer-B finding.
2. Source with `fetch('https://api.example.com')` → no finding.
3. Source with `allowsArbitraryLoads: true` in a config → Layer-B finding.

---

### Step 4.2 — Minimum functionality heuristic ✅ `8c0623e`

**Why last:** Guideline 4.2 rejections are subjective; the heuristic can only
flag *obvious* cases (pure static wrapper with no interactivity). False
positives are worse than false negatives here.

**Files to create/modify:**

- `converter/compliance/min_functionality_checker.py` — new module. Checks:
  - Zero Capacitor plugin imports detected.
  - Zero native API usage strings emitted.
  - Source has ≤ N unique routes/screens (configurable; default 3).
  - If all three conditions met → Layer-B finding with Guideline 4.2 text.
- `converter/compliance/tests/test_min_functionality_checker.py` — ≥6 tests.
- `wrapper/compliance_step.py` — wire in after entitlement scanner.

**Acceptance:**
1. Source with 1 route, 0 Capacitor plugins, 0 usage strings → Layer-B finding.
2. Source with 5+ routes or any Capacitor plugin → no finding.

---

### Step 4.6 — Encryption export declaration audit (bonus / low-risk) — DEFERRED

**Not a rejection risk on its own** (our template defaults to `false`), but
incorrect declarations can trigger export compliance holds. Add as a lightweight
Layer-B note when non-exempt crypto is detected.

**Files to create/modify:**

- Add crypto-import patterns to `converter/compliance/api_scanner.py`:
  `SubtleCrypto`, `crypto.subtle`, `CryptoKey`, `node:crypto`, `crypto-js`,
  `forge`, `jsencrypt`.
- Emit Layer-B finding if any match, with text: "Source uses non-exempt
  cryptography. Verify `ITSAppUsesNonExemptEncryption` in Info.plist before
  submitting — a false `false` declaration is an App Store violation."

**Acceptance:**
1. Source importing `crypto-js` → Layer-B note.
2. Source using `Math.random()` only → no crypto finding.

---

## Acceptance criteria for the full track

- All steps above shipped with tests.
- Total test count ≥ 310 (current 260 + ~50 new).
- `the-survival-bible/apps/web` re-run produces the same 87 Layer-A items
  plus any new findings the new scanners surface (regression baseline).
- `preflight` exit codes still correct: 0 = clear, 1 = blockers, 2 = error.
- No existing test regressions.

---

## Key files (reference)

| File | Role |
|------|------|
| `config/apple-entitlements.yaml` | Pattern catalogue for entitlement + SIWA scanner |
| `config/apple-required-reason-apis.yaml` | Pattern catalogue for required-reason API scanner |
| `converter/compliance/api_scanner.py` | Required-reason API scanner (Step 6) |
| `converter/compliance/entitlement_scanner.py` | Entitlement + SIWA scanner (Step 8.2) |
| `converter/compliance/privacy_manifest.py` | PrivacyInfo.xcprivacy generator |
| `converter/reports/three_layer_emitter.py` | Layer A/B/C report builder |
| `wrapper/compliance_step.py` | Orchestrates all compliance scanners |
| `wrapper/xcode_step.py` | XcodeGen emit + finding merge |
| `wrapper/preflight.py` | Pre-flight entry point |
| `schemas/report.schema.json` | Three-layer report schema |

---

## Notes

- Steps can be shipped individually; each is a self-contained commit.
- Step 4.3 (ATT) is the highest-priority; ship it first.
- SIWA parity (4.8) and usage string audit (4.5) are next in line.
- ATS (4.9) and minimum functionality (4.2) are lower-risk and can follow.
- Encryption export (4.6) is a stretch/bonus item.
- After all steps land, update `docs/mvp-scope.md` to mark these items complete
  and flip `config/compatibility-matrix.yaml` `supported: true` for `web × wrap`.
