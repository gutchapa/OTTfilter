# How to Check Logs on VPS

The backend logs to stdout/stderr (systemd journal), not to a file.

## Check if Backend is Running

```bash
systemctl status ottfilter-backend
```

## View Recent Logs (Last 100 lines)

```bash
journalctl -u ottfilter-backend -n 100 --no-pager
```

## View Logs in Real-Time (Follow mode)

```bash
journalctl -u ottfilter-backend -f
```

## Search for Tourist Family in Logs

```bash
journalctl -u ottfilter-backend -n 500 --no-pager | grep -i "tourist family" -A 20
```

## OR if logs are in a different location

```bash
# Find any log files in backend directory
find /root/OTTfilter/backend -name "*.log" -type f

# Check if logs are in /var/log
ls -la /var/log/ | grep ott

# Check backend directory
ls -la /root/OTTfilter/backend/
```

## Test the Search Directly

```bash
# From VPS, test the API directly
curl -s "http://localhost:8001/api/natural-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "tourist family"}' | python3 -m json.tool | head -100
```

## If Backend Not Running

```bash
# Check if backend was pulled correctly
cd /root/OTTfilter
git log --oneline -5
git branch

# Restart backend
systemctl restart ottfilter-backend

# Check status
systemctl status ottfilter-backend

# View startup logs
journalctl -u ottfilter-backend -n 50 --no-pager
```

## Expected Output in Logs

After searching for "Tourist Family", you should see:

```
🔍 JustWatch raw data for 'Tourist Family': X offers found
   📺 Raw platform name: '...'
      ✅ Mapped to: '...'
🎬 JustWatch found X unique platforms for 'Tourist Family': [...]
```

This will tell us exactly what JustWatch is returning.
