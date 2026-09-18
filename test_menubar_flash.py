"""Behavior tests for menubar_flash.

Runs against a throwaway images/ folder in a temp dir, so it neither depends on
nor touches your real pictures. Run: ./.venv/bin/python test_menubar_flash.py
"""

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBitmapImageRep,
    NSCalibratedRGBColorSpace,
    NSColor,
    NSControlStateValueOff,
    NSControlStateValueOn,
    NSGraphicsContext,
    NSMakeRect,
    NSPNGFileType,
    NSScreen,
)
from Foundation import NSDate, NSRunLoop, NSUserDefaults

import menubar_flash as mf

fails = []


def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + ((" | " + extra) if extra else ""))
    if not cond:
        fails.append(label)


def pump(seconds):
    """Advance the real run loop so NSTimers fire."""
    end = time.time() + seconds
    while time.time() < end:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            "kCFRunLoopDefaultMode", NSDate.dateWithTimeIntervalSinceNow_(0.02)
        )


def pump_until_dismissed(timeout=4.0):
    """Pump until the popup goes away; returns how long that took, or None."""
    start = time.time()
    while time.time() - start < timeout:
        pump(0.05)
        if c.window is None:
            return time.time() - start
    return None


def write_png(path, w=120, h=90):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0
    )
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(
        NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    )
    NSColor.grayColor().setFill()
    __import__("AppKit").NSBezierPath.fillRect_(NSMakeRect(0, 0, w, h))
    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, {}).writeToFile_atomically_(
        path, True
    )


def make_collection(name, count):
    folder = os.path.join(mf.IMAGE_DIR, name)
    os.makedirs(folder, exist_ok=True)
    for i in range(count):
        write_png(os.path.join(folder, f"{name.lower()}-{i}.png"))
    return folder


def shown_over(n):
    """Basenames of the images produced by n clicks."""
    out = set()
    for _ in range(n):
        c.showImage_(None)
        if c.last_image:
            out.add(os.path.basename(c.last_image))
        c.dismissWindow()
    return out


def titles():
    return [c.menu.itemAtIndex_(i).title() for i in range(c.menu.numberOfItems())]


# --- fixture: a temp images/ tree, unrelated to the real one ------------------

TMP = tempfile.mkdtemp(prefix="menubar_flash_test_")
REAL_IMAGE_DIR = mf.IMAGE_DIR
mf.IMAGE_DIR = os.path.join(TMP, "images")
os.makedirs(mf.IMAGE_DIR)
make_collection("Reaction", 6)
make_collection("Jazz", 4)
make_collection("aardvark", 2)  # lowercase: checks case-insensitive menu ordering
os.makedirs(os.path.join(mf.IMAGE_DIR, ".hidden"))  # must be ignored
write_png(os.path.join(mf.IMAGE_DIR, "loose.png"))  # a file, not a folder: ignored

app = NSApplication.sharedApplication()
app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

# The app and these tests share one NSUserDefaults domain, so stash the real
# preferences, run against a known state, and put them back at the end.
_defaults = NSUserDefaults.standardUserDefaults()
_saved = (
    _defaults.boolForKey_(mf.RANDOM_POSITION_KEY),
    _defaults.stringForKey_(mf.COLLECTION_KEY),
)


def restore_defaults():
    _defaults.setBool_forKey_(_saved[0], mf.RANDOM_POSITION_KEY)
    if _saved[1] is not None:
        _defaults.setObject_forKey_(_saved[1], mf.COLLECTION_KEY)
    shutil.rmtree(TMP, ignore_errors=True)
    mf.IMAGE_DIR = REAL_IMAGE_DIR


# Start from a saved name that no longer exists on disk, to exercise the fallback.
_defaults.setObject_forKey_("DeletedLongAgo", mf.COLLECTION_KEY)
c = mf.FlashController.alloc().init()
c.setUpStatusItem()
mf._controller = c
c.random_position = False  # geometry checks below assume centered
c.syncRandomItem()

# --- folder discovery ---------------------------------------------------------

check("subfolders discovered automatically",
      mf.find_collections() == ["aardvark", "Jazz", "Reaction"], str(mf.find_collections()))
check("sorted case-insensitively", mf.find_collections()[0] == "aardvark")
check("hidden folders ignored", ".hidden" not in mf.find_collections())
check("loose files are not collections", "loose.png" not in mf.find_collections())
check("menu built from discovery",
      titles() == ["Show Random Image", "", "Collection", "aardvark", "Jazz", "Reaction", "",
                   "Random Position", "", "Quit"], str(titles()))
check("Collection header is a disabled label", not c.menu.itemAtIndex_(2).isEnabled())
check("item tooltip reports the image count",
      c.collection_items["Jazz"].toolTip() == "4 images in images/Jazz",
      c.collection_items["Jazz"].toolTip())
check("stale saved name falls back to the first collection",
      c.collection == "aardvark", str(c.collection))

_defaults.setObject_forKey_("Reaction", mf.COLLECTION_KEY)
_resumed = mf.FlashController.alloc().init()
check("a valid saved name is restored on launch", _resumed.collection == "Reaction",
      str(_resumed.collection))
_defaults.setObject_forKey_(c.collection, mf.COLLECTION_KEY)

# --- popup basics -------------------------------------------------------------

c.selectCollection_(c.collection_items["Jazz"])
c.showImage_(None)
w = c.window
check("window created on click", w is not None)
check("window is visible", w.isVisible())
check("window is borderless/transparent", not w.isOpaque() and w.styleMask() == 0)
check("window ignores mouse (click-through)", w.ignoresMouseEvents())
check("window floats above others", w.level() == 25, f"level={w.level()}")
sz = w.frame().size
img = w.contentView().subviews()[0].image()
check("scaled within the %dpt cap" % mf.MAX_EDGE, max(sz.width, sz.height) <= mf.MAX_EDGE,
      f"{sz.width}x{sz.height}")
check("window matches requested size exactly (no Retina drift)",
      (sz.width, sz.height) == tuple(c.contentSize(img)),
      f"{sz.width}x{sz.height} vs {c.contentSize(img)}")
check("image view fills the window",
      tuple(w.contentView().subviews()[0].frame().size) == (sz.width, sz.height))
_s = img.size()
check("aspect ratio preserved within 1%",
      abs((sz.width / sz.height) - (_s.width / _s.height)) / (_s.width / _s.height) < 0.01,
      f"{sz.width/sz.height:.4f} vs {_s.width/_s.height:.4f}")
vis = NSScreen.mainScreen().visibleFrame()
check("centered horizontally",
      abs(w.frame().origin.x + sz.width / 2 - (vis.origin.x + vis.size.width / 2)) < 1)

pump(0.6)
check("still visible at 0.6s", c.window is not None and c.window.isVisible())
elapsed = pump_until_dismissed()
check("auto-dismissed on its own", elapsed is not None)
check("dismissal lands near DISPLAY_SECONDS",
      elapsed is not None and abs((0.6 + elapsed) - mf.DISPLAY_SECONDS) < 0.35,
      f"{0.6 + elapsed:.2f}s vs {mf.DISPLAY_SECONDS}s" if elapsed else "never")

c.showImage_(None)
first_w = c.window
c.showImage_(None)
check("re-click replaces window", first_w is not c.window and not first_w.isVisible())
check("only the new window is visible", c.window.isVisible())
check("dismissed once after rapid clicks", pump_until_dismissed() is not None)

seen, repeats, prev = set(), 0, c.last_image
for _ in range(60):
    c.pickImage()
    if c.last_image == prev:
        repeats += 1
    prev = c.last_image
    seen.add(os.path.basename(c.last_image))
check("all images in the collection reachable",
      len(seen) == len(mf.find_images("Jazz")), f"{len(seen)}/{len(mf.find_images('Jazz'))}")
check("never repeats back-to-back", repeats == 0, f"{repeats} repeats")

# --- collection selection -----------------------------------------------------

jazz, reaction = c.collection_items["Jazz"], c.collection_items["Reaction"]
jazz_files = {os.path.basename(p) for p in mf.find_images("Jazz")}
reaction_files = {os.path.basename(p) for p in mf.find_images("Reaction")}
check("only the active collection is checked",
      (jazz.state(), reaction.state()) == (NSControlStateValueOn, NSControlStateValueOff))
check("Jazz active -> only Jazz images", shown_over(25) == jazz_files)

c.selectCollection_(reaction)
check("switching activates Reaction", c.collection == "Reaction")
check("checkmark moves, never both",
      (jazz.state(), reaction.state()) == (NSControlStateValueOff, NSControlStateValueOn))
check("selection persisted",
      _defaults.stringForKey_(mf.COLLECTION_KEY) == "Reaction")
check("no-repeat memory cleared on switch", c.last_image is None)
_shown = shown_over(45)
check("Reaction active -> only Reaction images", _shown == reaction_files,
      f"{len(_shown)}/{len(reaction_files)}")
check("no cross-collection leakage", _shown.isdisjoint(jazz_files))

_prev = c.last_image
c.selectCollection_(reaction)
check("re-selecting the active one is a no-op", c.last_image == _prev)

# --- folders added / removed while running ------------------------------------

make_collection("Cats", 3)
check("new folder not in the menu until reopened", "Cats" not in c.collection_items)
c.menuWillOpen_(c.menu)
check("new folder appears on menu open", "Cats" in c.collection_items, str(titles()))
check("new folder slots into sort order",
      titles()[3:7] == ["aardvark", "Cats", "Jazz", "Reaction"], str(titles()[3:7]))
check("active collection survives a rebuild", c.collection == "Reaction")
check("checkmark survives a rebuild",
      c.collection_items["Reaction"].state() == NSControlStateValueOn)
check("added folder's images are usable",
      (c.selectCollection_(c.collection_items["Cats"]), shown_over(20))[1]
      == {os.path.basename(p) for p in mf.find_images("Cats")})

shutil.rmtree(os.path.join(mf.IMAGE_DIR, "Cats"))
c.menuWillOpen_(c.menu)
check("deleted folder leaves the menu", "Cats" not in c.collection_items)
check("deleting the active folder falls back to the first",
      c.collection == "aardvark", str(c.collection))
check("fallback is persisted", _defaults.stringForKey_(mf.COLLECTION_KEY) == "aardvark")
c.showImage_(None)
check("still works after the fallback",
      os.path.basename(c.last_image) in {os.path.basename(p) for p in mf.find_images("aardvark")})
c.dismissWindow()

# --- empty states -------------------------------------------------------------

os.makedirs(os.path.join(mf.IMAGE_DIR, "Empty"))
c.menuWillOpen_(c.menu)
c.selectCollection_(c.collection_items["Empty"])
check("empty folder is still selectable", c.collection == "Empty")
c.showImage_(None)
check("empty collection shows a named placeholder",
      "No images in Empty" in c.window.contentView().subviews()[0].stringValue())
check("placeholder auto-dismisses", pump_until_dismissed() is not None)
check("empty folder tooltip says 0 images",
      c.collection_items["Empty"].toolTip() == "0 images in images/Empty")

for name in mf.find_collections():
    shutil.rmtree(os.path.join(mf.IMAGE_DIR, name))
c.menuWillOpen_(c.menu)
check("no folders -> no collection active", c.collection is None)
check("no folders -> placeholder menu row",
      titles()[3] == "No folders in images/", str(titles()))
check("no folders -> that row is disabled", not c.menu.itemAtIndex_(3).isEnabled())
check("no folders -> Show Random Image is disabled", not c.menu.itemAtIndex_(0).isEnabled())
c.showImage_(None)
check("no folders -> guidance placeholder",
      "No image folders yet" in c.window.contentView().subviews()[0].stringValue())
check("guidance placeholder dismisses", pump_until_dismissed() is not None)

make_collection("Later", 2)
c.menuWillOpen_(c.menu)
check("recovers when a folder is created", c.collection == "Later")
check("Show Random Image re-enabled", c.menu.itemAtIndex_(0).isEnabled())
c.showImage_(None)
check("shows images again", c.window.contentView().subviews()[0].image() is not None)
c.dismissWindow()

# --- random position ----------------------------------------------------------

check("unchecked when off", c.random_item.state() == NSControlStateValueOff)
c.showImage_(None)
centered = c.window.frame()
c.dismissWindow()
check("off -> centered",
      abs(centered.origin.x + centered.size.width / 2 - (vis.origin.x + vis.size.width / 2)) < 1
      and abs(centered.origin.y + centered.size.height / 2 - (vis.origin.y + vis.size.height / 2)) < 1)

c.toggleRandomPosition_(None)
check("toggle turns it on", c.random_position is True)
check("checkmark appears", c.random_item.state() == NSControlStateValueOn)
check("choice persisted", _defaults.boolForKey_(mf.RANDOM_POSITION_KEY) is True)

origins, on_screen = set(), True
for _ in range(40):
    c.showImage_(None)
    f = c.window.frame()
    origins.add((round(f.origin.x, 1), round(f.origin.y, 1)))
    if not (f.origin.x >= vis.origin.x and f.origin.y >= vis.origin.y
            and f.origin.x + f.size.width <= vis.origin.x + vis.size.width
            and f.origin.y + f.size.height <= vis.origin.y + vis.size.height):
        on_screen = False
    c.dismissWindow()
check("on -> positions vary", len(origins) > 30, f"{len(origins)} distinct spots in 40 shows")
check("always fully on screen (menu bar/Dock excluded)", on_screen)
xs, ys = [p[0] for p in origins], [p[1] for p in origins]
check("spreads across width", max(xs) - min(xs) > vis.size.width * 0.3, f"{max(xs)-min(xs):.0f}pt")
check("spreads across height", max(ys) - min(ys) > vis.size.height * 0.3, f"{max(ys)-min(ys):.0f}pt")
check("respects edge margin",
      min(xs) >= vis.origin.x + mf.SCREEN_MARGIN - 0.5
      and min(ys) >= vis.origin.y + mf.SCREEN_MARGIN - 0.5)

c.toggleRandomPosition_(None)
check("toggle turns it back off",
      c.random_position is False and c.random_item.state() == NSControlStateValueOff)

restore_defaults()
print("\nrestored your settings: Random Position=%s, Collection=%s" % _saved)
print("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
