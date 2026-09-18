#!/usr/bin/env python3
"""Menu bar app: click the icon to flash a random image for one second."""

import os
import random
import sys

import objc
from AVFoundation import (
    AVLayerVideoGravityResizeAspect,
    AVMediaTypeVideo,
    AVPlayer,
    AVPlayerItemDidPlayToEndTimeNotification,
    AVPlayerLayer,
    AVURLAsset,
)
from CoreMedia import CMTimeGetSeconds
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSBitmapImageRep,
    NSBorderlessWindowMask,
    NSCenterTextAlignment,
    NSColor,
    NSControlStateValueOff,
    NSControlStateValueOn,
    NSEventMaskLeftMouseUp,
    NSEventMaskRightMouseUp,
    NSEventTypeRightMouseUp,
    NSFont,
    NSImage,
    NSImageCurrentFrame,
    NSImageCurrentFrameDuration,
    NSImageFrameCount,
    NSImageScaleProportionallyUpOrDown,
    NSImageView,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSScreen,
    NSStatusBar,
    NSTextField,
    NSTimer,
    NSVariableStatusItemLength,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
)
from Foundation import NSNotificationCenter, NSObject, NSURL, NSUserDefaults

# --- Configuration -----------------------------------------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(APP_DIR, "images")
DISPLAY_SECONDS = 1.0
MAX_EDGE = 500.0  # longest side of the popup window, in points
CORNER_RADIUS = 14.0
SCREEN_MARGIN = 5.0  # keep random placements this far from the screen edges
RANDOM_POSITION_KEY = "RandomPosition"  # NSUserDefaults key, so the toggle survives a restart
COLLECTION_KEY = "Collection"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".tiff", ".tif", ".bmp", ".heic", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
MUTE_VIDEO = False  # videos play with sound; set True to silence them
MAX_MEDIA_SECONDS = 30.0  # safety cap, so one long clip can't hold the screen
PLACEHOLDER_SIZE = (340.0, 120.0)
MIN_GIF_FRAME_DELAY = 0.1  # GIFs asking for ~0s per frame are shown at this rate


def find_collections():
    """Every subfolder of images/, in menu order. Each one is a collection."""
    if not os.path.isdir(IMAGE_DIR):
        return []
    return sorted(
        (
            name
            for name in os.listdir(IMAGE_DIR)
            if not name.startswith(".") and os.path.isdir(os.path.join(IMAGE_DIR, name))
        ),
        key=str.lower,
    )


def collection_dir(collection):
    """Folder holding one collection's images, e.g. images/Jazz."""
    return os.path.join(IMAGE_DIR, collection)


def find_media(collection):
    """Return sorted paths of every playable image or video in a collection."""
    folder = collection_dir(collection)
    if not os.path.isdir(folder):
        return []
    return sorted(
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if not name.startswith(".") and os.path.splitext(name)[1].lower() in MEDIA_EXTENSIONS
    )


def is_video(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def gif_loop_duration(image):
    """Seconds for one pass through an animated image, or None if it isn't animated.

    Frames asking for ~0s are clamped to MIN_GIF_FRAME_DELAY, matching how browsers
    and AppKit actually render them, so we never dismiss mid-loop.
    """
    for rep in image.representations():
        if not isinstance(rep, NSBitmapImageRep):
            continue
        frames = rep.valueForProperty_(NSImageFrameCount)
        if not frames or int(frames) < 2:
            continue
        total = 0.0
        for index in range(int(frames)):
            rep.setProperty_withValue_(NSImageCurrentFrame, index)
            delay = rep.valueForProperty_(NSImageCurrentFrameDuration)
            delay = float(delay) if delay else 0.0
            total += delay if delay >= 0.02 else MIN_GIF_FRAME_DELAY
        rep.setProperty_withValue_(NSImageCurrentFrame, 0)  # start playback at frame 1
        return total
    return None


def video_info(path):
    """(duration_seconds, (width, height)) for a video, or None if unreadable."""
    asset = AVURLAsset.URLAssetWithURL_options_(NSURL.fileURLWithPath_(path), None)
    tracks = asset.tracksWithMediaType_(AVMediaTypeVideo)
    if not tracks:
        return None
    duration = CMTimeGetSeconds(asset.duration())
    if duration != duration or duration <= 0:  # NaN or empty
        return None
    size = tracks[0].naturalSize()
    t = tracks[0].preferredTransform()
    # Respect rotation metadata, so portrait clips from a phone aren't sized sideways.
    width = abs(size.width * t.a + size.height * t.c)
    height = abs(size.width * t.b + size.height * t.d)
    if width <= 0 or height <= 0:
        width, height = size.width, size.height
    return duration, (width, height)


class RoundedView(NSView):
    """Clear-backed container that clips its content to a rounded rect."""

    def drawRect_(self, rect):
        NSColor.windowBackgroundColor().setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), CORNER_RADIUS, CORNER_RADIUS
        ).fill()


class FlashController(NSObject):
    def init(self):
        self = objc.super(FlashController, self).init()
        if self is None:
            return None
        self.window = None
        self.timer = None
        self.player = None
        self.last_image = None
        defaults = NSUserDefaults.standardUserDefaults()
        self.random_position = defaults.boolForKey_(RANDOM_POSITION_KEY)
        self.collection = defaults.stringForKey_(COLLECTION_KEY)
        self.collection_items = {}
        self.refreshCollections()  # validates the saved name against the folders on disk
        return self

    # --- menu bar setup ---

    @objc.python_method
    def setUpStatusItem(self):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        button = self.status_item.button()
        icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "photo.on.rectangle", "Show a random image"
        )
        if icon is not None:
            icon.setTemplate_(True)
            button.setImage_(icon)
        else:  # older macOS without SF Symbols
            button.setTitle_("Pic")
        button.setTarget_(self)
        button.setAction_("statusItemClicked:")
        button.sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)
        button.setToolTip_("Click for a random image \u2014 right-click for options")

        self.menu = NSMenu.alloc().init()
        self.menu.setAutoenablesItems_(False)  # we manage the header's disabled look
        self.menu.setDelegate_(self)  # menuWillOpen_ re-reads images/ before each open
        self.rebuildMenu()

    # --- menu construction ---

    @objc.python_method
    def rebuildMenu(self):
        """Build the menu from whatever subfolders images/ has right now."""
        self.menu.removeAllItems()

        show = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Random Image", "showImage:", ""
        )
        show.setTarget_(self)
        show.setEnabled_(self.collection is not None)
        self.menu.addItem_(show)
        self.menu.addItem_(NSMenuItem.separatorItem())

        header = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Collection", None, "")
        header.setEnabled_(False)
        self.menu.addItem_(header)

        self.collection_items = {}
        collections = find_collections()
        if not collections:
            empty = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No folders in images/", None, ""
            )
            empty.setEnabled_(False)
            empty.setToolTip_("Create a folder inside images/ and put pictures in it")
            self.menu.addItem_(empty)
        else:
            for name in collections:
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    name, "selectCollection:", ""
                )
                item.setTarget_(self)
                count = len(find_media(name))
                item.setToolTip_(
                    "%d file%s in images/%s" % (count, "" if count == 1 else "s", name)
                )
                self.menu.addItem_(item)
                self.collection_items[name] = item
        self.syncCollectionItems()

        self.menu.addItem_(NSMenuItem.separatorItem())

        self.random_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Random Position", "toggleRandomPosition:", ""
        )
        self.random_item.setTarget_(self)
        self.random_item.setToolTip_(
            "Show each image somewhere random instead of centered"
        )
        self.syncRandomItem()
        self.menu.addItem_(self.random_item)

        self.menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quit:", "q"
        )
        quit_item.setTarget_(self)
        self.menu.addItem_(quit_item)

    def menuWillOpen_(self, menu):
        """NSMenuDelegate: pick up folders added or removed since the last open."""
        self.refreshCollections()
        self.rebuildMenu()

    @objc.python_method
    def refreshCollections(self):
        """Keep self.collection pointing at a folder that actually exists."""
        collections = find_collections()
        if self.collection in collections:
            return
        self.collection = collections[0] if collections else None
        self.last_image = None
        if self.collection is not None:
            NSUserDefaults.standardUserDefaults().setObject_forKey_(
                self.collection, COLLECTION_KEY
            )

    # --- click handling ---

    def statusItemClicked_(self, sender):
        event = NSApp().currentEvent()
        right_click = event is not None and (
            event.type() == NSEventTypeRightMouseUp or (event.modifierFlags() & (1 << 18))
        )
        if right_click:
            self.showMenu()
        else:
            self.showImage_(None)

    @objc.python_method
    def showMenu(self):
        """Pop the options menu open, then detach it so left-clicks stay actions."""
        self.status_item.setMenu_(self.menu)
        self.status_item.button().performClick_(None)
        self.status_item.setMenu_(None)

    def selectCollection_(self, sender):
        name = sender.title()
        if name == self.collection:
            return  # already active; nothing to change
        self.collection = name
        self.last_image = None  # don't carry the no-repeat memory across collections
        self.syncCollectionItems()
        NSUserDefaults.standardUserDefaults().setObject_forKey_(name, COLLECTION_KEY)

    @objc.python_method
    def syncCollectionItems(self):
        """Check exactly the active collection, so the list reads as a radio group."""
        for name, item in self.collection_items.items():
            item.setState_(
                NSControlStateValueOn if name == self.collection else NSControlStateValueOff
            )
        self.status_item.button().setToolTip_(
            "Click for a random %s image \u2014 right-click for options" % self.collection
            if self.collection
            else "Add a folder of images to images/ \u2014 right-click for options"
        )

    def toggleRandomPosition_(self, sender):
        self.random_position = not self.random_position
        self.syncRandomItem()
        NSUserDefaults.standardUserDefaults().setBool_forKey_(
            self.random_position, RANDOM_POSITION_KEY
        )

    @objc.python_method
    def syncRandomItem(self):
        self.random_item.setState_(
            NSControlStateValueOn if self.random_position else NSControlStateValueOff
        )

    def quit_(self, sender):
        self.dismissWindow()
        NSApp().terminate_(None)

    def showImage_(self, sender):
        self.dismissWindow()  # a second click restarts the flash cleanly

        path = self.pickMedia()
        self.window, duration = self.makeWindow(path)
        self.window.orderFrontRegardless()  # show without stealing keyboard focus

        # A video also dismisses itself on AVPlayerItemDidPlayToEndTimeNotification;
        # this timer is the backstop if that notification never arrives.
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            duration, self, "timerFired:", None, False
        )

    @objc.python_method
    def pickMedia(self):
        """Random image or video from the active collection, never repeating twice."""
        self.refreshCollections()  # a folder may have appeared or vanished since last time
        if self.collection is None:
            return None
        media = find_media(self.collection)
        if not media:
            return None
        candidates = [p for p in media if p != self.last_image] or media
        self.last_image = random.choice(candidates)
        return self.last_image

    # --- window lifecycle ---

    @objc.python_method
    def makeWindow(self, path):
        """Build the popup for one file. Returns (window, seconds to keep it up)."""
        image = None
        duration = DISPLAY_SECONDS
        video = None

        if path is None:
            source = PLACEHOLDER_SIZE
        elif is_video(path):
            video = video_info(path)
            if video is None:  # unreadable or not really a video
                source = PLACEHOLDER_SIZE
            else:
                duration, source = min(video[0], MAX_MEDIA_SECONDS), video[1]
        else:
            image = NSImage.alloc().initWithContentsOfFile_(path)
            if image is None:
                source = PLACEHOLDER_SIZE
            else:
                source = tuple(image.size())
                loop = gif_loop_duration(image)
                if loop:
                    duration = min(loop, MAX_MEDIA_SECONDS)

        width, height = self.contentSize(source)
        x, y = self.windowOrigin(width, height)
        frame = NSMakeRect(x, y, width, height)

        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, NSBorderlessWindowMask, NSBackingStoreBuffered, False
        )
        window.setOpaque_(False)
        window.setBackgroundColor_(NSColor.clearColor())
        window.setLevel_(25)  # floats above normal windows
        window.setIgnoresMouseEvents_(True)
        window.setHasShadow_(True)
        window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
        )

        # AppKit may nudge the frame to land on the display's backing grid, so take
        # the sizes it actually gave us rather than the ones we asked for.
        bounds = window.contentRectForFrameRect_(window.frame())
        width, height = bounds.size.width, bounds.size.height

        container = RoundedView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        container.setWantsLayer_(True)
        container.layer().setCornerRadius_(CORNER_RADIUS)
        container.layer().setMasksToBounds_(True)
        window.setContentView_(container)

        if video is not None:
            self.attachPlayer(container, path, width, height)
        elif image is not None:
            view = NSImageView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
            view.setImage_(image)
            view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
            view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
            view.setAnimates_(True)  # animated GIFs play; static images ignore this
            container.addSubview_(view)
        else:
            container.addSubview_(self.makePlaceholder(width, height))

        return window, duration

    @objc.python_method
    def attachPlayer(self, container, path, width, height):
        """Start a video playing inside the popup, dismissing when it ends."""
        self.player = AVPlayer.playerWithURL_(NSURL.fileURLWithPath_(path))
        self.player.setMuted_(MUTE_VIDEO)

        layer = AVPlayerLayer.playerLayerWithPlayer_(self.player)
        layer.setFrame_(NSMakeRect(0, 0, width, height))
        layer.setVideoGravity_(AVLayerVideoGravityResizeAspect)
        layer.setCornerRadius_(CORNER_RADIUS)
        layer.setMasksToBounds_(True)
        container.layer().addSublayer_(layer)

        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "videoEnded:", AVPlayerItemDidPlayToEndTimeNotification,
            self.player.currentItem(),
        )
        self.player.play()

    def videoEnded_(self, notification):
        self.dismissWindow()

    @objc.python_method
    def windowOrigin(self, width, height):
        """Bottom-left corner for the popup: random when enabled, else centered.

        Random placements stay inside visibleFrame (which excludes the menu bar and
        Dock) and keep a margin from the edges, so the image is never clipped.
        """
        screen = NSScreen.mainScreen().visibleFrame()
        if not self.random_position:
            # Whole points only: a fractional origin makes AppKit round the whole
            # frame to the backing grid, which stretches the window by a point.
            return (
                round(screen.origin.x + (screen.size.width - width) / 2.0),
                round(screen.origin.y + (screen.size.height - height) / 2.0),
            )

        def span(origin, available, size):
            # Shrink the margin if the window is too big for the screen to spare it.
            margin = min(SCREEN_MARGIN, max(0.0, (available - size) / 2.0))
            low = origin + margin
            high = origin + available - size - margin
            if high <= low:
                return round(low)
            return round(random.uniform(low, high))

        return (
            span(screen.origin.x, screen.size.width, width),
            span(screen.origin.y, screen.size.height, height),
        )

    @objc.python_method
    def contentSize(self, source_size):
        """Fit a (width, height) into the popup's box, preserving aspect ratio."""
        width, height = source_size
        if width <= 0 or height <= 0:
            return PLACEHOLDER_SIZE
        scale = min(MAX_EDGE / width, MAX_EDGE / height)

        def snap(value):
            # Round to an even number of points and never exceed the cap, so the
            # window keeps the size we asked for on Retina displays.
            return max(2.0, min(MAX_EDGE, 2.0 * round(value * scale / 2.0)))

        return snap(width), snap(height)

    @objc.python_method
    def makePlaceholder(self, width, height):
        label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, height / 2 - 30, width - 40, 60)
        )
        label.setStringValue_(
            "Nothing in %s.\nAdd images or videos to images/%s/."
            % (self.collection, self.collection)
            if self.collection
            else "No folders yet.\nCreate one inside images/ and add some files."
        )
        label.setAlignment_(NSCenterTextAlignment)
        label.setFont_(NSFont.systemFontOfSize_(13))
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        return label

    def timerFired_(self, timer):
        self.dismissWindow()

    @objc.python_method
    def dismissWindow(self):
        if self.player is not None:
            NSNotificationCenter.defaultCenter().removeObserver_name_object_(
                self, AVPlayerItemDidPlayToEndTimeNotification, None
            )
            self.player.pause()
            self.player = None
        if self.timer is not None:
            self.timer.invalidate()
            self.timer = None
        if self.window is not None:
            self.window.orderOut_(None)
            self.window = None


_controller = None


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # menu bar only, no Dock icon

    global _controller
    _controller = FlashController.alloc().init()  # module-level: keeps it alive for the app's lifetime
    _controller.setUpStatusItem()

    collections = find_collections()
    if not collections:
        print(f"Warning: no subfolders in {IMAGE_DIR} — create one per collection",
              file=sys.stderr)
    for name in collections:
        if not find_media(name):
            print(f"Warning: no media found in {collection_dir(name)}", file=sys.stderr)

    app.run()


if __name__ == "__main__":
    main()
