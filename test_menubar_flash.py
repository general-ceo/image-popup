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


def scheduled_seconds():
    """How long the popup is set to stay up.

    NSTimer.timeInterval() reports 0 for non-repeating timers, so read the fire date.
    """
    return c.timer.fireDate().timeIntervalSinceNow()


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


def write_gif(path, frames=6, delay=0.3, w=100, h=80):
    """Animated GIF whose one loop lasts frames*delay seconds."""
    from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage,
                        CGColorSpaceCreateDeviceRGB, CGContextFillRect, CGContextSetRGBFillColor,
                        CGImageDestinationAddImage, CGImageDestinationCreateWithURL,
                        CGImageDestinationFinalize, CGImageDestinationSetProperties,
                        CGRectMake, kCGImageAlphaPremultipliedLast)
    from Foundation import NSURL as _NSURL
    dest = CGImageDestinationCreateWithURL(
        _NSURL.fileURLWithPath_(path), "com.compuserve.gif", frames, None)
    CGImageDestinationSetProperties(dest, {"{GIF}": {"LoopCount": 0}})
    for i in range(frames):
        ctx = CGBitmapContextCreate(None, w, h, 8, 0, CGColorSpaceCreateDeviceRGB(),
                                    kCGImageAlphaPremultipliedLast)
        CGContextSetRGBFillColor(ctx, i / max(frames - 1, 1), 0.4, 0.8, 1.0)
        CGContextFillRect(ctx, CGRectMake(0, 0, w, h))
        CGImageDestinationAddImage(dest, CGBitmapContextCreateImage(ctx),
                                   {"{GIF}": {"DelayTime": delay}})
    CGImageDestinationFinalize(dest)


def write_mp4(path, seconds=1.5, w=96, h=64, fps=10):
    """Short silent H.264 clip."""
    from AVFoundation import (AVAssetWriter, AVAssetWriterInput,
                              AVAssetWriterInputPixelBufferAdaptor, AVFileTypeMPEG4,
                              AVMediaTypeVideo, AVVideoCodecKey, AVVideoCodecTypeH264,
                              AVVideoHeightKey, AVVideoWidthKey)
    from CoreMedia import CMTimeMake
    from Quartz import (CVPixelBufferCreate, CVPixelBufferGetBaseAddress,
                        CVPixelBufferGetBytesPerRow, CVPixelBufferLockBaseAddress,
                        CVPixelBufferUnlockBaseAddress, kCVPixelFormatType_32ARGB)
    from Foundation import NSURL as _NSURL

    writer = AVAssetWriter.alloc().initWithURL_fileType_error_(
        _NSURL.fileURLWithPath_(path), AVFileTypeMPEG4, None)
    if isinstance(writer, tuple):
        writer = writer[0]
    inp = AVAssetWriterInput.assetWriterInputWithMediaType_outputSettings_(
        AVMediaTypeVideo,
        {AVVideoCodecKey: AVVideoCodecTypeH264, AVVideoWidthKey: w, AVVideoHeightKey: h})
    inp.setExpectsMediaDataInRealTime_(False)
    adaptor = AVAssetWriterInputPixelBufferAdaptor.assetWriterInputPixelBufferAdaptorWithAssetWriterInput_sourcePixelBufferAttributes_(
        inp, None)
    writer.addInput_(inp)
    writer.startWriting()
    writer.startSessionAtSourceTime_(CMTimeMake(0, fps))
    for i in range(int(seconds * fps)):
        res = CVPixelBufferCreate(None, w, h, kCVPixelFormatType_32ARGB, None, None)
        pb = res[1] if isinstance(res, tuple) else res
        CVPixelBufferLockBaseAddress(pb, 0)
        nbytes = CVPixelBufferGetBytesPerRow(pb) * h
        CVPixelBufferGetBaseAddress(pb).as_buffer(nbytes)[:] = (
            bytes((255, 40, (i * 9) % 256, 180)) * (nbytes // 4))
        CVPixelBufferUnlockBaseAddress(pb, 0)
        while not inp.isReadyForMoreMediaData():
            time.sleep(0.01)
        adaptor.appendPixelBuffer_withPresentationTime_(pb, CMTimeMake(i, fps))
    inp.markAsFinished()
    done = []
    writer.finishWritingWithCompletionHandler_(lambda: done.append(True))
    start = time.time()
    while not done and time.time() - start < 20:
        pump(0.05)


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
_saved_audio = _defaults.objectForKey_(mf.INCLUDE_AUDIO_KEY)


def restore_defaults():
    _defaults.setBool_forKey_(_saved[0], mf.RANDOM_POSITION_KEY)
    if _saved[1] is not None:
        _defaults.setObject_forKey_(_saved[1], mf.COLLECTION_KEY)
    if _saved_audio is None:
        _defaults.removeObjectForKey_(mf.INCLUDE_AUDIO_KEY)
    else:
        _defaults.setObject_forKey_(_saved_audio, mf.INCLUDE_AUDIO_KEY)
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
                   "Random Position", "Include Video Audio", "", "Quit"], str(titles()))
check("Collection header is a disabled label", not c.menu.itemAtIndex_(2).isEnabled())
check("item tooltip reports the file count",
      c.collection_items["Jazz"].toolTip() == "4 files in images/Jazz",
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
      (sz.width, sz.height) == tuple(c.contentSize(tuple(img.size()))),
      f"{sz.width}x{sz.height} vs {c.contentSize(tuple(img.size()))}")
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
    c.pickMedia()
    if c.last_image == prev:
        repeats += 1
    prev = c.last_image
    seen.add(os.path.basename(c.last_image))
check("all images in the collection reachable",
      len(seen) == len(mf.find_media("Jazz")), f"{len(seen)}/{len(mf.find_media('Jazz'))}")
check("never repeats back-to-back", repeats == 0, f"{repeats} repeats")

# --- collection selection -----------------------------------------------------

jazz, reaction = c.collection_items["Jazz"], c.collection_items["Reaction"]
jazz_files = {os.path.basename(p) for p in mf.find_media("Jazz")}
reaction_files = {os.path.basename(p) for p in mf.find_media("Reaction")}
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
      == {os.path.basename(p) for p in mf.find_media("Cats")})

shutil.rmtree(os.path.join(mf.IMAGE_DIR, "Cats"))
c.menuWillOpen_(c.menu)
check("deleted folder leaves the menu", "Cats" not in c.collection_items)
check("deleting the active folder falls back to the first",
      c.collection == "aardvark", str(c.collection))
check("fallback is persisted", _defaults.stringForKey_(mf.COLLECTION_KEY) == "aardvark")
c.showImage_(None)
check("still works after the fallback",
      os.path.basename(c.last_image) in {os.path.basename(p) for p in mf.find_media("aardvark")})
c.dismissWindow()

# --- empty states -------------------------------------------------------------

os.makedirs(os.path.join(mf.IMAGE_DIR, "Empty"))
c.menuWillOpen_(c.menu)
c.selectCollection_(c.collection_items["Empty"])
check("empty folder is still selectable", c.collection == "Empty")
c.showImage_(None)
check("empty collection shows a named placeholder",
      "Nothing in Empty" in c.window.contentView().subviews()[0].stringValue())
check("placeholder auto-dismisses", pump_until_dismissed() is not None)
check("empty folder tooltip says 0 files",
      c.collection_items["Empty"].toolTip() == "0 files in images/Empty")

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
      "No folders yet" in c.window.contentView().subviews()[0].stringValue())
check("guidance placeholder dismisses", pump_until_dismissed() is not None)

make_collection("Later", 2)
c.menuWillOpen_(c.menu)
check("recovers when a folder is created", c.collection == "Later")
check("Show Random Image re-enabled", c.menu.itemAtIndex_(0).isEnabled())
c.showImage_(None)
check("shows images again", c.window.contentView().subviews()[0].image() is not None)
c.dismissWindow()

# --- animated GIFs and videos -------------------------------------------------

GIF_LOOP, VIDEO_SECS = 1.8, 1.5  # both differ from DISPLAY_SECONDS on purpose
os.makedirs(os.path.join(mf.IMAGE_DIR, "Gif"))
write_gif(os.path.join(mf.IMAGE_DIR, "Gif", "spin.gif"), frames=6, delay=0.3)
os.makedirs(os.path.join(mf.IMAGE_DIR, "Video"))
write_mp4(os.path.join(mf.IMAGE_DIR, "Video", "clip.mp4"), seconds=VIDEO_SECS)
os.makedirs(os.path.join(mf.IMAGE_DIR, "Broken"))
with open(os.path.join(mf.IMAGE_DIR, "Broken", "not-really.mp4"), "w") as fh:
    fh.write("this is not a video")
os.makedirs(os.path.join(mf.IMAGE_DIR, "Still"))
write_png(os.path.join(mf.IMAGE_DIR, "Still", "flat.png"))
c.menuWillOpen_(c.menu)

gif_path = os.path.join(mf.IMAGE_DIR, "Gif", "spin.gif")
mp4_path = os.path.join(mf.IMAGE_DIR, "Video", "clip.mp4")
check("videos are collected alongside images", mf.find_media("Video") == [mp4_path])
check("is_video recognizes mp4/mov/m4v",
      all(mf.is_video("x" + e) for e in (".mp4", ".MP4", ".mov", ".m4v"))
      and not mf.is_video("x.png"))
check("GIF loop duration read from the file",
      abs(mf.gif_loop_duration(__import__("AppKit").NSImage.alloc().initWithContentsOfFile_(gif_path))
          - GIF_LOOP) < 0.05)
check("static images report no loop duration",
      mf.gif_loop_duration(__import__("AppKit").NSImage.alloc().initWithContentsOfFile_(
          os.path.join(mf.IMAGE_DIR, "Still", "flat.png"))) is None)
_dur, _size = mf.video_info(mp4_path)
check("video duration read from the file", abs(_dur - VIDEO_SECS) < 0.1, f"{_dur:.2f}s")
check("video natural size read from the file", tuple(_size) == (96.0, 64.0), str(tuple(_size)))
check("unreadable video reports no info", mf.video_info(
    os.path.join(mf.IMAGE_DIR, "Broken", "not-really.mp4")) is None)

c.selectCollection_(c.collection_items["Still"])
c.showImage_(None)
check("static image uses DISPLAY_SECONDS",
      abs(scheduled_seconds() - mf.DISPLAY_SECONDS) < 0.05, f"{scheduled_seconds():.2f}s")
check("static image has no player", c.player is None)
c.dismissWindow()

c.selectCollection_(c.collection_items["Gif"])
c.showImage_(None)
check("GIF stays up for exactly one loop",
      abs(scheduled_seconds() - GIF_LOOP) < 0.1, f"{scheduled_seconds():.2f}s")
_iv = c.window.contentView().subviews()[0]
check("GIF is animating", _iv.animates())
check("GIF window sized from the GIF", tuple(c.window.frame().size) == tuple(c.contentSize((100, 80))))
_gif_elapsed = pump_until_dismissed(timeout=5.0)
check("GIF dismisses after its loop, not after DISPLAY_SECONDS",
      _gif_elapsed is not None and abs(_gif_elapsed - GIF_LOOP) < 0.35,
      f"{_gif_elapsed:.2f}s vs loop {GIF_LOOP}s")

c.selectCollection_(c.collection_items["Video"])
c.showImage_(None)
check("video creates a player", c.player is not None)
check("video is playing", c.player.rate() > 0)
check("player layer attached to the popup",
      any(l.__class__.__name__.endswith("AVPlayerLayer")
          for l in (c.window.contentView().layer().sublayers() or [])))
check("video window sized from the video",
      tuple(c.window.frame().size) == tuple(c.contentSize((96, 64))), str(tuple(c.window.frame().size)))
check("backstop timer covers the clip length",
      abs(scheduled_seconds() - VIDEO_SECS) < 0.2, f"{scheduled_seconds():.2f}s")
check("audio follows the toggle", c.player.isMuted() is not c.include_audio)
_video_elapsed = pump_until_dismissed(timeout=6.0)
check("video dismisses when it ends",
      _video_elapsed is not None and abs(_video_elapsed - VIDEO_SECS) < 0.4,
      f"{_video_elapsed:.2f}s vs clip {VIDEO_SECS}s")
check("player released on dismiss", c.player is None)

c.showImage_(None)
_playing = c.player
c.showImage_(None)
check("re-click stops the previous video", _playing.rate() == 0 and c.player is not _playing)
c.dismissWindow()
check("player cleaned up after manual dismiss", c.player is None)

c.selectCollection_(c.collection_items["Broken"])
c.showImage_(None)
check("corrupt video falls back to the placeholder",
      c.window.contentView().subviews()[0].__class__.__name__.endswith("NSTextField"))
check("corrupt video does not start a player", c.player is None)
check("corrupt video still dismisses", pump_until_dismissed() is not None)

# --- include video audio toggle ---

_defaults.removeObjectForKey_(mf.INCLUDE_AUDIO_KEY)
_fresh = mf.FlashController.alloc().init()
check("defaults to INCLUDE_AUDIO_DEFAULT on first run",
      _fresh.include_audio == mf.INCLUDE_AUDIO_DEFAULT)
_defaults.setBool_forKey_(False, mf.INCLUDE_AUDIO_KEY)
check("an explicit off is remembered, not mistaken for unset",
      mf.FlashController.alloc().init().include_audio is False)
_defaults.setBool_forKey_(True, mf.INCLUDE_AUDIO_KEY)
c.include_audio = True
c.syncAudioItem()

c.selectCollection_(c.collection_items["Video"])
check("checked when audio is on", c.audio_item.state() == NSControlStateValueOn)
c.showImage_(None)
check("audio on -> player unmuted", c.player.isMuted() is False)
c.dismissWindow()

c.toggleIncludeAudio_(None)
check("toggle turns audio off", c.include_audio is False)
check("checkmark clears", c.audio_item.state() == NSControlStateValueOff)
check("choice persisted", _defaults.boolForKey_(mf.INCLUDE_AUDIO_KEY) is False)
c.showImage_(None)
check("audio off -> player muted", c.player.isMuted() is True)

c.toggleIncludeAudio_(None)
check("toggling mid-playback unmutes the running clip", c.player.isMuted() is False)
c.toggleIncludeAudio_(None)
check("toggling mid-playback mutes the running clip", c.player.isMuted() is True)
check("mid-playback toggle does not disturb the clip", c.player.rate() > 0)
check("clip still ends on its own", pump_until_dismissed(timeout=6.0) is not None)

check("toggle survives a menu rebuild",
      (c.menuWillOpen_(c.menu), c.audio_item.state())[1] == NSControlStateValueOff)
c.toggleIncludeAudio_(None)
check("restored to on", c.include_audio is True and c.audio_item.state() == NSControlStateValueOn)
check("audio setting is independent of Random Position",
      (c.toggleRandomPosition_(None), c.include_audio)[1] is True)
c.toggleRandomPosition_(None)

os.makedirs(os.path.join(mf.IMAGE_DIR, "Long"))
write_gif(os.path.join(mf.IMAGE_DIR, "Long", "long.gif"), frames=60, delay=0.6)  # 36s
c.menuWillOpen_(c.menu)
c.selectCollection_(c.collection_items["Long"])
c.showImage_(None)
check("over-long media is capped at MAX_MEDIA_SECONDS",
      abs(scheduled_seconds() - mf.MAX_MEDIA_SECONDS) < 0.1, f"{scheduled_seconds():.1f}s")
c.dismissWindow()

for _name in ("Gif", "Video", "Broken", "Still", "Long"):
    shutil.rmtree(os.path.join(mf.IMAGE_DIR, _name))
c.menuWillOpen_(c.menu)

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
