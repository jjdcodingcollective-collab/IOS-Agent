# ios-agent — Developer Disclaimer

**Status: PENDING LEGAL REVIEW** (MVP DoD §9.1)
**Version:** 1.0 (matches `wrapper/disclaimer.py` `DISCLAIMER_VERSION`)
**Last updated:** 2026-05-21

This document contains the disclaimer text shown to developers before running
a conversion. It must be reviewed and approved by legal counsel before the tool
is marketed as MVP-complete. The engineering scaffold (`wrapper/disclaimer.py`)
is built and tested — only the text requires legal sign-off.

---

## Disclaimer Text (as shown to users)

```
ios-agent — Developer Disclaimer

This tool generates best-effort App Store compliance scaffolding for your web
application. By proceeding you acknowledge the following:

1. NO GUARANTEE OF APP STORE APPROVAL
   ios-agent automates compliance checks based on known Apple guidelines as of
   its last update. Apple's review process is discretionary. The tool cannot
   guarantee that any converted app will be approved, and approval of one
   version does not guarantee approval of future versions.

2. DEVELOPER RESPONSIBILITY
   Final responsibility for App Store submission, compliance with Apple's
   Developer Program License Agreement, and any regulatory requirements
   (export compliance, privacy laws, COPPA, GDPR, etc.) rests entirely with
   the developer submitting the app.

3. TOOL OUTPUT REQUIRES HUMAN REVIEW
   All generated files — including PrivacyInfo.xcprivacy, Info.plist, and
   project.yml — must be reviewed and validated by a qualified developer
   before submission. Placeholder values (bundle ID, team ID, usage strings)
   MUST be replaced with accurate information.

4. COMPLIANCE RULES MAY BE STALE
   Apple updates its guidelines continuously. The compliance rule data files
   in config/ reflect requirements as of the tool's last release. Check
   CHANGELOG.md for the rule-update date and review Apple's latest guidelines
   before submitting.

5. NO WARRANTY
   This software is provided "as is", without warranty of any kind. See
   LICENSE for the full MIT license terms.
```

---

## Legal Review Checklist

These are the questions legal counsel should assess before sign-off:

- [ ] Does point 1 (no guarantee) adequately disclaim liability for App Store
      rejection outcomes?
- [ ] Does point 2 (developer responsibility) cover the full range of regulatory
      frameworks our users may be subject to (GDPR, COPPA, CCPA, export controls)?
- [ ] Does point 5 (no warranty) align with the MIT License in `LICENSE`? Are
      additional warranty disclaimers needed beyond what MIT provides?
- [ ] Should the disclaimer include a governing-law clause?
- [ ] Should acknowledgement logging (timestamp + disclaimer version stored in
      `~/.ios-agent/disclaimer-accepted.json`) be disclosed in a privacy notice?
- [ ] Is "Type 'agree' to acknowledge and continue" sufficient for enforceable
      acknowledgement, or do we need a checkbox / more explicit consent flow?
- [ ] Are there jurisdictions where this disclaimer is insufficient or
      unenforceable that we should address?

---

## Engineering Notes (for legal context)

- The disclaimer is shown **once per machine per disclaimer version**. After
  acknowledgement, a JSON record is written to `~/.ios-agent/disclaimer-accepted.json`
  with: `accepted_at` (ISO 8601 UTC timestamp), `via` (`"interactive"` or
  `"--yes"`), and `tool_version`.
- Bumping `DISCLAIMER_VERSION` in `wrapper/disclaimer.py` forces re-acknowledgement
  on all machines. Use this whenever the text changes materially.
- `--yes` / `-y` auto-accepts without prompting (for CI pipelines). The disclaimer
  is still printed; the record is written with `via: "--yes"`.
- The dotfile is local only — it is never transmitted anywhere.

---

## Sign-off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Legal counsel | — | — | **REQUIRED before MVP ship** |
| Product owner | — | — | |
| Tech lead | — | — | |
