"""Behavior tests for menubar_flash. Run: ./.venv/bin/python test_menubar_flash.py"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from Foundation import NSRunLoop, NSDate
import menubar_flash as mf

fails = []
def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + ((" | " + extra) if extra else ""))
    if not cond: fails.append(label)

def pump(seconds):
    """Advance the real run loop so NSTimers fire."""
    end = time.time() + seconds
    while time.time() < end:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            "kCFRunLoopDefaultMode", NSDate.dateWithTimeIntervalSinceNow_(0.02))


def pump_until_dismissed(timeout=4.0):
    """Pump until the popup goes away; returns how long that took, or None."""
    start = time.time()
    while time.time() - start < timeout:
        pump(0.05)
        if c.window is None:
            return time.time() - start
    return None

app = NSApplication.sharedApplication()
app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
c = mf.FlashController.alloc().init()
c.setUpStatusItem()
mf._controller = c

# The app and these tests share one NSUserDefaults domain, so stash the real
# preferences, run against a known state, and put them back at the end.
_defaults = __import__("Foundation").NSUserDefaults.standardUserDefaults()
_saved = (_defaults.boolForKey_(mf.RANDOM_POSITION_KEY), _defaults.stringForKey_(mf.COLLECTION_KEY))

def restore_defaults():
    _defaults.setBool_forKey_(_saved[0], mf.RANDOM_POSITION_KEY)
    if _saved[1] is not None:
        _defaults.setObject_forKey_(_saved[1], mf.COLLECTION_KEY)

c.random_position = False          # geometry checks below assume centered
c.collection = mf.COLLECTIONS[0]   # and the first collection
c.syncCollectionItems()
c.syncRandomItem()

check("status item + button created", c.status_item is not None and c.status_item.button() is not None)
titles = [c.menu.itemAtIndex_(i).title() for i in range(c.menu.numberOfItems())]
check("menu layout",
      titles == ["Show Random Image", "", "Collection", "Jazz", "Reaction", "",
                 "Random Position", "", "Quit"], str(titles))
check("Collection header is a disabled label", not c.menu.itemAtIndex_(2).isEnabled())
check("Jazz is the default collection", mf.COLLECTIONS[0] == "Jazz")
for _name in mf.COLLECTIONS:
    check(f"{_name} folder has images", len(mf.find_images(_name)) > 0, f"{len(mf.find_images(_name))} files")

# --- single click ---
c.showImage_(None)
w = c.window
check("window created on click", w is not None)
check("window is visible", w.isVisible())
check("window is borderless/transparent", not w.isOpaque() and w.styleMask() == 0)
check("window ignores mouse (click-through)", w.ignoresMouseEvents())
check("window floats above others", w.level() == 25, f"level={w.level()}")
sz = w.frame().size
check("scaled within the %dpt cap" % mf.MAX_EDGE, max(sz.width, sz.height) <= mf.MAX_EDGE, f"{sz.width}x{sz.height}")
img = c.window.contentView().subviews()[0].image()
check("window matches requested size exactly (no Retina drift)",
      (sz.width, sz.height) == tuple(c.contentSize(img)), f"{sz.width}x{sz.height} vs {c.contentSize(img)}")
check("image view fills the window",
      tuple(c.window.contentView().subviews()[0].frame().size) == (sz.width, sz.height))
_src = img.size()
check("aspect ratio preserved within 1%",
      abs((sz.width/sz.height) - (_src.width/_src.height)) / (_src.width/_src.height) < 0.01,
      f"{sz.width/sz.height:.4f} vs {_src.width/_src.height:.4f}")
check("window centered horizontally",
      abs(w.frame().origin.x + sz.width/2 - (__import__('AppKit').NSScreen.mainScreen().visibleFrame().size.width/2
          + __import__('AppKit').NSScreen.mainScreen().visibleFrame().origin.x)) < 1)
check("image view has an image", c.window.contentView().subviews()[0].image() is not None,
      os.path.basename(c.last_image))

pump(0.6)
check("still visible at 0.6s", c.window is not None and c.window.isVisible())
elapsed = pump_until_dismissed()
check("auto-dismissed on its own", elapsed is not None)
check("dismissal lands near DISPLAY_SECONDS",
      elapsed is not None and abs((0.6 + elapsed) - mf.DISPLAY_SECONDS) < 0.35,
      f"{0.6 + elapsed:.2f}s vs {mf.DISPLAY_SECONDS}s" if elapsed else "never")

# --- rapid re-click: old window must not linger ---
c.showImage_(None); first_w = c.window
c.showImage_(None); second_w = c.window
check("re-click replaces window", first_w is not second_w and not first_w.isVisible())
check("only new window visible", second_w.isVisible())
check("dismissed once after rapid clicks", pump_until_dismissed() is not None)

# --- randomness ---
seen, repeats = set(), 0
prev = c.last_image
for _ in range(60):
    c.pickImage()
    if c.last_image == prev: repeats += 1
    prev = c.last_image
    seen.add(os.path.basename(c.last_image))
check("all images reachable", len(seen) == len(mf.find_images(c.collection)), ",".join(sorted(seen)))
check("never repeats back-to-back", repeats == 0, f"{repeats} repeats")

# --- collection selection ---
from AppKit import NSControlStateValueOn as _ON, NSControlStateValueOff as _OFF
import Foundation

def basenames_shown(n):
    out = set()
    for _ in range(n):
        c.showImage_(None)
        out.add(os.path.basename(c.last_image))
        c.dismissWindow()
    return out

jazz_item, reaction_item = c.collection_items["Jazz"], c.collection_items["Reaction"]
check("only Jazz checked at start", (jazz_item.state(), reaction_item.state()) == (_ON, _OFF))

jazz_files = {os.path.basename(p) for p in mf.find_images("Jazz")}
reaction_files = {os.path.basename(p) for p in mf.find_images("Reaction")}
check("collections hold different images", jazz_files.isdisjoint(reaction_files))

shown = basenames_shown(30)
check("Jazz selected -> only Jazz images", shown <= jazz_files and len(shown) == len(jazz_files),
      ",".join(sorted(shown)))

c.selectCollection_(reaction_item)
check("switching activates Reaction", c.collection == "Reaction")
check("checkmark moves, never both", (jazz_item.state(), reaction_item.state()) == (_OFF, _ON))
check("selection persisted",
      Foundation.NSUserDefaults.standardUserDefaults().stringForKey_(mf.COLLECTION_KEY) == "Reaction")
check("no-repeat memory cleared on switch", c.last_image is None)

shown = basenames_shown(60)
check("Reaction selected -> only Reaction images", shown <= reaction_files, f"{len(shown)} distinct")
check("no Jazz leakage", shown.isdisjoint(jazz_files))
check("all Reaction images reachable", shown == reaction_files, f"{len(shown)}/{len(reaction_files)}")

c.selectCollection_(jazz_item)
check("switching back to Jazz", c.collection == "Jazz"
      and (jazz_item.state(), reaction_item.state()) == (_ON, _OFF))
check("re-shows only Jazz images", basenames_shown(20) <= jazz_files)

prev_last = c.last_image
c.selectCollection_(jazz_item)
check("re-selecting the active one is a no-op", c.last_image == prev_last)

check("placeholder text names the collection", "Jazz" in c.makePlaceholder(300, 100).stringValue())

# --- random position toggle ---
from AppKit import NSScreen, NSControlStateValueOn, NSControlStateValueOff
vis = NSScreen.mainScreen().visibleFrame()

c.random_position = False
c.syncRandomItem()
check("unchecked when off", c.random_item.state() == NSControlStateValueOff)
c.showImage_(None)
centered = c.window.frame()
c.dismissWindow()
check("off -> centered",
      abs(centered.origin.x + centered.size.width/2 - (vis.origin.x + vis.size.width/2)) < 1
      and abs(centered.origin.y + centered.size.height/2 - (vis.origin.y + vis.size.height/2)) < 1)

c.toggleRandomPosition_(None)
check("toggle turns it on", c.random_position is True)
check("checkmark appears", c.random_item.state() == NSControlStateValueOn)
check("choice persisted to NSUserDefaults",
      __import__("Foundation").NSUserDefaults.standardUserDefaults().boolForKey_(mf.RANDOM_POSITION_KEY) is True)

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
check("never centered twice in the same spot", (round(centered.origin.x,1), round(centered.origin.y,1)) not in origins or len(origins) > 1)
check("always fully on screen (menu bar/Dock excluded)", on_screen)

xs = [p[0] for p in origins]; ys = [p[1] for p in origins]
check("spreads across width", max(xs) - min(xs) > vis.size.width * 0.3, f"x range {max(xs)-min(xs):.0f}pt")
check("spreads across height", max(ys) - min(ys) > vis.size.height * 0.3, f"y range {max(ys)-min(ys):.0f}pt")
check("respects edge margin",
      min(xs) >= vis.origin.x + mf.SCREEN_MARGIN - 0.5 and min(ys) >= vis.origin.y + mf.SCREEN_MARGIN - 0.5)

c.toggleRandomPosition_(None)
check("toggle turns it back off", c.random_position is False and c.random_item.state() == NSControlStateValueOff)
c.showImage_(None)
check("off again -> centered",
      abs(c.window.frame().origin.x - centered.origin.x) < 1)
c.dismissWindow()

# --- empty folder fallback ---
real = mf.IMAGE_DIR
mf.IMAGE_DIR = "/nonexistent"
c.showImage_(None)
sub = c.window.contentView().subviews()[0]
check("placeholder shown when a collection is empty", "No images in Jazz" in sub.stringValue())
check("placeholder auto-dismisses", pump_until_dismissed() is not None)
mf.IMAGE_DIR = real

restore_defaults()
print("\nrestored your saved settings: Random Position=%s, Collection=%s"
      % (_saved[0], _saved[1] or mf.COLLECTIONS[0]))
print(("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
