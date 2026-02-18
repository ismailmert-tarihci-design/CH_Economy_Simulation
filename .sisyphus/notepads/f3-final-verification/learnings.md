## QA Testing Learnings - F3 Final Verification

### Successful Testing Patterns
1. **Playwright for UI automation**: Effective for navigation, clicking, and visual verification
2. **Python CLI for edge cases**: Faster and more reliable than UI testing for logic validation
3. **Performance benchmarking via CLI**: Direct simulation calls provide accurate timing data
4. **Screenshot evidence**: Captures visual state for later review

### Simulation Engine Strengths
- **Zero-crash robustness**: All edge cases (zero packs, single day, 500 runs) handled gracefully
- **Excellent performance**: 8.35s for 100×100 Monte Carlo (well under 120s threshold)
- **Deterministic reproducibility**: 0.08s for 100-day simulation
- **Dashboard rendering**: All 4 charts render correctly with proper legends and data

### Testing Challenges
- Streamlit's `st.data_editor` doesn't expose editable elements in accessibility tree
- Long-running Playwright sessions can cause Streamlit disconnection
- Pydantic serialization warnings in session state (int vs str type mismatches)

### Recommendations
1. Add integration tests for URL sharing (don't rely solely on manual QA)
2. Pin Streamlit version to avoid rendering regressions
3. Use Python CLI tests for performance and edge case validation
4. Supplement Playwright with manual spot checks for complex interactions
