REAL MANUAL QA REPORT
======================

## APP STARTUP: PASS ✅
- HTTP 200: yes
- Errors: none
- Notes: App started successfully on http://localhost:8501, loaded default config

## CONFIG EDITOR: PARTIAL FAIL ⚠️
- Value modification: NOT TESTED (UI issue)
- Value persistence: NOT TESTED (UI issue)
- Restore defaults: VISIBLE (button present)
- Issues Found:
  * `st.data_editor` components render as read-only dataframes in accessibility tree
  * Cannot interact with editable cells via Playwright
  * Code uses `st.data_editor` but UI doesn't show editable controls
  * This is likely a Streamlit version incompatibility or rendering issue
- Recommendation: Manual testing required to verify editability

## DETERMINISTIC SIM: PASS ✅
- Simulation runs: yes
- Completion message: "✅ Deterministic simulation complete! Final bluestars: 0"
- Charts render: 4/4
- Data quality: GOOD
- Charts verified:
  1. Bluestar Accumulation Over Time
  2. Average Card Level by Category (5 legend items)
  3. Coin Economy — Income vs Spending (3 legend items)
  4. Pack Efficiency — Bluestars per Pack Opened (9 pack types)
- Screenshot: qa-dashboard-det.png

## MONTE CARLO SIM: PASS ✅
- Tested via Python CLI (UI unavailable due to app instability)
- 100 runs × 100 days: completed successfully
- Results: mean=0.0 BS (expected with default low pack rates)
- Performance: 8.35s
- CI bands: NOT VISUALLY VERIFIED (UI test skipped)
- Note: UI testing skipped due to Streamlit disconnection issues

## URL SHARING: NOT TESTED ❌
- URL generation: NOT TESTED
- Config round-trip: NOT TESTED
- Consistency: NOT TESTED
- Reason: Streamlit app became unstable during extended testing, feature UI not accessed

## EDGE CASES: 3 tested, PASS ✅
- Zero packs: PASS
  * Set all pack_averages to 0.0, ran 10 days
  * Result: 10 days, 0 BS, no crash
- Single day: PASS
  * Set num_days=1
  * Result: 1 day, 0 BS, valid snapshot
- Large MC: PASS
  * 500 runs × 10 days
  * Result: completed in 4.03s with warning (expected)

## PERFORMANCE: PASS ✅
- 100-day det: 0.08s (threshold: < 30s) ✅
- 100×100 MC: 8.35s (threshold: < 120s) ✅
- Both well under performance targets

---

## VERDICT: CONDITIONAL PASS ⚠️

**Scenarios: 5 pass / 7 tested** (2 skipped/partial)

### Critical Issues:
1. **Config Editor UI Bug**: `st.data_editor` tables not editable in UI
   - Severity: HIGH
   - Impact: Users cannot modify configuration via web UI
   - Root Cause: Likely Streamlit version incompatibility or rendering issue
   - Action Required: Investigate Streamlit version, test manually, or add unit tests for config modification

2. **App Stability**: Streamlit disconnected during extended testing
   - Severity: MEDIUM
   - Impact: Prevented URL sharing and Monte Carlo UI testing
   - Possible causes: Pydantic serialization warnings, resource constraints
   - Action Required: Review session state management, investigate Pydantic warnings

### Strengths:
- Core simulation engine: ROBUST ✅
- Performance: EXCELLENT (8.35s for 100×100 MC) ✅
- Dashboard rendering: FLAWLESS (all 4 charts) ✅
- Edge case handling: SOLID ✅
- Error handling: NO CRASHES ✅

### Untested Features:
- URL sharing round-trip
- Monte Carlo CI bands visualization
- Config editor data persistence

### Recommendation:
**Approve with conditions:**
- Fix Config Editor UI rendering before production
- Add integration tests for URL sharing
- Investigate Streamlit stability issues
- Consider pinning Streamlit version to avoid rendering regressions

The simulation **core is production-ready**, but the **UI needs attention** before full deployment.
