import os
import subprocess
from time import sleep
import idaapi
import ida_kernwin
import ida_idaapi
import ida_kernwin
from PyQt5 import QtWidgets, QtCore, QtGui

PLUGIN_NAME = "bIDApple"
ACTION_NAME = "bIDApple:toggle_animation"

class NavbandImagePainter(QtCore.QObject):
    def __init__(self, parent_widget, margin=4):
        """
        parent_widget: the navband QWidget (PyQt‐wrapped) to paint on.
        margin: pixels of padding from bottom/right edges.
        """
        super().__init__()
        self.nav_widget = parent_widget
        self.margin     = margin
        self.pixmap     = None
        self.painting   = False

        # Install our event filter on the navband
        self.nav_widget.installEventFilter(self)

    def set_pixmap(self, pixmap):
        """
        Replace the current QPixmap (frame) and trigger a repaint.
        Pass None to clear.
        """
        self.pixmap = pixmap
        if self.nav_widget:
            self.nav_widget.update()

    def eventFilter(self, obj, event):
        # Only intercept Paint events on our navband widget
        if obj is self.nav_widget and event.type() == QtCore.QEvent.Paint:
            # 1) Let IDA paint the navband normally (once)
            if not self.painting:
                self.painting = True
                try:
                    fake_pe = QtGui.QPaintEvent(self.nav_widget.rect())
                    QtWidgets.QApplication.instance().sendEvent(self.nav_widget, fake_pe)
                finally:
                    self.painting = False

            # 2) Overlay our pixmap (if defined) in bottom‐right corner
            if self.pixmap:
                painter = QtGui.QPainter(self.nav_widget)
                painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

                nav_w = obj.width()
                nav_h = obj.height()
                pm_w  = self.pixmap.width()
                pm_h  = self.pixmap.height()

                x = nav_w - pm_w - self.margin
                y = nav_h - pm_h - self.margin
                painter.drawPixmap(x, y, self.pixmap)
                painter.end()

            # 3) Swallow the Paint event so Qt doesn’t issue a second paint
            return True

        return super().eventFilter(obj, event)

    def uninstall(self):
        """
        Remove our event filter and clear any displayed pixmap.
        """
        if self.nav_widget:
            self.nav_widget.removeEventFilter(self)
            self.nav_widget.update()

class NavbandAnimator(QtCore.QObject):
    def __init__(self, folder_path, painter, fps=25):
        """
        folder_path: directory containing frames named 0001.jpeg, 0002.jpeg, …
        painter: NavbandImagePainter instance
        fps: frames per second (default 25)
        """
        super().__init__()
        self.folder  = folder_path
        self.painter = painter
        self.timer   = QtCore.QTimer(self)
        interval_ms = int(1000 / fps)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._next_frame)

        self.index   = 1    # next frame index
        self.running = False

    def start(self):
        """Start immediately at frame 0001.jpeg, then begin timer for subsequent frames."""
        self.running = True
        self.index = 1
        if not self._load_frame():
            # If first file doesn't exist, just stop
            self.running = False
            self.painter.uninstall()
            return
        self.timer.start()

    def stop(self):
        """Stop the timer and clear the final image from navband."""
        self.running = False
        self.timer.stop()
        self.painter.set_pixmap(None)

    def _next_frame(self):
        """Advance index, attempt to load next frame, or stop if missing."""
        if not self.running:
            return

        self.index += 1
        if not self._load_frame():
            # No such file -> end animation
            self.stop()
            self.painter.uninstall()

    def _load_frame(self):
        """
        Attempt to load "%04d.jpeg" from self.folder -> painter.
        Returns True if loaded, False if file not found or invalid image.

        In the video I use pngs but I don't want to put 132mb of pngs on git.
        If you really want pngs you can get the original video and cut it into pngs with :
        ffmpeg -i bad_apple.webm -vf fps=25 bad_apple/%04d.png
        """
        fname = f"{self.index:04d}.jpeg"
        fullpath = os.path.join(self.folder, fname)
        if not os.path.isfile(fullpath):
            return False

        img = QtGui.QImage(fullpath)
        if img.isNull():
            return False

        # Determine navband height dynamically
        nav_h = self.painter.nav_widget.height()
        if nav_h <= 0:
            nav_h = 20
        target_h = max(1, nav_h - 2 * self.painter.margin)
        target_w = int(img.width() * (target_h / img.height()))

        scaled = img.scaled(
            target_w, target_h,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        pix = QtGui.QPixmap.fromImage(scaled)
        self.painter.set_pixmap(pix)
        return True

class BIDAppleAction(ida_kernwin.action_handler_t):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin

    def activate(self, ctx):
        self.plugin.toggle_animation()
        return 1

    def update(self, ctx):
        return ida_kernwin.AST_ENABLE_FOR_WIDGET if ctx.widget_type in (ida_kernwin.BWN_DISASM, ida_kernwin.BWN_PSEUDOCODE) else ida_kernwin.AST_DISABLE_FOR_WIDGET

class MyHook(ida_kernwin.UI_Hooks):
    def __init__(self):
        super().__init__()
        self.hook()

    def finish_populating_widget_popup(self, widget, popup_handle):
        if ida_kernwin.get_widget_type(widget) in (ida_kernwin.BWN_DISASM, ida_kernwin.BWN_PSEUDOCODE):
            ida_kernwin.attach_action_to_popup(widget, popup_handle, ACTION_NAME, None)
        return 0

class BIDApplePlugin(ida_idaapi.plugin_t):
    flags         = ida_idaapi.PLUGIN_KEEP
    comment       = "bIDApple: Bad Apple on IDA navband"
    help          = "Right-click Disassembly or Pseudocode -> Start/Stop bIDApple Animation"
    wanted_name   = "bIDApple"
    wanted_hotkey = ""  # no default shortcut

    def __init__(self):
        super().__init__()
        self.hook       = None
        self.animator   = None
        self.painter    = None
        self.audio_proc  = None
        self.folder     = f"{idaapi.get_user_idadir()}/plugins/bIDApple"

    def init(self):
        """
        Called when IDA loads the plugin—register our action, then install the pop-up hook.
        """
        # 1) Register the toggle action
        desc = ida_kernwin.action_desc_t(
            ACTION_NAME,                             # unique action name
            "Start/Stop bIDApple Animation",        # menu text
            BIDAppleAction(self),                    # handler
            "",                                      # no single-key shortcut
            "Toggle bIDApple animation on navband", 
            -1                                       # no icon
        )
        if not ida_kernwin.register_action(desc):
            ida_kernwin.msg(f"[{PLUGIN_NAME}] failed to register action.\n")
            return ida_idaapi.PLUGIN_SKIP

        # 2) Install our ida_kernwin.UI_Hooks so that pop-up menus in DISASM/PSEUDOCODE get our entry
        self.hook = MyHook()
        return ida_idaapi.PLUGIN_KEEP

    def run(self, arg):
        pass

    def term(self):
        """
        Called when IDA unloads the plugin. Stop animation, uninstall hook, unregister action.
        """
        # 1) Clear navband (stop animation + teardown painter)
        self.clear_navband()

        # 2) Terminate any audio process
        if self.audio_proc:
            try:
                self.audio_proc.terminate()
            except Exception:
                pass
            self.audio_proc = None

        # 3) Unhook ida_kernwin.UI_Hooks
        if self.hook:
            self.hook.unhook()
            self.hook = None

        # 3) Unregister our action
        ida_kernwin.unregister_action(ACTION_NAME)

    def clear_navband(self):
        # 1) Stop any running animation
        if self.animator:
            self.animator.stop()
            self.animator = None

        # 2) Teardown the painter
        if self.painter:
            self.painter.uninstall()
            self.painter = None

    def toggle_animation(self):
        """
        Start or stop the navband animation. On first run, prompt for a folder.
        """
        # If already running, stop immediately
        if self.animator and self.animator.running:
            self.clear_navband()
            if self.audio_proc:
                try:
                    self.audio_proc.terminate()
                except Exception:
                    pass
                self.audio_proc = None
            return

        # Otherwise, prompt for a folder if not set
        if not os.path.exists(self.folder):
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                None,
                "Select Folder with Frames (e.g. 0001.jpeg, 0002.jpeg, ...)",
                os.getcwd()
            )
            if not folder:
                ida_kernwin.msg(f"[{PLUGIN_NAME}] no folder selected; abort.\n")
                return
            self.folder = folder

        # 1) Get (or open) the navband TWidget* and wrap to QWidget
        tw = ida_kernwin.open_navband_window(ida_kernwin.get_screen_ea(), 1)
        nav_qt = ida_kernwin.PluginForm.FormToPyQtWidget(tw)

        # 2) Create & install a NavbandImagePainter for this navband
        self.painter = NavbandImagePainter(nav_qt, margin=4)

        # 3) Create & start the animator
        self.animator = NavbandAnimator(self.folder, self.painter, fps=25)
        self.animator.start()
        self.play_song()
    def play_song(self):
        song_path = os.path.join(self.folder, "song.mp3")
        if os.path.isfile(song_path):
            # Attempt to launch with ffplay.
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", song_path]
            try:
                self.audio_proc = subprocess.Popen(cmd,
                                                   stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                ida_kernwin.msg(f"[{PLUGIN_NAME}] failed to launch player."
                               "We can't use QtMultimedia so ensure ffplay (for MP3) is installed.\n")
        else:
            ida_kernwin.msg(f"[{PLUGIN_NAME}] no song.mp3 in folder; skipping audio.\n")

def PLUGIN_ENTRY():
    return BIDApplePlugin()
