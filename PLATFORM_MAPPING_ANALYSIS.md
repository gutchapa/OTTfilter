# Platform Mapping Analysis

## Issue
Tourist Family should show **both** JioHotstar AND Prime Video, but only showing one platform (Disney+ Hotstar).

## Code Changes Made

### 1. Added Detailed Logging (server.py:313-361)
```python
logger.info(f"🔍 JustWatch raw data for '{title}': {len(entry.offers)} offers found")
for offer in entry.offers:
    platform_name = offer.package.name
    logger.info(f"   📺 Raw platform name: '{platform_name}'")

    # ... mapping logic ...

    if mapped:
        logger.info(f"      ✅ Mapped to: '{mapped}'")

logger.info(f"🎬 JustWatch found {len(set(providers))} unique platforms for '{title}': {list(set(providers))}")
```

This logs:
- Total number of offers from JustWatch
- Each raw platform name before mapping
- What each platform gets mapped to
- Final deduplicated list

### 2. Platform Mapping Order (server.py:320-354)
The mapping checks are done with elif, so order matters:

1. Netflix
2. Prime/Amazon → "Prime Video"
3. **JioHotstar** → "JioHotstar" (NEW - post-merger)
4. **Disney/Hotstar** → "Disney+ Hotstar" (OLD - pre-merger)
5. Jio Cinema
6. Zee5
7. Sony → SonyLIV
8. Voot
9. MX → MX Player
10. Aha
11. Sun → Sun NXT
12. Others (if not Lionsgate/Channel)

## Possible Causes

### Theory 1: JustWatch Returns Old Name
JustWatch might still return "Hotstar" or "Disney+ Hotstar" instead of "JioHotstar":
- If JustWatch returns "Hotstar" → Matches line 330 → Maps to "Disney+ Hotstar" ✓
- If JustWatch returns "Disney+ Hotstar" → Matches line 330 → Maps to "Disney+ Hotstar" ✓

**Fix**: Update mapping to recognize both old and new names, but OUTPUT only new name:
```python
elif "JioHotstar" in platform_name or "Hotstar" in platform_name or "Disney" in platform_name:
    # Hotstar has been rebranded to JioHotstar after Disney-Jio merger
    providers.append("JioHotstar")
```

### Theory 2: Prime Video Name Mismatch
JustWatch might return Prime Video with a name that doesn't match our check:
- Current check: `"Prime" in platform_name or "Amazon" in platform_name`
- If JustWatch returns: "Prime Video India" → Should match ✓
- If JustWatch returns: "primevideo" (lowercase, no space) → Won't match ✗

**Fix**: Make check case-insensitive:
```python
platform_name_lower = platform_name.lower()
if "prime" in platform_name_lower or "amazon" in platform_name_lower:
    providers.append("Prime Video")
```

### Theory 3: Multiple Entries, Taking Wrong One
The year matching logic (lines 304-309) might be picking the wrong entry:
- If year=2025, it skips entries that don't match 2025
- If Tourist Family has multiple entries (different regions?), we might pick one without all platforms

**Fix**: Aggregate platforms from ALL matching entries, not just first match

### Theory 4: JustWatch Only Returns One Platform
JustWatch API might actually only return ONE platform per region/offer type:
- Flatrate (subscription): Hotstar
- Rent: Prime Video

We might need to process different offer types separately.

## Next Steps

1. **Deploy the logging changes** to VPS:
   ```bash
   cd /root/OTTfilter
   git pull origin claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ
   systemctl restart ottfilter-backend
   ```

2. **Search for "Tourist Family"** on http://103.118.17.51:8080/

3. **Check logs** to see raw JustWatch data:
   ```bash
   tail -100 /root/OTTfilter/backend/backend.log | grep -A 20 "Tourist Family"
   ```

4. **Analyze the logs** to determine:
   - How many offers does JustWatch return?
   - What are the exact raw platform names?
   - Are both Hotstar AND Prime Video in the offers?
   - What are they being mapped to?

5. **Apply the appropriate fix** based on log analysis

## Expected Log Output

```
🔍 JustWatch raw data for 'Tourist Family': 5 offers found
   📺 Raw platform name: 'Hotstar'
      ✅ Mapped to: 'Disney+ Hotstar'
   📺 Raw platform name: 'Amazon Prime Video'
      ✅ Mapped to: 'Prime Video'
   📺 Raw platform name: 'Apple TV'
   📺 Raw platform name: 'Google Play Movies'
   📺 Raw platform name: 'YouTube'
🎬 JustWatch found 2 unique platforms for 'Tourist Family': ['Disney+ Hotstar', 'Prime Video']
```

OR

```
🔍 JustWatch raw data for 'Tourist Family': 1 offers found
   📺 Raw platform name: 'Hotstar'
      ✅ Mapped to: 'Disney+ Hotstar'
🎬 JustWatch found 1 unique platforms for 'Tourist Family': ['Disney+ Hotstar']
```

The second case would mean JustWatch only returns one platform, not both.
