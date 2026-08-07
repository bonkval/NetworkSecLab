# The Detector and Sliding Time Window

> Scope: this lesson explains the standalone five-attempt sliding-window detector. The integrated `security/engine.py` also correlates password spraying, credential stuffing, distributed attacks, and Suricata alerts into incidents.

## Parsing events with a regular expression

`EVENT_PATTERN` defines the exact accepted line format. Named groups capture values:

```python
match.group("timestamp")
match.group("ip")
match.group("email")
```

`fullmatch()` rejects lines with extra or missing text. Malformed lines are printed and skipped instead of crashing the monitor.

## Constants

```python
THRESHOLD = 5
WINDOW_SECONDS = 30
```

Uppercase names conventionally mean configuration constants. Python does not enforce immutability.

## The detector’s state

```python
self.histories = defaultdict(deque)
```

This combines two data structures:

- A dictionary maps each IP address to its own history.
- A deque stores timestamps in chronological order.

Conceptually:

```text
{
  "127.0.0.1": [12:00:01, 12:00:04, 12:00:08],
  "10.0.0.8":  [12:00:06]
}
```

`defaultdict(deque)` automatically creates an empty deque when a new IP appears. A deque supports efficient removal from the left with `popleft()`.

## The class constructor

```python
def __init__(self, threshold=THRESHOLD, window_seconds=WINDOW_SECONDS):
```

`__init__` initializes each instance. `self` refers to that specific object. Default arguments use the constants but allow tests or experiments to supply other values.

```python
self.window = timedelta(seconds=window_seconds)
```

A `timedelta` represents a duration and can be subtracted from a `datetime`.

## Recording an attempt

```python
history = self.histories[ip_address]
history.append(event_time)
cutoff = event_time - self.window
```

The attempt is appended, then the oldest allowed timestamp is calculated.

```python
while history and history[0] < cutoff:
    history.popleft()
```

This is the sliding-window eviction step.

- `history` is false when empty.
- `history[0]` is the oldest timestamp.
- `< cutoff` means strictly older than 30 seconds is expired.
- The loop removes expired timestamps until the first remaining timestamp is valid.

Because timestamps are ordered, there is no need to examine newer entries after finding a valid oldest entry.

## Why the count “goes down”

Suppose attempts occurred at seconds 0, 4, 10, and 15. At second 35, the cutoff is second 5. Attempts at 0 and 4 are evicted, so the count falls from four to the remaining attempts at 10 and 15 plus the new attempt at 35.

The current implementation performs eviction when a new event arrives. It does not redraw an idle count every second. When you next submit after 30 seconds, you see that old attempts no longer count.

## Trigger and reset

```python
if count >= self.threshold:
    history.clear()
    return True, count
return False, count
```

The method returns a tuple: whether to alarm and the count that caused the decision. Clearing only that IP prevents one alert from immediately repeating on the next attempt and leaves other IP histories untouched.

Tuple unpacking occurs here:

```python
alarm, count = detector.record(ip_address, event_time)
```

## Complexity

Each timestamp is appended once and removed once. Although eviction uses a loop, the amortized processing cost is O(1) per event. Memory is proportional to recent attempts retained for active IPs.

One improvement for a long-running production service would periodically delete dictionary keys whose deques are empty, preventing unused IP keys from accumulating indefinitely.

## Event time versus arrival time

The detector uses the timestamp written in the log. This supports deterministic replay with `--from-start`. In a hostile environment, trusted ingestion time would be safer because manipulated or badly ordered timestamps could confuse the window.

## `run_detector`

The loop:

1. Receives a line from `follow()`.
2. Validates it with the regex.
3. parses its timestamp using `datetime.strptime`.
4. extracts the IP.
5. updates detector state.
6. prints the live count.
7. calls `trigger_alarm()` when the Boolean is true.

This separation makes `FailedAttemptDetector` testable without opening files, producing sound, or creating popups.
