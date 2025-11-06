#!/usr/bin/env python3
"""Detailed JustWatch test to see all platforms returned"""

from simplejustwatchapi.justwatch import search

print("=" * 80)
print("JUSTWATCH DETAILED TEST: Tourist Family")
print("=" * 80)

results = search("Tourist Family", "IN", "en", 3, True)

print(f"\nTotal search results: {len(results)}")

for idx, entry in enumerate(results):
    print(f"\n--- Result {idx + 1} ---")
    print(f"Title: {entry.title}")
    print(f"Year: {entry.release_year if hasattr(entry, 'release_year') else 'N/A'}")

    if entry.title == "Tourist Family" and hasattr(entry, 'release_year') and entry.release_year == 2025:
        print(f"\n✅ MATCHED: Tourist Family (2025)")
        print(f"Total offers: {len(entry.offers) if hasattr(entry, 'offers') else 0}")

        if hasattr(entry, 'offers') and entry.offers:
            print("\n🎬 All platforms found:")
            for i, offer in enumerate(entry.offers):
                platform_name = offer.package.name
                print(f"  {i+1}. {platform_name}")

                # Show what our mapping would produce
                mapped_name = None
                if "Netflix" in platform_name:
                    mapped_name = "Netflix"
                elif "Prime" in platform_name or "Amazon" in platform_name:
                    mapped_name = "Prime Video"
                elif "JioHotstar" in platform_name:
                    mapped_name = "JioHotstar"
                elif "Disney" in platform_name or "Hotstar" in platform_name:
                    mapped_name = "Disney+ Hotstar"
                elif "Jio Cinema" in platform_name:
                    mapped_name = "Jio Cinema"
                elif "Zee5" in platform_name or "ZEE5" in platform_name:
                    mapped_name = "Zee5"
                elif "SonyLIV" in platform_name:
                    mapped_name = "SonyLIV"
                elif "Aha" in platform_name:
                    mapped_name = "Aha"
                elif "Sun NXT" in platform_name:
                    mapped_name = "Sun NXT"
                elif "Apple TV" in platform_name:
                    mapped_name = "Apple TV+"

                if mapped_name:
                    print(f"      -> Maps to: {mapped_name}")
                else:
                    print(f"      -> NO MAPPING (will be ignored)")
        break

print("\n" + "=" * 80)
