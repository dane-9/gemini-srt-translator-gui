import platform
from enum import Enum
from ctypes import cast, POINTER, Structure, c_int, byref, windll, c_bool, sizeof
from ctypes.wintypes import LPRECT, MSG, HWND, RECT, UINT, DWORD, LPARAM, BOOL

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QIcon, QCursor, QGuiApplication

IS_WINDOWS = platform.system() == 'Windows'

class TitleBar(QWidget):
    def __init__(self, parent=None, hint=None):
        super().__init__(parent)
        self._hint = hint or ['min', 'max', 'close']
        self._setupLayout()

    def _setupLayout(self):
        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setLayout(self._layout)

    def setTitleBarFont(self, font: QFont):
        self.setFont(font)

    def setIconSize(self, width: int, height: int):
        pass

    def layout(self):
        return self._layout

if IS_WINDOWS:
    try:
        from winreg import ConnectRegistry, HKEY_CURRENT_USER, OpenKey, KEY_READ, QueryValueEx
        import win32con, win32gui, win32api
        from PyQt5.QtWinExtras import QtWin
        from win32comext.shell import shellcon
        WINDOWS_AVAILABLE = True
    except ImportError:
        try:
            from winreg import ConnectRegistry, HKEY_CURRENT_USER, OpenKey, KEY_READ, QueryValueEx
            import win32con, win32gui, win32api
            class QtWin:
                @staticmethod
                def isCompositionEnabled(): return True
            class _ShellCon:
                ABS_AUTOHIDE = 1; ABM_GETSTATE = 4; ABM_GETTASKBARPOS = 5
            shellcon = _ShellCon()
            WINDOWS_AVAILABLE = True
        except ImportError:
            WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False

if IS_WINDOWS and WINDOWS_AVAILABLE:
    class MARGINS(Structure):
        _fields_ = [("l", c_int), ("r", c_int), ("t", c_int), ("b", c_int)]

    class PWINDOWPOS(Structure):
        _fields_ = [('h', HWND), ('i', HWND), ('x', c_int), ('y', c_int), ('cx', c_int), ('cy', c_int), ('f', UINT)]

    class NCCALCSIZE_PARAMS(Structure):
        _fields_ = [('rgrc', RECT * 3), ('lppos', POINTER(PWINDOWPOS))]

    class DWMWINDOWATTRIBUTE(Enum):
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20

    LPNCCALCSIZE_PARAMS = POINTER(NCCALCSIZE_PARAMS)

    class WindowsEffectHelper:
        def __init__(self):
            self.dwmapi = windll.LoadLibrary("dwmapi")

        def setBasicEffect(self, hWnd, hint):
            margins = MARGINS(-1, -1, -1, -1)
            self.dwmapi.DwmExtendFrameIntoClientArea(int(hWnd), byref(margins))
            dwNewLong = win32con.WS_CAPTION
            if 'min' in hint:
                dwNewLong |= win32con.WS_MINIMIZEBOX
            if 'max' in hint:
                dwNewLong |= win32con.CS_DBLCLKS | win32con.WS_THICKFRAME | win32con.WS_MAXIMIZEBOX
            win32gui.SetWindowLong(hWnd, win32con.GWL_STYLE, dwNewLong)

        def setDarkTheme(self, id, f: bool):
            self.dwmapi.DwmSetWindowAttribute(int(id), DWMWINDOWATTRIBUTE.DWMWA_USE_IMMERSIVE_DARK_MODE.value, byref(c_bool(f)), sizeof(BOOL))

    class _Win32Utils:
        class APPBARDATA(Structure):
            _fields_ = [('s', DWORD), ('h', HWND), ('c', UINT), ('e', UINT), ('r', RECT), ('l', LPARAM)]

        class Taskbar:
            LEFT, TOP, RIGHT, BOTTOM, NO_POSITION = 0, 1, 2, 3, 4
            AUTO_HIDE_THICKNESS = 2

            @staticmethod
            def isAutoHide():
                d = _Win32Utils.APPBARDATA(sizeof(_Win32Utils.APPBARDATA))
                return windll.shell32.SHAppBarMessage(shellcon.ABM_GETSTATE, byref(d)) == shellcon.ABS_AUTOHIDE

            @classmethod
            def getPosition(cls, hWnd):
                mi = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hWnd, win32con.MONITOR_DEFAULTTONEAREST))
                if not mi: return cls.NO_POSITION
                d = _Win32Utils.APPBARDATA(sizeof(_Win32Utils.APPBARDATA), 0, 0, 0, RECT(*mi['Monitor']), 0)
                for p in [cls.LEFT, cls.TOP, cls.RIGHT, cls.BOTTOM]:
                    d.e = p
                    if windll.shell32.SHAppBarMessage(11, byref(d)): return p
                return cls.NO_POSITION

        @staticmethod
        def isMaximized(hWnd):
            return win32gui.GetWindowPlacement(hWnd)[1] == win32con.SW_MAXIMIZE

        @staticmethod
        def isFullScreen(hWnd):
            if not hWnd: return False
            wr = win32gui.GetWindowRect(hWnd)
            mi = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hWnd, win32con.MONITOR_DEFAULTTOPRIMARY))
            return mi and all(i == j for i, j in zip(wr, mi["Monitor"]))

        @staticmethod
        def getResizeBorderThickness(hWnd):
            w = next((w for w in QGuiApplication.topLevelWindows() if w and int(w.winId()) == hWnd), None)
            if not w: return 0
            r = win32api.GetSystemMetrics(win32con.SM_CXSIZEFRAME) + win32api.GetSystemMetrics(92)
            if r > 0: return r
            return round((8 if QtWin.isCompositionEnabled() else 4) * w.devicePixelRatio())

    class BaseWidget(QWidget):
        changedToDark = Signal(bool)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def _initVal(self):
            self._pressToMove, self._resizable, self._border_width = True, True, 5
            self.__detect_theme_flag = True
            self._titleBar = TitleBar(self, getattr(self, '_hint', ['min', 'max', 'close']))
            self._restore_geometry = None

        def _initUi(self, hint=None, flags: list = []):
            if hint is None: hint = ['min', 'max', 'close']
            self._hint = hint
            self._windowEffect = WindowsEffectHelper()
            newFlags = self.windowFlags() | Qt.FramelessWindowHint
            for flag in flags: newFlags |= flag
            self.setWindowFlags(newFlags)
            self._windowEffect.setBasicEffect(self.winId(), hint)
            self.windowHandle().screenChanged.connect(self._onScreenChanged)
            self.__setCurrentWindowsTheme()

        def _updateAeroEffect(self):
            hWnd = int(self.winId())
            margins = MARGINS(0, 0, 0, 0) if self.isMaximized() else MARGINS(-1, -1, -1, -1)
            self._windowEffect.dwmapi.DwmExtendFrameIntoClientArea(hWnd, byref(margins))

        def minimize(self):
            self.showMinimized()

        def toggleMaximize(self):
            if self.isMaximized() or self.isFullScreen():
                self.showNormal()
                if self._restore_geometry:
                    self.setGeometry(self._restore_geometry)
            else:
                self._restore_geometry = self.geometry()
                self.showMaximized()

        def _startSystemMove(self):
            if self.isMaximized():
                self.toggleMaximize()
                
                cursor_pos = QCursor.pos()
                if self._restore_geometry:
                    title_bar_width = self._restore_geometry.width()
                    click_ratio = (cursor_pos.x() - self._restore_geometry.left()) / title_bar_width if title_bar_width > 0 else 0.5
                    
                    new_x = cursor_pos.x() - int(self._restore_geometry.width() * click_ratio)
                    new_y = cursor_pos.y() - (self._titleBar.height() // 2)
                    self.move(new_x, new_y)
            
            self.window().windowHandle().startSystemMove()

        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton and self._pressToMove:
                if hasattr(self, '_titleBar') and self._titleBar.geometry().contains(e.pos()):
                     self._startSystemMove()
            return super().mousePressEvent(e)

        def isPressToMove(self) -> bool:
            return self._pressToMove

        def setPressToMove(self, f: bool):
            self._pressToMove = f

        def __setCurrentWindowsTheme(self):
            try:
                k = OpenKey(HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 0, KEY_READ)
                v, _ = QueryValueEx(k, 'AppsUseLightTheme')
                dark_f = v == 0
                self._windowEffect.setDarkTheme(self.winId(), dark_f)
                self.changedToDark.emit(dark_f)
            except Exception:
                pass

        def setDarkTheme(self, f: bool):
            self._windowEffect.setDarkTheme(self.winId(), f)

        def isDetectingThemeAllowed(self):
            return self.__detect_theme_flag

        def allowDetectingTheme(self, f: bool):
            self.__detect_theme_flag = f

        def isResizable(self) -> bool:
            return self._resizable

        def setResizable(self, f: bool):
            self._resizable = f

        def nativeEvent(self, e, message):
            msg = MSG.from_address(message.__int__())
            if not msg.hWnd: return super().nativeEvent(e, message)

            if msg.message == win32con.WM_SIZE:
                self._updateAeroEffect()

            if msg.message == win32con.WM_NCHITTEST and self._resizable:
                if self.isMaximized() or self.isFullScreen():
                    return super().nativeEvent(e, message)
                x, y = QCursor.pos().x() - self.x(), QCursor.pos().y() - self.y()
                w, h, b = self.width(), self.height(), self._border_width
                l, r, t, bt = x < b, x > w - b, y < b, y > h - b
                if t and l: return True, win32con.HTTOPLEFT
                if t and r: return True, win32con.HTTOPRIGHT
                if bt and l: return True, win32con.HTBOTTOMLEFT
                if bt and r: return True, win32con.HTBOTTOMRIGHT
                if l: return True, win32con.HTLEFT
                if r: return True, win32con.HTRIGHT
                if t: return True, win32con.HTTOP
                if bt: return True, win32con.HTBOTTOM
            elif msg.message == win32con.WM_NCCALCSIZE:
                r = cast(msg.lParam, LPNCCALCSIZE_PARAMS).contents.rgrc[0] if msg.wParam else cast(msg.lParam, LPRECT).contents
                max_f, full_f = _Win32Utils.isMaximized(msg.hWnd), _Win32Utils.isFullScreen(msg.hWnd)
                if max_f and not full_f:
                    th = _Win32Utils.getResizeBorderThickness(msg.hWnd)
                    r.top += th
                    r.left += th
                    r.right -= th
                    r.bottom -= th
                if (max_f or full_f) and _Win32Utils.Taskbar.isAutoHide():
                    p = _Win32Utils.Taskbar.getPosition(msg.hWnd)
                    if p in [_Win32Utils.Taskbar.TOP, _Win32Utils.Taskbar.LEFT]: r.top += _Win32Utils.Taskbar.AUTO_HIDE_THICKNESS
                    elif p == _Win32Utils.Taskbar.BOTTOM: r.bottom -= _Win32Utils.Taskbar.AUTO_HIDE_THICKNESS
                return True, 0 if not msg.wParam else win32con.WVR_REDRAW
            elif msg.message == win32con.WM_SETTINGCHANGE and self.__detect_theme_flag:
                self.__setCurrentWindowsTheme()
            return super().nativeEvent(e, message)

        def _onScreenChanged(self):
            hWnd = int(self.windowHandle().winId())
            win32gui.SetWindowPos(hWnd, None, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_FRAMECHANGED)

        def setWindowIcon(self, icon):
            icon = QIcon(icon) if isinstance(icon, str) else icon
            super().setWindowIcon(icon)

        def setWindowTitle(self, title: str):
            super().setWindowTitle(title)

        def getTitleBar(self):
            return self._titleBar

        def setFixedSize(self, width, height):
            super().setFixedSize(width, height)
            self.setResizable(False)

else:
    class BaseWidget(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def _initVal(self):
            self._resizable, self._pressToMove = True, True
            self._margin, self._cursor = 5, QCursor()
            self._titleBar = TitleBar(self, getattr(self, '_hint', ['min', 'max', 'close']))
            self._resizing = False
            self._initPosition()

        def _initUi(self, hint, flags):
            if hint is None: hint = ['min', 'max', 'close']
            self._hint = hint
            self.setMouseTracking(True)
            newFlags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint
            for flag in flags: newFlags |= flag
            self.setWindowFlags(newFlags)
        
        def minimize(self):
            self.showMinimized()

        def toggleMaximize(self):
            if self.isMaximized() or self.isFullScreen():
                self.showNormal()
            else:
                self.showMaximized()

        def _initPosition(self):
            self._top = self._bottom = self._left = self._right = False

        def _setCursorShape(self, p):
            if not (self.isResizable() and not (self.isMaximized() or self.isFullScreen())): return
            rect = self.rect().adjusted(self._margin, self._margin, -self._margin, -self._margin)
            on_edge = not rect.contains(p)
            if on_edge:
                x, y, w, h = p.x(), p.y(), self.width(), self.height()
                self._left, self._right = x < self._margin, x > w - self._margin
                self._top, self._bottom = y < self._margin, y > h - self._margin
                if (self._top and self._left) or (self._bottom and self._right): self._cursor.setShape(Qt.SizeFDiagCursor)
                elif (self._top and self._right) or (self._bottom and self._left): self._cursor.setShape(Qt.SizeBDiagCursor)
                elif self._left or self._right: self._cursor.setShape(Qt.SizeHorCursor)
                elif self._top or self._bottom: self._cursor.setShape(Qt.SizeVerCursor)
                self.setCursor(self._cursor)
            else: self.unsetCursor(); self._initPosition()
            self._resizing = on_edge

        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton:
                if self._resizing: 
                    self.window().windowHandle().startSystemResize(self._get_edge())
                elif self._pressToMove and self._titleBar.geometry().contains(e.pos()):
                    self.window().windowHandle().startSystemMove()

        def mouseMoveEvent(self, e):
            self._setCursorShape(e.pos())

        def _get_edge(self):
            if self._top and self._left: return Qt.TopEdge | Qt.LeftEdge
            if self._top and self._right: return Qt.TopEdge | Qt.RightEdge
            if self._bottom and self._left: return Qt.BottomEdge | Qt.LeftEdge
            if self._bottom and self._right: return Qt.BottomEdge | Qt.RightEdge
            if self._left: return Qt.LeftEdge
            if self._right: return Qt.RightEdge
            if self._top: return Qt.TopEdge
            if self._bottom: return Qt.BottomEdge
            return Qt.ArrowCursor

        def isResizable(self) -> bool:
            return self._resizable

        def setResizable(self, f: bool):
            self._resizable = f

        def isPressToMove(self) -> bool:
            return self._pressToMove

        def setPressToMove(self, f: bool):
            self._pressToMove = f

        def setWindowIcon(self, icon):
            icon = QIcon(icon) if isinstance(icon, str) else icon
            super().setWindowIcon(icon)

        def setWindowTitle(self, title: str):
            super().setWindowTitle(title)

        def getTitleBar(self):
            return self._titleBar

        def setFixedSize(self, width, height):
            super().setFixedSize(width, height)
            self.setResizable(False)

class FramelessWidget(BaseWidget):
    def __init__(self, hint=None, flags: list = []):
        super().__init__()
        self._initVal()
        self._initUi(hint, flags)
        lay = QVBoxLayout(self)
        if hasattr(self, '_titleBar') and self._titleBar:
            lay.addWidget(self._titleBar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)