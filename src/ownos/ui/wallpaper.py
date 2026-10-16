"""Wallpaper drawn inside Husk Desktop; no separate process or background service."""
from ownos.wallpaper import image_placement, wallpaper_candidates
from ownos.ui.common import Gtk, Gdk, GdkPixbuf, GLib


class Wallpaper(Gtk.DrawingArea):
    def __init__(self, path='', mode='cover'):
        super().__init__()
        self.mode = mode
        self.pixbuf = None
        self.source_path = None
        for candidate in wallpaper_candidates(path):
            try:
                self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(candidate))
                self.source_path = candidate
                break
            except GLib.Error:
                continue
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect('draw', self.draw_wallpaper)

    def draw_wallpaper(self, widget, context):
        # Redrawn at the allocated logical size, including after resolution or
        # scale changes. Cairo applies the monitor's device scale separately.
        context.set_source_rgb(0, 0, 0)
        context.paint()
        width, height = self.get_allocated_width(), self.get_allocated_height()
        if self.pixbuf is None or min(width, height) <= 0:
            return False
        scale, x, y = image_placement(self.pixbuf.get_width(), self.pixbuf.get_height(),
                                    width, height, self.mode)
        context.save()
        context.rectangle(0, 0, width, height)
        context.clip()
        context.translate(x, y)
        context.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(context, self.pixbuf, 0, 0)
        context.paint()
        context.restore()
        return False
