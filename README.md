# Menu Bar Image Flash

A macOS menu bar app. Click the icon and a random image from `images/` appears in the
middle of the screen for one second, then disappears on its own.

## Run

```bash
./run.sh
```

A small photo icon appears in the menu bar. There is no Dock icon and no app window —
it lives entirely in the menu bar.

- **Left-click** the icon — flashes a random image for 1 second.
- **Right-click** (or control-click) — menu with *Show Random Image*, the collection
  picker, *Random Position*, and *Quit*.

## Random Position

*Random Position* in the right-click menu is a checkbox. Off (the default), images
appear centered. On, each image lands somewhere random on screen instead.

The checkmark reflects the current state, and the setting is saved to `NSUserDefaults`,
so it stays on across restarts. Random placements are kept inside the screen's
`visibleFrame` — excluding the menu bar and Dock — with a `SCREEN_MARGIN` gap from
every edge, so the image is always fully visible and never clipped. If an image is
too large for the screen to spare that margin, the margin shrinks rather than
pinning the window to one spot.

## Collections

Images live in two subfolders, and the right-click menu picks which one is used:

```
images/
  Jazz/
  Reaction/
```

*Jazz* and *Reaction* sit under a **Collection** heading in the menu. They behave as a
radio pair — exactly one is checked, and clicking the checked one does nothing. Only
images from the checked collection are ever shown. The choice is saved to
`NSUserDefaults`, so it survives a restart.

To add a third collection, make the folder and add its name to `COLLECTIONS` in
`menubar_flash.py`; the menu builds itself from that tuple. A name saved from a
previous run that's no longer in `COLLECTIONS` falls back to the first entry.

## Images

Drop images into `images/Jazz/` or `images/Reaction/`. They're re-scanned on every
click, so you can add, remove, or move files between collections while the app is
running. Supported: `.png .jpg .jpeg .gif .tiff .bmp .heic .webp`.

Within a collection the same image is never shown twice in a row (when there's more
than one to choose from); switching collections clears that memory. If the active
collection's folder is empty or missing, the popup says so by name instead of
showing nothing.

`images/Jazz/` currently holds three `placeholder-*.png` files so the collection
isn't empty out of the box — delete them once you add real images.

## Popup behavior

The window is borderless, transparent-cornered, and floats above other windows.
It ignores mouse events, so clicks pass straight through to whatever is underneath,
and it never steals keyboard focus — typing is uninterrupted while it's on screen.
Images are scaled proportionally to fit a 500pt box, so aspect ratio is preserved
and large photos don't fill the screen.

Clicking the icon again while an image is up swaps in a new one and restarts the timer.

## Tuning

Constants at the top of `menubar_flash.py`:

| Constant | Default | Meaning |
| --- | --- | --- |
| `DISPLAY_SECONDS` | `1.0` | How long the image stays up |
| `MAX_EDGE` | `500.0` | Longest side of the popup, in points |
| `CORNER_RADIUS` | `14.0` | Popup corner rounding |
| `SCREEN_MARGIN` | `20.0` | Minimum gap from screen edges in random mode |
| `IMAGE_DIR` | `images/` | Where images are read from |

## Setup from scratch

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Tests

```bash
./.venv/bin/python test_menubar_flash.py
```

Covers click handling, the 1-second dismissal, rapid re-clicks, image randomness,
window geometry, the Random Position toggle (checkmark state, persistence, spread,
and on-screen bounds), and the empty-folder fallback.
