# Plan: Tier 1 Step 8 — Xcode Project Generation (XcodeGen)

**Parent plan:** `plans/mvp-tier-0-tier-1.md` (Step 8)
**Source:** `MVP-Gap-Analysis.md` §5.1 (BLOCKING), §5.2 (BLOCKING), §5.3 (BLOCKING — partial here, finishes later)
**Status:** Draft — 2026-05-05.
**Owner:** Tech lead (this conversation)
**Created:** 2026-05-05

---

## Summary

Today the wrapper outputs a directory tree (`Sources/`, `PrivacyInfo.xcprivacy`, `report.md` / `report.json`) but **no `.xcodeproj`**. A developer cannot open the conversion result in Xcode without hand-rolling a project file. Step 8 closes that gap by emitting a declarative XcodeGen spec (`project.yml`) into the output dir, alongside placeholder signing config, a placeholder app-icon set, a placeholder `LaunchScreen.storyboard`, and a `PrivacyInfo.xcprivacy` reference. Running `xcodegen generate` from the output dir produces a buildable `.xcodeproj` that opens cleanly in Xcode and runs in the Simulator with the WKWebView wrapper around the source's web bundle.

XcodeGen is the default per ADR-0001 (Step 4 of the master plan). Tuist is explicitly **out of scope** for MVP — adding a second generator doubles the test matrix without buying anything until we have real users asking for it. The deliverable in this plan is the spec emitter + the supporting scaffolding, **not** an in-process invocation of `xcodegen`. The wrapper writes `project.yml`; the developer (or CI) runs `xcodegen generate`. This keeps the wrapper toolchain-agnostic and avoids shelling out to a Homebrew binary that might not be installed.

§5.2 (signing) is partially closed here — placeholder team/bundle IDs and a signing guide section in the generated README. Real signing requires the developer's Apple Developer account; the wrapper cannot do that work and shouldn't pretend to. §5.3 (asset pipeline) is partially closed here — a placeholder icon set + launch screen so the project builds. Converting source-codebase image assets is deferred to a follow-on plan.

---

## Architectural choices

### XcodeGen spec as data, generator invocation out-of-process

The wrapper writes `project.yml` and `Info.plist` and the supporting asset/storyboard files. It does **not** invoke `xcodegen` itself. Reasons:

1. The wrapper runs on Linux as well as macOS (CI, container builds). XcodeGen is a Swift binary; bundling or shelling out adds platform conditionals.
2. The developer needs to run `xcodegen generate` exactly once and then start editing — making the wrapper own that lifecycle invites stale-project bugs (when does the wrapper regenerate? after every conversion? only on first run?).
3. The generated `project.yml` is a first-class artifact. Developers can tweak it and re-run `xcodegen generate` themselves; the wrapper never has to round-trip.

The generated README's quickstart includes the one-line `xcodegen generate && open *.xcodeproj` command.

### Spec template, not Python string concatenation

`templates/xcodegen.yml.tmpl` is a real file with `{{placeholder}}` tokens. The emitter does a narrow substitution pass — same posture as `templates/privacy-overrides.yaml.template` in Step 6. No Jinja, no f-strings inside long heredocs. The template is reviewable as YAML in isolation, and the placeholders are documented at the top of the file.

### Capability detection reuses the Step 6 scanner

The Step 6 `api_scanner` already walks the source tree for required-reason API patterns. Step 8 extends the same data file (`config/apple-required-reason-apis.yaml`) with a parallel section listing **entitlement-bearing patterns**: e.g. `@capacitor/push-notifications` → `aps-environment`, `@capacitor/share` → none, `Notification.requestPermission` → `aps-environment`. The scanner emits `EntitlementFinding` records (separate dataclass; same scanner pass), and the spec emitter consumes them to flip the right capability flags.

Crucially, every detected entitlement that requires Apple Developer Account configuration (push notifications, App Groups, iCloud, HealthKit, Sign in with Apple, In-App Purchase) emits a **Layer A finding** through the Step 7 emitter, with `recommended_fix` pointing at Apple's developer portal. This closes the §5.2 acceptance criterion "emit a Layer-A finding for every required entitlement that the developer must enable in their Apple Developer account."

### Bundle ID, team ID, app name as CLI args

The wrapper's `convert` subcommand already takes `--app-name`. Step 8 adds `--bundle-id` (default: `com.example.<slug>`) and `--team-id` (default: `TODO_TEAMID`). When defaults are used, the spec emits the placeholder *and* a Layer A finding telling the developer to replace it before submission. No "guess from environment" magic — a guessed bundle ID is worse than a clearly-marked placeholder.

### Asset pipeline: placeholder, not generation

A flat-color SVG → PNG pipeline for icon generation is feasible (Pillow / ImageMagick) but it's a separate concern. For MVP, the spec emitter ships a checked-in `Assets.xcassets` template — a single 1024×1024 placeholder PNG, an `Contents.json` covering every required iOS slot, and a `LaunchScreen.storyboard` displaying the app name. A Layer A finding flags both as placeholders requiring developer replacement. Real asset conversion lands in the plan that closes §5.3 fully.

### Privacy manifest reference, not regeneration

Step 6 already writes `PrivacyInfo.xcprivacy`. The XcodeGen spec includes that file as a project resource. The spec emitter does not regenerate the manifest — it just lists it as a member of the target's `Resources` group. If the manifest is missing (e.g. the developer ran with `--skip-compliance`), the spec emitter logs a warning and excludes the file rather than referencing a missing resource.

### Capacitor host vs. raw WKWebView

The wrap-mode output is a **Capacitor host project**, not a hand-rolled WKWebView shell. ADR-0001 mandates Capacitor for the web wrapper layer. The spec lists Capacitor's iOS Pods (or SPM packages — see "Notes / risks") as dependencies, the source's web bundle is staged into `App/public/` per Capacitor's convention, and the host `AppDelegate.swift` is a thin Capacitor-bootstrap file. The emitter does **not** run `npx cap add ios` — that's a Node toolchain step the developer runs alongside `xcodegen generate`. The spec is what the post-`cap add ios` project would have looked like, with Capacitor's iOS scaffolding inlined as templates.

This is a deliberate tradeoff: we trade some duplication of Capacitor's own iOS scaffolding for not depending on a Node toolchain at conversion time. If Capacitor's iOS scaffolding drifts, our templates need to be re-pinned in lockstep with the Capacitor version listed in the matrix file. We add a CI check that compares our scaffolding against `npx cap add ios` output for the pinned Capacitor version; drift fails the build.

---

## Deliverables

1. **Spec template** — `templates/xcodegen.yml.tmpl`. Capacitor host project, placeholder signing, capability list driven by entitlement findings, privacy manifest as a resource.
2. **Info.plist template** — `templates/Info.plist.tmpl`. Required-reason usage strings as placeholders for any detected category, `ITSAppUsesNonExemptEncryption=NO` default, ATS dictionary.
3. **AppDelegate template** — `templates/AppDelegate.swift.tmpl`. Capacitor bootstrap, no app-specific logic.
4. **Asset placeholders** — `templates/Assets.xcassets/` (icon set Contents.json + a single placeholder PNG) and `templates/LaunchScreen.storyboard`.
5. **Entitlement scanner extension** — `converter/compliance/entitlement_scanner.py`. Walks source for entitlement-bearing patterns; emits `EntitlementFinding` records. Driven by a new section in `config/apple-required-reason-apis.yaml` (renamed file — see "Notes / risks") or a sibling YAML.
6. **Spec emitter** — `converter/xcode_project/emitter.py`. Consumes scan results + CLI flags + an output dir; writes `project.yml`, `Info.plist`, `AppDelegate.swift`, `Assets.xcassets/`, `LaunchScreen.storyboard` into the output dir.
7. **Wrapper integration** — `wrapper/__main__.py` adds `--bundle-id` and `--team-id`, runs the spec emitter after the compliance step, and passes the entitlement findings into the report builder.
8. **Generated README section** — the existing `wrapper/explainer.py` post-flight banner gains a "Build" section: the `xcodegen generate && open *.xcodeproj` quickstart and the signing guide.
9. **Tests** — emitter produces a syntactically valid spec for the fixture project; the spec passes `xcodegen --spec project.yml --quiet --no-cache` validation when XcodeGen is available; entitlement scanner produces the expected findings for known patterns.

Out of scope for this step (handled later):
- Actual `xcodegen generate` invocation. The wrapper writes the spec; the developer runs the tool.
- Full asset pipeline (§5.3): converting source app icons, splash screens, multi-scale images. Placeholders only here.
- Localisation pipeline (§5.4): `.xcstrings` generation. Separate plan.
- Tuist as an alternative generator. ADR-0001 lists it as opt-in; MVP ships XcodeGen only.
- Code-signing automation. The spec emits placeholders + a Layer-A finding; developer wires their Apple Developer account.

---

## Sub-steps (strict order)

### Step 8.1 — Author the templates

**Files:**
- `templates/xcodegen.yml.tmpl`
- `templates/Info.plist.tmpl`
- `templates/AppDelegate.swift.tmpl`
- `templates/Assets.xcassets/AppIcon.appiconset/Contents.json`
- `templates/Assets.xcassets/AppIcon.appiconset/icon-1024.png` (single placeholder)
- `templates/LaunchScreen.storyboard`

**`xcodegen.yml.tmpl` skeleton:**

```yaml
name: {{APP_NAME}}
options:
  bundleIdPrefix: {{BUNDLE_ID_PREFIX}}
  deploymentTarget:
    iOS: "15.0"
settings:
  base:
    DEVELOPMENT_TEAM: {{TEAM_ID}}
    CODE_SIGN_STYLE: Automatic
    SWIFT_VERSION: "5.9"
targets:
  {{APP_NAME}}:
    type: application
    platform: iOS
    sources:
      - path: App
    resources:
      - path: PrivacyInfo.xcprivacy
        optional: true
    info:
      path: App/Info.plist
    settings:
      PRODUCT_BUNDLE_IDENTIFIER: {{BUNDLE_ID}}
    entitlements:
      path: App/{{APP_NAME}}.entitlements
    dependencies:
{{DEPENDENCIES}}
```

**Acceptance:** Templates parse as YAML/Plist/Swift in isolation. Placeholders documented in a header comment.

---

### Step 8.2 — Entitlement scanner

**File:** `converter/compliance/entitlement_scanner.py`

**Behaviour:**
- Reads a new section in `config/apple-required-reason-apis.yaml` (or a sibling `config/apple-entitlements.yaml` — see "Notes / risks") mapping detection patterns to entitlement keys.
- Walks the source tree using the same pattern-matching infrastructure as Step 6's `api_scanner`. Emits `EntitlementFinding` records: `entitlement_key`, `pattern`, `file`, `line`, `requires_developer_account` (bool), `reason`.
- Plugin detection: reads `package.json` and `capacitor.config.{ts,js,json}` for known Capacitor plugins that imply entitlements (`@capacitor/push-notifications` → `aps-environment`, `@capacitor/local-notifications` → none but flag a Layer-B usage-string check).

**Acceptance:** A fixture with `@capacitor/push-notifications` and `Notification.requestPermission` produces exactly one `aps-environment` finding (deduped), with `requires_developer_account=True`.

---

### Step 8.3 — Spec emitter

**File:** `converter/xcode_project/emitter.py`

**Public interface:**

```python
@dataclass(frozen=True)
class XcodeSpec:
    app_name: str
    bundle_id: str
    team_id: str
    entitlements: tuple[str, ...]
    capacitor_version: str
    has_privacy_manifest: bool

def emit_xcode_project(
    *,
    spec: XcodeSpec,
    output_dir: Path,
    template_dir: Path | None = None,
) -> EmitResult: ...
```

`EmitResult` carries the list of files written and any Layer-A findings (placeholder bundle ID, placeholder team ID, placeholder icon set, placeholder launch screen, missing privacy manifest if applicable). The findings flow into the Step 7 report builder by the wrapper.

**Implementation notes:**
- Validate the spec on entry: bundle ID matches `^[a-zA-Z0-9.-]+$`, team ID matches `^[A-Z0-9]{10}$|^TODO_TEAMID$`, app name matches a narrow whitelist (alphanumerics + spaces).
- Write atomically: write to a temp dir under `workspace/`, then move into place. A partial Xcode project on disk is worse than no project.
- Validation pass after write: re-parse `project.yml` as YAML to confirm placeholder substitution didn't break the structure.

**Acceptance:** For the fixture, the emitter writes `project.yml`, `App/Info.plist`, `App/AppDelegate.swift`, `App/Assets.xcassets/AppIcon.appiconset/{Contents.json,icon-1024.png}`, `App/Base.lproj/LaunchScreen.storyboard`, and `App/<AppName>.entitlements`. Re-parsing each artifact succeeds.

---

### Step 8.4 — Wrapper integration

**File:** `wrapper/__main__.py`

**Behaviour:**
- New `--bundle-id` (default `com.example.<slug>`) and `--team-id` (default `TODO_TEAMID`) flags on `convert` and `convert-from-github`.
- After the compliance step writes the privacy manifest, run the entitlement scanner, build an `XcodeSpec`, and call `emit_xcode_project`.
- Push the entitlement findings + the emitter's placeholder findings into the same `ReportBuilder` the compliance step used. This way the final `report.md` lists *all* Layer-A blockers from both Step 6 (privacy manifest) and Step 8 (entitlements + signing).
- The post-flight banner (`wrapper/explainer.py`) gets a new line: `Build: cd <output_dir> && xcodegen generate && open *.xcodeproj`.

**Acceptance:** End-to-end run on the fixture produces a directory containing `project.yml` plus all supporting files, plus the existing `report.md` / `report.json` / `PrivacyInfo.xcprivacy`. The report's Layer A includes findings for placeholder bundle ID, placeholder team ID, push-notification entitlement (since the fixture imports `@capacitor/push-notifications`), and required-reason API findings from Step 6.

---

### Step 8.5 — XcodeGen validation in CI

**File:** `.github/workflows/test.yml` (or equivalent)

**Behaviour:**
- A CI job runs the wrapper end-to-end against the fixture, then runs `xcodegen --spec project.yml --quiet --no-cache` against the emitted spec. If XcodeGen reports any error, the build fails.
- A second job (macOS-only — separate from the Python suite) runs `xcodegen generate` and `xcodebuild -scheme <AppName> -destination 'generic/platform=iOS' -configuration Debug` to confirm the project builds clean.
- The macOS job is the slow path; the Linux Python suite runs on every PR, the macOS build runs on `main` push only (gated by a label for PR triggers).

**Acceptance:** CI green for the fixture. A deliberate breakage (e.g. malformed `bundle_id`) fails the spec-validation job loudly.

---

### Step 8.6 — Tests

**Files:**
- `converter/compliance/tests/test_entitlement_scanner.py` — entitlement detection coverage.
- `converter/xcode_project/tests/test_emitter.py` — spec validation, atomic write, placeholder substitution, finding emission.
- `converter/xcode_project/tests/test_templates.py` — every shipped template parses as its declared format (YAML/Plist/Swift via `swift-format --check` if available, else string-level invariants).
- `wrapper/tests/test_xcode_integration.py` — end-to-end run produces every expected file, every finding lands in the report, the report still passes schema validation.

**Coverage targets:**
- Every public function in `entitlement_scanner.py` and `emitter.py` has at least one direct test.
- Every entitlement pattern in the YAML data file has at least one positive detection test.
- Every Layer-A finding type the emitter can produce has a test that confirms it lands in the report's Layer A.

---

## Acceptance for the whole step

All of the following must hold:

1. The wrapper writes a complete XcodeGen spec + supporting files into the output dir on every conversion.
2. Running `xcodegen generate` from the output dir produces a `.xcodeproj` that Xcode opens without errors.
3. The generated project builds clean on the latest two Xcode releases (CI macOS job, gated to `main` push).
4. The `Info.plist` includes the Step 6 privacy manifest as a resource.
5. Every detected entitlement that requires Apple Developer Account configuration appears in `report.md` Layer A with `recommended_fix` pointing at Apple's developer portal.
6. Placeholder bundle ID, team ID, app icon, and launch screen each emit a Layer-A finding.
7. Tests cover scanner, emitter, templates, and end-to-end wrapper integration. All green on Linux.

When all seven pass, Step 8 is done. The next plan introduces the pre-flight scanner (gap §7.3) which consumes Layer-A findings to gate ship-readiness — at that point the wrapper refuses to produce a "ready to ship" message until the developer has resolved every placeholder finding from Step 8.

---

## Notes / risks

- **Capacitor SPM vs CocoaPods.** Capacitor 6 supports SPM but the iOS docs still default to CocoaPods. Pinning SPM means the developer doesn't need a Ruby toolchain; pinning CocoaPods means we ride the better-trodden path. Decision deferred to Step 8.1 — pick whichever has the cleaner `xcodegen` integration today, document the choice in ADR-0001's first revision. Either way, the matrix file pins the Capacitor major version.
- **Capacitor scaffolding drift.** Our `AppDelegate.swift.tmpl` and `Info.plist.tmpl` shadow what `npx cap add ios` would have written for the pinned Capacitor version. If Capacitor 7 changes the bootstrap, our templates rot. Mitigation: a CI job runs `npx cap add ios` against a tiny fixture, diffs the output against our templates, and fails on substantive drift. Same posture as the Apple required-reason API list in Step 6 — data drifts; treat it as data, not as source.
- **Bundle ID / team ID validation.** Apple's actual rules are complex (reserved domains, character class restrictions, length caps). We validate against the loose form here; Apple's review system catches the rest. We do **not** try to register the bundle ID — that's the developer's job in App Store Connect.
- **Asset placeholder licensing.** The placeholder PNG must be something we can ship under whatever license `ios-agent` ships under. Use a flat-color generated PNG, not a sourced image. Same for the launch screen — text-only, no logos.
- **macOS CI cost.** A full `xcodebuild` job costs a macOS runner minute per PR. We gate it to `main` push, not PR open, to keep PR costs low. If a PR claims to fix the macOS build, the contributor labels it `macos-ci` to opt in.
- **`config/apple-required-reason-apis.yaml` filename.** The current name reads "this file is about required-reason APIs only." Adding entitlements to it widens its scope. Either rename to `config/apple-source-detection.yaml` or split into a sibling `config/apple-entitlements.yaml`. The split keeps file responsibilities narrow and is the recommended path; rename only if the entitlement section is small and stable.

---

## File inventory (for review)

After Step 8:

```
config/
  apple-entitlements.yaml                       (new — entitlement detection patterns)
templates/
  xcodegen.yml.tmpl                             (new)
  Info.plist.tmpl                               (new)
  AppDelegate.swift.tmpl                        (new)
  Assets.xcassets/                              (new — placeholder icon set)
    AppIcon.appiconset/Contents.json
    AppIcon.appiconset/icon-1024.png
  LaunchScreen.storyboard                       (new)
converter/
  compliance/
    entitlement_scanner.py                      (new)
    tests/
      test_entitlement_scanner.py               (new)
  xcode_project/
    __init__.py                                 (new)
    emitter.py                                  (new)
    tests/
      __init__.py                               (new)
      test_emitter.py                           (new)
      test_templates.py                         (new)
wrapper/
  __main__.py                                   (modified — adds --bundle-id, --team-id, calls emitter)
  explainer.py                                  (modified — adds Build quickstart)
  tests/
    test_xcode_integration.py                   (new)
.github/workflows/
  test.yml                                      (modified — adds spec-validation + macOS-build jobs)
```

No edits to existing converter modules outside `compliance/` (entitlement scanner) and the new `xcode_project/` subtree. No changes to the matrix, scope doc, ADR (yet — ADR-0001 may gain a note on Capacitor SPM vs CocoaPods at the end of 8.1), the privacy-manifest schema/template, or the report schema.
