# Scheduler Timezone Fix

## Problem

`hiring_cafe_scheduler.py` had suspicious naive datetime handling in `_to_utc_mysql()`:

```python
# OLD CODE (BUGGY)
local_epoch = calendar.timegm(dt.timetuple())  # Treats naive as UTC!
dt = datetime.utcfromtimestamp(local_epoch)
```

**Issue**: `calendar.timegm()` interprets a naive datetime as **UTC**, not local time, despite the comment saying "local → epoch". This produced incorrect `next_run_at` timestamps.

### Root Cause

1. Server DB stores `next_run_at` as MySQL DATETIME (no timezone info)
2. Server Python code treats stored values as UTC
3. Scheduler was sending local time (e.g., 16:00 PST)
4. Server compared it as UTC 16:00 vs real UTC 00:00
5. Schedule appeared always overdue → fired every 5 min → logged FAILED

## Solution

**Use timezone-aware datetimes everywhere.**

### Changes Made

#### 1. Fixed `_to_utc_mysql()` (lines 56-68)

```python
# NEW CODE (CORRECT)
def _to_utc_mysql(dt: datetime) -> str:
    if dt.tzinfo is None:
        # Naive: treat as local system time
        dt = dt.astimezone(timezone.utc)
    else:
        # Already aware: convert to UTC
        dt = dt.astimezone(timezone.utc)
    
    return dt.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
```

**Key fix**: Use `astimezone()` which correctly interprets naive datetimes as local time and converts to UTC.

#### 2. Fixed `get_next_run_from_cron()` (lines 82-147)

- Use `zoneinfo.ZoneInfo` or `pytz.timezone` for timezone-aware calculations
- Create all candidate datetimes with explicit timezone
- Falls back to `datetime.now().astimezone()` if no timezone library

```python
# Get timezone-aware current time
if tz:
    now_local = datetime.now(tz)
else:
    now_local = datetime.now().astimezone()  # Local TZ

# Build timezone-aware candidates
if tz:
    candidate = datetime(..., tzinfo=tz)
else:
    candidate = datetime(...).astimezone()
```

#### 3. Fixed run name detection (line 416)

```python
# OLD
now_hour = datetime.now().hour  # Naive

# NEW
now_local = datetime.now().astimezone()
now_hour = now_local.hour  # Timezone-aware
```

## Verification

All tests pass (`test_timezone_fix.py`):

- ✓ Timezone-aware PST → UTC conversion
- ✓ Already-UTC datetime handling
- ✓ Naive datetime conversion (uses system local)
- ✓ MySQL DATETIME format validation
- ✓ Deterministic output

## Impact

### Before Fix

```
Local time: 2024-01-15 16:00:00 PST
Sent to DB: 2024-01-15 16:00:00      (interpreted as UTC by server)
Real UTC:   2024-01-16 00:00:00
Result:     Schedule appears 8 hours overdue
```

### After Fix

```
Local time: 2024-01-15 16:00:00 PST
Sent to DB: 2024-01-16 00:00:00      (correct UTC value)
Real UTC:   2024-01-16 00:00:00
Result:     Schedule fires at correct time
```

## Testing

```bash
# Run test suite
python test_timezone_fix.py

# Verify scheduler compiles
python -m py_compile hiring_cafe_scheduler.py
```

## Migration

No data migration needed. Next scheduler run will:
1. Calculate `next_run_at` correctly using fixed logic
2. Send proper UTC timestamp to server
3. Schedule will fire at correct time going forward

## Dependencies

**Preferred** (Python 3.9+):
- `zoneinfo` (built-in) - IANA timezone database

**Fallback** (Python < 3.9):
- `pytz` - Install via `pip install pytz`

**Minimum**:
- Works without external libs using `datetime.now().astimezone()`

## Related Files

- `hiring_cafe_scheduler.py` - Main scheduler logic
- `test_timezone_fix.py` - Verification tests
- `TIMEZONE_FIX.md` - This document
