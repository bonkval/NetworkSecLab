# Viewer, Command-Line Options, Audio, Threads, and Shutdown

## Why run modules with `-m`

```powershell
python -m monitor.viewer
python -m monitor.detector
```

`-m` tells Python to locate and execute a module through the import system. Because `monitor` contains `__init__.py`, it is a package. Running from the project root makes imports such as `from monitor.common import follow` work consistently.

## The live viewer

`viewer.py` deliberately contains no detection logic. It follows the log and prints each line. This separation lets the upper-right terminal remain a raw event stream while the lower terminal explains security decisions.

```python
color = RED if "STATUS: FAILED" in line else RESET
```

This is a conditional expression: choose `RED` when the condition is true, otherwise `RESET`.

## ANSI terminal colors

```python
RED = "\033[91m"
RESET = "\033[0m"
```

Escape character `\033` begins an ANSI control sequence. `91m` selects bright red, and `0m` resets formatting. These sequences are printed with the text and interpreted by compatible terminals.

## Command-line arguments

`argparse` turns command-line text into structured Python values.

```python
parser.add_argument("--no-popup", action="store_true")
```

Without the flag, the value is false. Including `--no-popup` stores true.

```python
parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
```

`type=Path` converts the supplied text to a Path object. A default is used when the option is omitted.

Examples:

```powershell
python -m monitor.detector --no-popup
python -m monitor.detector --from-start
python -m monitor.detector --test-alarm
python -m monitor.detector --log C:\temp\events.log
```

## Main functions and exit codes

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

`main()` returns `0` for success. `SystemExit` converts it into the process exit status. Nonzero statuses conventionally indicate errors.

## Graceful shutdown

```python
STOP_EVENT = threading.Event()
```

An Event is a thread-safe Boolean-like signal. Signal handlers call `.set()` when Ctrl+C produces `SIGINT` or when the process receives `SIGTERM`.

The follow loop repeatedly calls `.is_set()` and uses `.wait(timeout)` instead of `time.sleep`. If shutdown occurs during a wait, Event.wait returns immediately.

## Audio playback

On Windows, Python’s standard `winsound` module plays the PCM WAV file:

```python
winsound.PlaySound(str(alarm_path), winsound.SND_FILENAME)
```

On macOS, the code looks for `afplay`. On Linux, it looks for `aplay`. `shutil.which` checks whether the executable exists. `subprocess.run` launches it without passing through a command shell, which is safer than constructing a shell command string.

## Why audio runs in a thread

`PlaySound` is blocking in this implementation: it returns after playback. If the detector called it directly, log processing and terminal output would pause.

```python
threading.Thread(target=play_alarm, args=(alarm_path,), daemon=True).start()
```

- `target` is the function to execute.
- `args` is a tuple of positional arguments. The comma makes it a one-item tuple.
- `daemon=True` means the audio thread will not keep the entire process alive during shutdown.
- `.start()` creates the operating-system thread and calls the target there.

The popup uses another thread so its modal window does not block detection.

## Tkinter popup

Tkinter is Python’s standard GUI toolkit on many installations. The code creates a root window, hides it, marks it topmost, opens a warning dialog, and destroys the root after dismissal.

The broad exception handler makes the popup optional: if Tkinter is unavailable, the terminal and audio alert still work. In larger systems, catching and logging narrower exceptions is preferable.

## Terminal clearing and banner formatting

```python
os.system("cls" if os.name == "nt" else "clear")
```

Windows uses `cls`; Unix-like systems use `clear`.

Formatting such as `{ip_address:<57}` left-aligns text in a 57-character field. This keeps the ASCII border aligned for ordinary IP lengths.

## Testing the alarm separately

`--test-alarm` calls the same `play_alarm` function used during detection. This isolates audio setup from login and threshold logic:

```powershell
python -m monitor.detector --test-alarm
```
