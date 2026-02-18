## QA Testing Issues - F3 Final Verification

### Config Editor UI Bug (HIGH SEVERITY)
- **Issue**: `st.data_editor` components render as read-only in accessibility tree
- **Impact**: Cannot verify editability via Playwright automation
- **Root Cause**: Likely Streamlit version incompatibility or rendering issue
- **Code Location**: `pages/config_editor.py` lines 57-73 (pack averages), 95-112 (card types)
- **Evidence**: 
  - Code calls `st.data_editor()` with editable columns
  - UI snapshot shows no `[data-testid="stDataEditor"]` elements
  - Only `[data-testid="stDataFrame"]` elements found
- **Action Required**: Manual testing or Streamlit version investigation

### Streamlit App Stability (MEDIUM SEVERITY)
- **Issue**: App disconnected during extended Playwright testing
- **Symptoms**: "Connection error" dialog, "Connecting" banner, disabled navigation
- **Logs**: "Stopping..." message after Pydantic serialization warnings
- **Impact**: Prevented URL sharing and Monte Carlo UI testing
- **Action Required**: 
  - Review session state serialization
  - Investigate Pydantic warnings about int vs str types
  - Test with different Streamlit versions

### URL Sharing - Not Tested
- **Reason**: App became unstable before reaching URL sharing tests
- **Impact**: Cannot verify shareable URL round-trip functionality
- **Action Required**: Retest in stable environment or add integration tests
