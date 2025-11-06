# Potential Fix for Platform Mapping

## Most Likely Issue
Based on user feedback, Tourist Family is showing "Disney+ Hotstar" when it should show "JioHotstar".

This suggests JustWatch is returning "Hotstar" as the platform name, which is matching our old mapping.

## Solution: Map All Hotstar Variants to JioHotstar

Since Hotstar has been fully merged with Jio and rebranded as JioHotstar in India, we should map all "Hotstar" references to "JioHotstar":

### Current Code (server.py:326-333)
```python
elif "JioHotstar" in platform_name:
    # JioHotstar is the NEW platform after Disney-Jio merger
    mapped = "JioHotstar"
    providers.append(mapped)
elif "Disney" in platform_name or "Hotstar" in platform_name:
    # Old Disney+ Hotstar (before merger)
    mapped = "Disney+ Hotstar"
    providers.append(mapped)
```

### Fixed Code
```python
elif "Hotstar" in platform_name or "Disney" in platform_name:
    # Hotstar rebranded to JioHotstar after Disney-Jio merger
    # Map all Hotstar variants to the new name
    mapped = "JioHotstar"
    providers.append(mapped)
```

## Alternative: Case-Insensitive Matching

If the issue is that platform names have unexpected casing, we should make all checks case-insensitive:

```python
platform_name_lower = platform_name.lower()

if "netflix" in platform_name_lower:
    mapped = "Netflix"
    providers.append(mapped)
elif "prime" in platform_name_lower or "amazon" in platform_name_lower:
    mapped = "Prime Video"
    providers.append(mapped)
elif "hotstar" in platform_name_lower or "disney" in platform_name_lower:
    mapped = "JioHotstar"
    providers.append(mapped)
# ... etc
```

## To Apply After Log Analysis

Once we see the logs and confirm the issue, apply the appropriate fix and commit:

```bash
# Edit server.py with the fix
# Then commit and push
git add backend/server.py
git commit -m "Fix: Map all Hotstar variants to JioHotstar (post-merger name)"
git push origin claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ
```
