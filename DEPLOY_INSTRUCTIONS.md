# Deployment Instructions for VPS

## Changes Made
- Added detailed JustWatch platform extraction logging
- This will help diagnose why Prime Video not showing for Tourist Family

## Deploy to VPS (103.118.17.51)

SSH to the VPS and run:

```bash
cd /root/OTTfilter
git fetch origin
git checkout claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ
git pull origin claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ
systemctl restart ottfilter-backend
```

## Test the Changes

1. Search for "Tourist Family" on the frontend: http://103.118.17.51:8080/

2. Check the logs to see JustWatch raw platform data:
```bash
tail -100 /root/OTTfilter/backend/backend.log | grep -A 10 "JustWatch raw data"
```

You should see output like:
```
🔍 JustWatch raw data for 'Tourist Family': X offers found
   📺 Raw platform name: 'Hotstar'
      ✅ Mapped to: 'Disney+ Hotstar'
   📺 Raw platform name: 'Amazon Prime Video'
      ✅ Mapped to: 'Prime Video'
🎬 JustWatch found 2 unique platforms for 'Tourist Family': ['Disney+ Hotstar', 'Prime Video']
```

## What to Look For

The logs will show:
1. **Total offers**: How many streaming options JustWatch returned
2. **Raw platform names**: Exact names as returned by JustWatch API
3. **Mapped names**: What our code converted them to
4. **Final unique platforms**: The deduplicated list that gets stored

This will help us understand if:
- JustWatch is returning both JioHotstar AND Prime Video
- The platform names are being matched correctly
- The mapping is working as expected
