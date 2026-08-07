# The File-Based Event Pipeline

> Scope: this lesson covers the original append-only authentication log used by the standalone viewer and alarm detector. The web dashboard additionally persists normalized events in SQLite and writes redacted SNMP audit records as JSON Lines.

## Why use a file

The log file is a simple local communication channel. The web server is a producer. The viewer and detector are independent consumers.

```text
Producer: app.record_failed_login()
Shared channel: logs/login_attempts.log
Consumers: monitor.viewer and monitor.detector
```

The server has no import from `monitor`. The monitors have no import from `app`. Their agreement is the text event format and log path.

## Event format

```text
[2026-08-05 12:30:15] IP: 127.0.0.1 - EMAIL: attacker@gmail.com - STATUS: FAILED
```

Structured text is easier to parse than free-form sentences. Each field has a predictable label and separator.

## Writing an event

```python
with LOG_PATH.open("a", encoding="utf-8", buffering=1) as log_file:
    log_file.write(event)
    log_file.flush()
    os.fsync(log_file.fileno())
```

- Append mode positions writes at the end.
- UTF-8 provides a predictable text encoding.
- Line buffering encourages flushing after newline boundaries.
- `flush()` empties Python’s buffer.
- `fileno()` gets the operating-system file descriptor.
- `fsync()` requests storage synchronization.
- Leaving the `with` block closes the handle, even if an exception occurs.

This is deliberately durability-oriented. A high-volume production logger would normally use the `logging` package, a queue, rotation, and perhaps asynchronous batching.

## Following a growing file

`monitor/common.py` contains the generator `follow()`.

A generator uses `yield` instead of returning all results at once:

```python
yield line.rstrip("\r\n")
```

Each consumer requests the next line. When there is no new line, the generator waits and later continues from the same local state.

## Starting at the end

```python
log_file.seek(0, os.SEEK_END)
```

`seek` moves the read cursor. Offset zero relative to `SEEK_END` means the current end. This imitates `tail -f`: old entries are ignored and only new events appear.

The `--from-start` option changes this behavior, which is useful for replay and testing.

## Polling without high CPU usage

When `readline()` returns an empty string, no complete new text is currently available. The code waits on a threading event:

```python
stop_event.wait(POLL_INTERVAL)
```

`POLL_INTERVAL` is 0.05 seconds. Waiting yields CPU time instead of spinning continuously. The maximum ordinary detection delay from polling is roughly 50 milliseconds plus filesystem scheduling.

## File truncation and recreation

The current cursor is saved:

```python
position = log_file.tell()
```

If the file size becomes smaller than this position, the log was probably truncated. The inner loop breaks so the outer loop can reopen it.

If the file disappears, `FileNotFoundError` is handled. The monitor prints one warning, waits half a second, and keeps trying. This resilience lets the monitor survive startup ordering and basic log rotation.

## File locking

Readers open the file in read mode and do not request an exclusive lock. The server opens it only for a short append operation. This keeps the text file usable by multiple programs.

## Trust boundary

The detector treats matching log lines as events. If another local program can edit the log, it can create false alerts or remove evidence. A production system would restrict file permissions and send events to a protected logging service or append-only store.
