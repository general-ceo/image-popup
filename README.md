# Menu Bar Image Flash

A macOS menu bar app. Click the icon and a random picture, GIF, or video flashes on
screen, then disappears on its own. Group your files into folders and pick which
folder to draw from — right from the menu bar.

There's no Dock icon and no app window; it lives entirely in the menu bar.

## Quick start

```bash
git clone https://github.com/general-ceo/image-popup.git
cd image-popup
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./run.sh
```

A small photo icon appears in your menu bar. The repo ships with two empty example
folders, so your first stop is adding some images — see below.

**Requires macOS** (it's built on AppKit and AVFoundation) and Python 3.8+.

Running `./run.sh` a second time is harmless: it notices the first copy and exits, so
you never end up with two icons.

### Running without keeping a terminal open

```bash
./run.sh --background   # detach; close the terminal and the icon stays
./run.sh --stop         # quit it again (or use Quit in the menu)
```

Started normally the app is a child of your shell, so closing the terminal window
kills it. `--background` detaches it so it keeps running on its own.

You'd do that once per login. Making it start **automatically** at login needs a
LaunchAgent or Login Item, and that only works if this folder lives **outside**
Desktop, Documents, and Downloads: macOS blocks anything it launches on your behalf
from reading those three folders until you grant permission, and that applies to
LaunchAgents, Login Items, and app bundles alike. Starting from a terminal is exempt,
because your terminal already holds that permission. Move the project to somewhere
like `~/Projects/image-popup` and a LaunchAgent becomes straightforward.

## Adding your own image folders

Every subfolder of `images/` automatically becomes a collection in the menu. That's
the whole setup — there is no config file and no code to edit.

1. Make a folder inside `images/`. Its name is exactly what shows up in the menu:

   ```bash
   mkdir images/Cats
   ```

2. Put pictures in it. Drag them in from Finder, or:

   ```bash
   cp ~/Downloads/*.jpg images/Cats/
   ```

3. Right-click the menu bar icon. **Cats** is now listed under **Collection** —
   no restart needed. Click it to make it active.

Supported file types:

| Kind | Extensions | How long it stays up |
| --- | --- | --- |
| Images | `.png` `.jpg` `.jpeg` `.tiff` `.bmp` `.heic` `.webp` | `DISPLAY_SECONDS` (1 second) |
| Animated GIFs | `.gif` | one full loop |
| Videos | `.mp4` `.mov` `.m4v` | until the clip ends |

A non-animated GIF is treated as a still image. Mix all three kinds in the same
folder — each file brings its own timing.

A folder layout like this:

```
images/
  Cats/
    fluffy.jpg
    grumpy.png
  Memes/
    reaction.jpg
  Album Art/
    cover.png
```

gives you this menu:

```
Show Random Image
─────────────────
Collection
  Album Art
✓ Cats
  Memes
─────────────────
  Random Position
✓ Include Video Audio
─────────────────
Quit
```

### Things worth knowing

- **The menu re-reads `images/` every time you open it**, so folders you add, rename,
  or delete show up immediately — the app keeps running.
- **Files are re-scanned on every click**, so you can drop a new one in and see it
  right away.
- **Folder names sort alphabetically**, ignoring case. Spaces are fine.
- **Folders starting with `.` are ignored**, as are loose files sitting directly in
  `images/` — only subfolders become collections.
- **Nested folders aren't searched.** Only images directly inside a collection folder
  are used; a folder inside a collection is ignored.
- **Deleting the active folder** falls back to the first remaining collection.
- **An empty folder still appears** in the menu; selecting it tells you it's empty
  rather than doing nothing. Hover any collection to see its image count.
- **With no folders at all**, the menu says so and *Show Random Image* is disabled.

## Using it

- **Left-click** the icon — flashes a random image from the active collection.
- **Right-click** (or control-click) — the options menu.

Exactly one collection is checked at a time, and only its images are ever shown.
Your choice is saved, so it's still active after a restart — as are *Random Position*
and *Include Video Audio*.

Within a collection the same image never appears twice in a row (when there's more
than one to choose from). Switching collections resets that.

## Random Position

*Random Position* is a checkbox in the menu. Off (the default), images appear
centered. On, each one lands somewhere random on screen. The setting is saved
across restarts.

Random placements stay inside the screen's visible area — excluding the menu bar and
Dock — with a `SCREEN_MARGIN` gap from every edge, so an image is never clipped or
hidden behind the Dock. If an image is too big for the screen to spare that margin,
the margin shrinks rather than pinning the window to one spot.

## GIFs and videos

**Animated GIFs** play once. The app adds up the frame delays stored in the file and
keeps the popup open for exactly that long, so the loop finishes instead of getting
cut off at one second. Frames that ask for ~0 delay are shown at
`MIN_GIF_FRAME_DELAY`, which is what browsers do too.

**Videos** play from start to finish and the popup closes on the last frame. Portrait
clips from a phone are sized using the file's rotation metadata, so they aren't shown
sideways. Videos play with sound by default; see *Include Video Audio* below.

Anything longer than `MAX_MEDIA_SECONDS` (30s) is cut off there, so one long clip
can't hold the screen. A file that can't be decoded shows a placeholder instead of
failing silently.

Clicking the icon during playback stops the current clip and starts a new one.

## Include Video Audio

A checkbox in the menu, on by default. Uncheck it to play videos silently — useful
when you want clips to flash past without interrupting whatever you're listening to.

Toggling it takes effect immediately, even mid-clip: a video that's playing right now
goes quiet the moment you uncheck it. The setting is saved and survives a restart,
and it has no effect on GIFs or still images, which have no audio to begin with.

## Popup behavior

The window is borderless with rounded corners and floats above other windows. It
ignores mouse events, so clicks pass straight through to whatever is underneath, and
it never takes keyboard focus — you can keep typing while it's on screen.

Images and videos scale proportionally into a 500pt box, so aspect ratio is preserved
and large files don't swallow the screen. Sizes snap to whole even points to stay aligned with
Retina displays, which keeps edges crisp.

Clicking the icon again while something is up swaps in a new file and restarts the
timer.

## Tuning

Constants at the top of `menubar_flash.py`:

| Constant | Default | Meaning |
| --- | --- | --- |
| `DISPLAY_SECONDS` | `1.0` | How long a still image stays up |
| `MAX_EDGE` | `500.0` | Longest side of the popup, in points |
| `CORNER_RADIUS` | `14.0` | Popup corner rounding |
| `SCREEN_MARGIN` | `5.0` | Minimum gap from screen edges in random mode |
| `MAX_MEDIA_SECONDS` | `30.0` | Hard cap on GIF loops and video length |
| `INCLUDE_AUDIO_DEFAULT` | `True` | First-run value of *Include Video Audio* |
| `MIN_GIF_FRAME_DELAY` | `0.1` | Rate used for GIF frames with ~0 delay |
| `IMAGE_DIR` | `images/` | Where collection folders are read from |

## Committing your images

The example folders are kept in git by empty `.gitkeep` files. If you'd rather not
push your own pictures, add this to `.gitignore`:

```gitignore
images/*/*
!images/*/.gitkeep
```

That keeps the folder structure in the repo while leaving the pictures themselves
out of it.

## Tests

```bash
./.venv/bin/python test_menubar_flash.py
```

112 checks, run against a temporary `images/` folder — they don't touch your files, and
they save and restore your menu settings. The suite generates its own animated GIF and
H.264 clip on the fly, so it needs no fixtures checked into the repo.

Covers folder auto-detection (sorting, hidden folders, loose files, adding and deleting
folders while running), collection switching and isolation, per-format timing (still vs.
GIF loop vs. video length), video playback and teardown, the duration cap, corrupt-file
fallback, click handling, rapid re-clicks, randomness, window geometry, both toggles
(including muting a clip mid-playback), and every empty state.
