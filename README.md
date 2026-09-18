# Menu Bar Image Flash

A macOS menu bar app. Click the icon and a random image flashes on screen for one
second, then disappears on its own. Group your images into folders and pick which
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

**Requires macOS** (it's built on AppKit) and Python 3.8+.

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

Supported file types: `.png` `.jpg` `.jpeg` `.gif` `.tiff` `.bmp` `.heic` `.webp`.

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
─────────────────
Quit
```

### Things worth knowing

- **The menu re-reads `images/` every time you open it**, so folders you add, rename,
  or delete show up immediately — the app keeps running.
- **Images are re-scanned on every click**, so you can drop a new picture in and see
  it right away.
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
Your choice is saved, so it's still active after a restart.

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

## Popup behavior

The window is borderless with rounded corners and floats above other windows. It
ignores mouse events, so clicks pass straight through to whatever is underneath, and
it never takes keyboard focus — you can keep typing while it's on screen.

Images scale proportionally into a 500pt box, so aspect ratio is preserved and large
photos don't swallow the screen. Sizes snap to whole even points to stay aligned with
Retina displays, which keeps edges crisp.

Clicking the icon again while an image is up swaps in a new one and restarts the timer.

## Tuning

Constants at the top of `menubar_flash.py`:

| Constant | Default | Meaning |
| --- | --- | --- |
| `DISPLAY_SECONDS` | `1.0` | How long the image stays up |
| `MAX_EDGE` | `500.0` | Longest side of the popup, in points |
| `CORNER_RADIUS` | `14.0` | Popup corner rounding |
| `SCREEN_MARGIN` | `5.0` | Minimum gap from screen edges in random mode |
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

70 checks, run against a temporary `images/` folder in `/tmp` — they don't touch your
pictures, and they save and restore your menu settings. Covers folder auto-detection
(sorting, hidden folders, loose files, adding and deleting folders while running),
collection switching and isolation, click handling, the one-second dismissal, rapid
re-clicks, randomness, window geometry, the Random Position toggle, and every empty
state.
