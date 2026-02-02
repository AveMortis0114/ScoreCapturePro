import sys, os, re, time, qrcode, numpy as np, cv2, imagehash, tempfile, shutil, ctypes
import traceback
import json
import webbrowser
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# 기본 설정
OUTPUT_FOLDER = os.path.join(tempfile.gettempdir(), f"ScoreCapturePro_{os.getpid()}")  # 임시 폴더 경로
DEFAULT_SENSITIVITY = "0.9"        # 이미지 변화 감지 민감도 (SSIM 임계값)
DEFAULT_DELAY = "3"                # 캡처 시작 전 카운트다운 (초)
DEFAULT_MARGIN = "60"              # PDF 생성 시 페이지 여백 (px)
DEFAULT_SPACING = "40"             # PDF 생성 시 이미지 간 간격 (px)
DEFAULT_OPACITY = 100              # 프로그램 창 기본 투명도 (100 = 불투명)
MIN_OPACITY = 20                   # 프로그램 창 최소 투명도

# 리소스 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "fonts")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "NotoSansKR-Bold.ttf")
FONT_REGULAR_PATH = os.path.join(FONT_DIR, "NotoSansKR-Regular.ttf")
ICON_PATH = os.path.join(BASE_DIR, "assets", "icon.ico")
ICON_PNG_PATH = os.path.join(BASE_DIR, "assets", "icon.png")
SUN_ICON_PATH = os.path.join(BASE_DIR, "assets", "sun.svg")
MOON_ICON_PATH = os.path.join(BASE_DIR, "assets", "moon.svg")
COMPACT_ICON_PATH = os.path.join(BASE_DIR, "assets", "compact.svg")
EXPAND_ICON_PATH = os.path.join(BASE_DIR, "assets", "expand.svg")

# 앱 상수
APP_TITLE = "Score Capture Pro"
APP_WINDOW_TITLE = "Score Capture Pro - 화면 악보 자동 캡처"

# 이스터 에그 상수
EASTER_EGG_TITLE = "내 시그나 사라"
EASTER_EGG_IMAGE_PATH = os.path.join(BASE_DIR, "assets", "BuyMySignature.png")
EASTER_EGG_TRIGGER_COUNT = 5

def load_version_info():
    """version.json 파일 로드"""
    json_path = os.path.join(BASE_DIR, "version.json")
    default_info = {
        "version": "1.0.0",
        "developer": "Developer",
        "github": "",
        "repo_api_url": ""
    }
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                default_info.update(data)
        except Exception:
            pass
    return default_info

VERSION_INFO = load_version_info()

def imread_unicode(path):
    """한글 경로 지원 이미지 읽기"""
    try:
        stream = np.fromfile(path, np.uint8)
        return cv2.imdecode(stream, cv2.IMREAD_COLOR)
    except Exception:
        return None

def imwrite_unicode(path, img):
    """한글 경로 지원 이미지 쓰기"""
    try:
        ext = os.path.splitext(path)[1]
        result, n = cv2.imencode(ext, img)
        if result:
            with open(path, mode='wb') as f:
                n.tofile(f)
            return True
        return False
    except Exception:
        return False
    
def cleanup_old_temp_folders():
    """실행 시 이전 실행에서 남은 임시 폴더 정리"""
    temp_dir = tempfile.gettempdir()
    current_pid = os.getpid()
    
    try:
        for name in os.listdir(temp_dir):
            if name.startswith("ScoreCapturePro_"):
                folder_path = os.path.join(temp_dir, name)
                if not os.path.isdir(folder_path):
                    continue
                    
                try:
                    # 폴더명에서 PID 추출
                    pid_str = name.replace("ScoreCapturePro_", "")
                    pid = int(pid_str)
                    
                    # 현재 프로세스는 건너뜀
                    if pid == current_pid:
                        continue
                        
                    # 프로세스 생존 여부 확인
                    is_running = False
                    try:
                        os.kill(pid, 0)
                        is_running = True
                    except ProcessLookupError:
                        is_running = False
                    except (PermissionError, OSError):
                        is_running = True
                    
                    if not is_running:
                        shutil.rmtree(folder_path, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass

def get_system_theme():
    """시스템 다크모드 설정 감지"""
    try:
        # Windows
        if sys.platform == "win32":
            import winreg
            try:
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return "light" if value == 1 else "dark"
            except:
                return "light"
        # macOS
        elif sys.platform == "darwin":
            import subprocess
            try:
                result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], 
                                      capture_output=True, text=True)
                return "dark" if "Dark" in result.stdout else "light"
            except:
                return "light"
        # Linux
        else:
            return "light"
    except:
        return "light"

# UI 스타일시트
LIGHT_STYLE = """
/* 메인 윈도우 및 다이얼로그 */
QMainWindow, QDialog {
    background-color: #f5f5f5;
}

QWidget {
    font-family: 'Segoe UI', 'Apple SD Gothic Neo', sans-serif;
    font-size: 12px;
    color: #333333;
}

/* 그룹박스 */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    margin-top: 6px;
    padding-top: 14px;
    font-weight: 600;
    font-size: 11px;
    color: #2c2c2c;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 3px 10px;
    color: #2c2c2c;
}

/* 입력 필드 */
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 6px 10px;
    color: #333333;
    font-size: 12px;
}

QLineEdit:focus {
    border: 1px solid #0078d4;
    background-color: #ffffff;
}

QLineEdit::placeholder {
    color: #999999;
}

/* 콤보박스 */
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 10px;
    color: #333333;
}

QComboBox:hover {
    border: 1px solid #0078d4;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #333333;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    border: 1px solid #d0d0d0;
    outline: none;
}

/* 체크박스 */
QCheckBox {
    spacing: 5px;
    color: #333333;
}

QCheckBox::indicator:unchecked:hover {
    border: 1px solid #a0a0a0;
    background-color: #f5f5f5;
    border-radius: 2px;
}

/* 기본 버튼 */
QPushButton {
    background-color: #0078d4;
    border: none;
    border-radius: 4px;
    padding: 8px 14px;
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #106ebe;
}

QPushButton:pressed {
    background-color: #005a9e;
}

QPushButton:disabled {
    background-color: #e0e0e0;
    color: #a0a0a0;
}

/* 영역 선택 버튼 */
QPushButton#selectButton {
    background-color: #6a5acd;
    color: #ffffff;
}

QPushButton#selectButton:hover {
    background-color: #5b4ab8;
}

QPushButton#selectButton:pressed {
    background-color: #4c3ba3;
}

/* 캡처 시작 버튼 */
QPushButton#captureButton {
    background-color: #28a745;
    color: #ffffff;
    font-size: 13px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#captureButton:hover {
    background-color: #218838;
}

QPushButton#captureButton:pressed {
    background-color: #1e7e34;
}

/* 캡처 중지 버튼 */
QPushButton#captureButtonActive {
    background-color: #dc3545;
    color: #ffffff;
    font-size: 13px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#captureButtonActive:hover {
    background-color: #c82333;
}

QPushButton#captureButtonActive:pressed {
    background-color: #bd2130;
}

/* PDF 생성 버튼 */
QPushButton#pdfButton {
    background-color: #ff8c00;
    color: #ffffff;
    font-size: 13px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#pdfButton:hover {
    background-color: #e67e00;
}

QPushButton#pdfButton:pressed {
    background-color: #cc7000;
}

QFrame#listContainer {
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    background-color: #ffffff;
}

/* 리스트 위젯 */
QListWidget {
    background-color: transparent;
    border: none;
    padding: 3px;
    color: #333333;
    outline: none;
}

QListWidget::item {
    background-color: #fafafa;
    border-radius: 3px;
    padding: 3px 8px;
    margin: 1px;
    border: 1px solid #e8e8e8;
    color: #333333;
}

QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
    border: 1px solid #0078d4;
}

QListWidget::item:hover {
    background-color: #e8f4fd;
    border: 1px solid #0078d4;
    color: #333333;
}

QListWidget::item:selected:hover {
    background-color: #106ebe;
    color: #ffffff;
}

/* 라벨 */
QLabel#statusLabel {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 8px;
    font-weight: 600;
    color: #333333;
    font-size: 11px;
}

QLabel#previewLabel {
    background-color: #e0e0e0;
    border: 2px dashed #aaaaaa;
    border-radius: 10px;
    padding: 6px;
    font-size: 14px;
    color: #666666;
}

/* 테마 버튼 */
QPushButton#themeButton {
    background-color: transparent;
    border: none;
    border-radius: 16px;
    font-size: 20px;
    margin: 0px;
}
QPushButton#themeButton:hover {
    background-color: rgba(0, 0, 0, 0.06);
}

/* 미니 모드 스타일 오버라이드 */
QFrame#leftPanel[miniMode="true"] {
    border: none;
}

QLabel#statusLabel[miniMode="true"] {
    padding: 0px 4px;
    font-size: 11px;
}

QLabel#miniPreviewLabel {
    background-color: #f0f0f0;
    color: #666666;
    border-radius: 4px;
    border: 1px solid #d0d0d0;
}

QLabel#headerLabel {
    font-size: 16px;
    font-weight: 700;
    color: #2c2c2c;
    padding: 6px 0px;
}

QLabel#sectionLabel {
    font-size: 11px;
    font-weight: 600;
    color: #666666;
    padding: 4px 0px;
}

/* 스플리터 */
QSplitter::handle {
    background-color: #d0d0d0;
    width: 1px;
}

QSplitter::handle:hover {
    background-color: #0078d4;
}

/* 스크롤바 */
QScrollBar:vertical {
    background: #f5f5f5;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #c0c0c0;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #a0a0a0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* 프레임 */
QFrame#leftPanel {
    background-color: #f5f5f5;
    border-right: 1px solid #d0d0d0;
}

/* 슬라이더 */
QSlider::groove:horizontal {
    background: #d0d0d0;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #0078d4;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #106ebe;
}
"""

DARK_STYLE = """
/* 메인 윈도우 및 다이얼로그 */
QMainWindow, QDialog {
    background-color: #1e1e1e;
}

QWidget {
    font-family: 'Segoe UI', 'Apple SD Gothic Neo', sans-serif;
    font-size: 12px;
    color: #e0e0e0;
}

/* 그룹박스 */
QGroupBox {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    margin-top: 6px;
    padding-top: 14px;
    font-weight: 600;
    font-size: 11px;
    color: #e0e0e0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 3px 10px;
    color: #e0e0e0;
}

/* 입력 필드 */
QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e0e0e0;
    font-size: 12px;
}

QLineEdit:focus {
    border: 1px solid #0078d4;
    background-color: #2d2d2d;
}

QLineEdit::placeholder {
    color: #808080;
}

/* 콤보박스 */
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 4px 10px;
    color: #e0e0e0;
}

QComboBox:hover {
    border: 1px solid #0078d4;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    border: 1px solid #3d3d3d;
    outline: none;
}

/* 체크박스 */
QCheckBox {
    spacing: 5px;
    color: #e0e0e0;
}

QCheckBox::indicator:unchecked:hover {
    border: 1px solid #606060;
    background-color: #3d3d3d;
    border-radius: 2px;
}

/* 기본 버튼 */
QPushButton {
    background-color: #0078d4;
    border: none;
    border-radius: 4px;
    padding: 8px 14px;
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #106ebe;
}

QPushButton:pressed {
    background-color: #005a9e;
}

QPushButton:disabled {
    background-color: #3d3d3d;
    color: #808080;
}

/* 영역 선택 버튼 */
QPushButton#selectButton {
    background-color: #6a5acd;
    color: #ffffff;
}

QPushButton#selectButton:hover {
    background-color: #5b4ab8;
}

QPushButton#selectButton:pressed {
    background-color: #4c3ba3;
}

/* 캡처 시작 버튼 */
QPushButton#captureButton {
    background-color: #28a745;
    color: #ffffff;
    font-size: 13px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#captureButton:hover {
    background-color: #218838;
}

QPushButton#captureButton:pressed {
    background-color: #1e7e34;
}

/* 캡처 중지 버튼 */
QPushButton#captureButtonActive {
    background-color: #dc3545;
    color: #ffffff;
    font-size: 13px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#captureButtonActive:hover {
    background-color: #c82333;
}

QPushButton#captureButtonActive:pressed {
    background-color: #bd2130;
}

/* PDF 생성 버튼 */
QPushButton#pdfButton {
    background-color: #ff8c00;
    color: #ffffff;
    font-size: 13px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton#pdfButton:hover {
    background-color: #e67e00;
}

QPushButton#pdfButton:pressed {
    background-color: #cc7000;
}

QFrame#listContainer {
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    background-color: #2d2d2d;
}

/* 리스트 위젯 */
QListWidget {
    background-color: transparent;
    border: none;
    padding: 3px;
    color: #e0e0e0;
    outline: none;
}

QListWidget::item {
    background-color: #2d2d2d;
    border-radius: 3px;
    padding: 3px 8px;
    margin: 1px;
    border: 1px solid #3d3d3d;
    color: #e0e0e0;
}

QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
    border: 1px solid #0078d4;
}

QListWidget::item:hover {
    background-color: #3d3d3d;
    border: 1px solid #0078d4;
    color: #e0e0e0;
}

QListWidget::item:selected:hover {
    background-color: #106ebe;
    color: #ffffff;
}

/* 라벨 */
QLabel#statusLabel {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 8px;
    font-weight: 600;
    color: #e0e0e0;
    font-size: 11px;
}

QLabel#previewLabel {
    background-color: #2d2d2d;
    border: 2px dashed #606060;
    border-radius: 10px;
    padding: 6px;
    font-size: 14px;
    color: #a0a0a0;
}

/* 테마 버튼 */
QPushButton#themeButton {
    background-color: transparent;
    border: none;
    border-radius: 16px;
    font-size: 20px;
    margin: 0px;
}
QPushButton#themeButton:hover {
    background-color: rgba(255, 255, 255, 0.1);
}

/* 미니 모드 스타일 오버라이드 */
QFrame#leftPanel[miniMode="true"] {
    border: none;
}

QLabel#statusLabel[miniMode="true"] {
    padding: 0px 4px;
    font-size: 11px;
}

QLabel#miniPreviewLabel {
    background-color: #2d2d2d;
    color: #a0a0a0;
    border-radius: 4px;
    border: 1px solid #3d3d3d;
}

QLabel#headerLabel {
    font-size: 16px;
    font-weight: 700;
    color: #e0e0e0;
    padding: 6px 0px;
}

QLabel#sectionLabel {
    font-size: 11px;
    font-weight: 600;
    color: #a0a0a0;
    padding: 4px 0px;
}

/* 스플리터 */
QSplitter::handle {
    background-color: #3d3d3d;
    width: 1px;
}

QSplitter::handle:hover {
    background-color: #0078d4;
}

/* 스크롤바 */
QScrollBar:vertical {
    background: #2d2d2d;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #606060;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #808080;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* 프레임 */
QFrame#leftPanel {
    background-color: #1e1e1e;
    border-right: 1px solid #3d3d3d;
}

/* 슬라이더 */
QSlider::groove:horizontal {
    background: #3d3d3d;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #0078d4;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #106ebe;
}
"""

EASTER_EGG_STYLE = """
/* 이스터 에그 스타일 */
QMainWindow, QDialog {
    background-color: #000000;
}

QWidget {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #00ff00;
}

QGroupBox {
    background-color: #001000;
    border: 1px solid #00ff00;
    color: #00ff00;
    margin-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #00ff00;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #000000;
    border: 1px solid #00ff00;
    color: #00ff00;
    selection-background-color: #00ff00;
    selection-color: #000000;
}

QPushButton {
    background-color: #000000;
    border: 1px solid #00ff00;
    color: #00ff00;
    font-weight: bold;
    padding: 5px;
}

QPushButton:hover {
    background-color: #00ff00;
    color: #000000;
}

QPushButton:pressed {
    background-color: #008800;
    color: #000000;
}

QListWidget {
    background-color: #000000;
    border: 1px solid #00ff00;
    color: #00ff00;
    outline: none;
}

QListWidget::item {
    border: 1px solid #00ff00;
    margin: 2px;
    padding: 4px;
}

QListWidget::item:selected {
    background-color: #00ff00;
    color: #000000;
}

QLabel {
    color: #00ff00;
}

QLabel#previewLabel {
    border: 2px dashed #00ff00;
    border-radius: 10px;
    padding: 6px;
}

QLabel#miniPreviewLabel {
    border: 1px solid #00ff00;
    border-radius: 4px;
}

QLabel#statusLabel {
    border: 2px dashed #00ff00;
    border-radius: 4px;
    padding: 6px;
}

QScrollBar:vertical {
    background: #000000;
    border-left: 1px solid #00ff00;
}
QScrollBar::handle:vertical {
    background: #00ff00;
}
"""

def apply_window_theme(widget, parent=None):
    """부모 창의 상태(테마, 이스터에그)를 기반으로 윈도우 테마 적용"""
    theme = "light"
    target = parent if parent else QApplication.activeWindow()
    
    if target:
        win = target.window()
        if hasattr(win, "is_easter_egg_active") and win.is_easter_egg_active:
            theme = "dark"
        elif hasattr(win, "current_theme"):
            theme = win.current_theme
        else:
            theme = get_system_theme()
    else:
        theme = get_system_theme()
    
    set_window_theme(widget, theme)

def set_window_theme(widget, theme_str):
    """윈도우 타이틀바 색상 변경 (Windows DWM & macOS)"""
    if sys.platform == "win32":
        try:
            from ctypes import windll, c_int, byref, sizeof
            hwnd = int(widget.winId())
            is_dark = 1 if theme_str == "dark" else 0
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                20, 
                byref(c_int(is_dark)), 
                sizeof(c_int)
            )
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            import ctypes.util
            libobjc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
            c_void_p = ctypes.c_void_p
            c_char_p = ctypes.c_char_p
            
            objc_getClass = libobjc.objc_getClass
            objc_getClass.restype = c_void_p
            objc_getClass.argtypes = [c_char_p]
            
            sel_registerName = libobjc.sel_registerName
            sel_registerName.restype = c_void_p
            sel_registerName.argtypes = [c_char_p]
            
            objc_msgSend = libobjc.objc_msgSend
            objc_msgSend.restype = c_void_p
            
            def _utf8(s): return s.encode('utf-8')
            
            ns_view = c_void_p(int(widget.winId()))
            
            objc_msgSend.argtypes = [c_void_p, c_void_p]
            ns_window = objc_msgSend(ns_view, sel_registerName(_utf8("window")))
            
            if ns_window:
                style = "NSAppearanceNameDarkAqua" if theme_str == "dark" else "NSAppearanceNameAqua"
                
                objc_msgSend.argtypes = [c_void_p, c_void_p, c_char_p]
                ns_str = objc_msgSend(objc_getClass(_utf8("NSString")), sel_registerName(_utf8("stringWithUTF8String:")), _utf8(style))
                
                objc_msgSend.argtypes = [c_void_p, c_void_p, c_void_p]
                appearance = objc_msgSend(objc_getClass(_utf8("NSAppearance")), sel_registerName(_utf8("appearanceNamed:")), ns_str)
                
                objc_msgSend(ns_window, sel_registerName(_utf8("setAppearance:")), appearance)
        except Exception:
            pass

def show_message(parent, title, text, icon=QMessageBox.Icon.Information, buttons=QMessageBox.StandardButton.Ok, default_button=None, detailed_text=None):
    """테마가 적용된 메시지 박스 표시"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStandardButtons(buttons)
    if default_button:
        msg.setDefaultButton(default_button)
    if detailed_text:
        msg.setDetailedText(detailed_text)
    
    apply_window_theme(msg, parent)
    return msg.exec()

def grab_screen_area(x, y, w, h):
    """멀티 모니터 지원 화면 캡처"""
    screens = QApplication.screens()
    target_rect = QRect(x, y, w, h)
    
    # 캡처 영역의 중심이 있는 화면의 DPR을 구함 (HiDPI 지원)
    center = target_rect.center()
    target_screen = screens[0]
    for screen in screens:
        if screen.geometry().contains(center):
            target_screen = screen
            break
    dpr = target_screen.devicePixelRatio()

    # 물리 픽셀 크기로 Pixmap 생성 후 DPR 설정 (고해상도 유지)
    res_pixmap = QPixmap(int(w * dpr), int(h * dpr))
    res_pixmap.setDevicePixelRatio(dpr)
    res_pixmap.fill(Qt.black)
    
    painter = QPainter(res_pixmap)
    
    for screen in screens:
        geo = screen.geometry()
        intersect = geo.intersected(target_rect)
        
        if not intersect.isEmpty():
            local_x = intersect.x() - geo.x()
            local_y = intersect.y() - geo.y()
            
            grab = screen.grabWindow(0, local_x, local_y, intersect.width(), intersect.height())
            
            dest_x = intersect.x() - x
            dest_y = intersect.y() - y
            painter.drawPixmap(dest_x, dest_y, grab)
            
    painter.end()
    return res_pixmap

class SelectionOverlay(QWidget):
    """영역 선택 오버레이"""
    selection_finished = Signal(dict) 
    selection_cancelled = Signal()
    
    def __init__(self, parent=None, font_family="Segoe UI"): 
        super().__init__(parent)
        self.font_family = font_family
        # 전체 화면 오버레이 설정
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        self.start_pos = None
        self.current_pos = None
        self.is_selecting = False
        self.bg_pixmap = None

    def start(self):
        """화면 캡처 후 선택 모드 시작"""
        screens = QApplication.screens()
        x_min = min(s.geometry().x() for s in screens)
        y_min = min(s.geometry().y() for s in screens)
        x_max = max(s.geometry().x() + s.geometry().width() for s in screens)
        y_max = max(s.geometry().y() + s.geometry().height() for s in screens)
        
        virtual_rect = QRect(x_min, y_min, x_max - x_min, y_max - y_min)
        self.setGeometry(virtual_rect)
        
        # 현재 화면을 캡처하여 배경으로 사용 (Freeze 효과)
        self.bg_pixmap = grab_screen_area(virtual_rect.x(), virtual_rect.y(), virtual_rect.width(), virtual_rect.height())
        
        self.show()
        self.activateWindow()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.selection_cancelled.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.position().toPoint()
            self.current_pos = event.position().toPoint()
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            rect = QRect(self.start_pos, self.current_pos).normalized()
            if rect.width() > 10 and rect.height() > 10:
                final_area = {
                    'top': self.y() + rect.y(),
                    'left': self.x() + rect.x(),
                    'width': rect.width(),
                    'height': rect.height()
                }
                self.close()
                self.selection_finished.emit(final_area)
            else:
                self.start_pos = None
                self.current_pos = None
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        if self.bg_pixmap:
            painter.drawPixmap(self.rect(), self.bg_pixmap)
            
            # 배경 어둡게 처리
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
            
            if self.start_pos and self.current_pos:
                rect = QRect(self.start_pos, self.current_pos).normalized()
                
                # 논리 좌표(Widget) -> 물리 좌표(Pixmap) 비율 계산
                sx = self.bg_pixmap.width() / self.width()
                sy = self.bg_pixmap.height() / self.height()
                
                # 원본 이미지에서 가져올 실제 물리 좌표 영역 계산
                source_rect = QRect(
                    int(rect.x() * sx), int(rect.y() * sy),
                    int(rect.width() * sx), int(rect.height() * sy)
                )
                
                # 선택 영역은 원본 밝기로 그리기
                painter.drawPixmap(rect, self.bg_pixmap, source_rect)
                
                # 테두리
                pen = QPen(QColor(0, 120, 212), 2, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawRect(rect)
                
                # 사이즈 텍스트
                painter.setPen(Qt.white)
                font = QFont(self.font_family, 9, QFont.Bold)
                painter.setFont(font)
                text = f"{rect.width()} × {rect.height()} px"
                painter.drawText(rect.topLeft() - QPoint(0, 5), text)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

class CaptureAreaIndicator(QWidget):
    """선택된 영역을 화면에 계속 표시하는 투명 위젯"""
    def __init__(self, x, y, w, h, parent=None):
        super().__init__(parent)
        self.setGeometry(x, y, w, h)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # 마우스 이벤트를 통과시킴
        self.border_color = QColor(0, 255, 0)  # 기본: 초록색
        self.show()

    def set_color(self, color):
        self.border_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(self.border_color, 3)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

def enhance_score_image(img_bgr, use_basic=False, use_high=False):
    """OpenCV DNN Super Resolution을 이용한 업스케일링 (모델 없으면 Bicubic+Sharpening)"""
    if not use_basic and not use_high:
        return img_bgr

    # 모델 파일이 위치할 경로 (models 폴더)
    models_dir = os.path.join(BASE_DIR, "models")
    
    # 고화질 모드(EDSR)가 체크되어 있으면 EDSR 우선 사용
    if use_high:
        model_path = os.path.join(models_dir, "EDSR_x4.pb")
        algo = "edsr"
    # 기본 모드만 체크되어 있으면 LapSRN 사용
    elif use_basic:
        model_path = os.path.join(models_dir, "LapSRN_x4.pb")
        algo = "lapsrn"
    else:
        return img_bgr
    
    model_info = None
    
    if os.path.exists(model_path):
        model_info = (model_path, algo, 4)

    result_img = None

    if model_info and hasattr(cv2, 'dnn_superres'):
        try:
            path, algo, scale = model_info
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(path)
            sr.setModel(algo, scale)
            result_img = sr.upsample(img_bgr)
        except Exception as e:
            print(f"DNN Upscaling error: {e}")

    # 모델 적용에 실패했거나 모델이 없는 경우 (기본 모드일 때만 Fallback)
    if result_img is None and use_basic and not use_high:
        # Fallback: Bicubic Interpolation + Sharpening
        upscaled = cv2.resize(img_bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        result_img = cv2.filter2D(upscaled, -1, kernel)
    
    # 만약 모델 적용이 안됐는데 result_img가 None이면 원본 반환
    if result_img is None:
        result_img = img_bgr

    return result_img

def apply_natural_grayscale(img_bgr):
    """자연스러운 흑백 악보 변환 (스캔 효과)"""
    if img_bgr is None: return None
    
    # 1. 그레이스케일 변환
    if len(img_bgr.shape) == 3:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_bgr

    # 2. 2배 업스케일링 (Cubic Interpolation)
    enhanced = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    
    # 3. Soft Thresholding (Gamma Correction)
    # 정규화 (0~255)
    norm = cv2.normalize(enhanced, None, 0, 255, cv2.NORM_MINMAX)
    
    # 감마 보정 (Gamma > 1: 어두운 영역 강조 / Gamma < 1: 밝은 영역 강조)
    gamma = 1.5
    table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    soft_binary = cv2.LUT(norm, table)
    
    return cv2.cvtColor(soft_binary, cv2.COLOR_GRAY2BGR)

def cv2_to_qpixmap(img_cv):
    """OpenCV 이미지를 QPixmap으로 변환"""
    if img_cv is None:
        return QPixmap()
    # 메모리 연속성 보장
    if not img_cv.flags['C_CONTIGUOUS']:
        img_cv = np.ascontiguousarray(img_cv)
    
    rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)

def qpixmap_to_cv(pixmap):
    """QPixmap을 OpenCV 이미지(BGR)로 변환"""
    if pixmap.isNull():
        return None
    img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    arr = np.array(ptr).reshape(h, img.bytesPerLine())
    # 패딩 제거 및 BGR 변환
    arr = arr[:, :w * 3].reshape(h, w, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def calculate_ssim(img1, img2):
    """scikit-image 제거를 위한 OpenCV 기반 SSIM 계산 함수"""
    if img1.shape != img2.shape:
        return 0.0

    # SSIM 상수 (L=255 기준)
    C1 = 6.5025  # (0.01 * 255)^2
    C2 = 58.5225 # (0.03 * 255)^2

    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)

    # 커널 크기 설정 (이미지가 작을 경우 대비)
    k_size = 11
    min_dim = min(img1.shape[0], img1.shape[1])
    if min_dim < k_size:
        k_size = min_dim
        if k_size % 2 == 0: k_size -= 1
        if k_size < 3: k_size = 3

    kernel = (k_size, k_size)
    sigma = 1.5

    mu1 = cv2.GaussianBlur(img1, kernel, sigma)
    mu2 = cv2.GaussianBlur(img2, kernel, sigma)

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(img1 ** 2, kernel, sigma) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2 ** 2, kernel, sigma) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, kernel, sigma) - mu1_mu2

    t1 = 2 * mu1_mu2 + C1
    t2 = 2 * sigma12 + C2
    t3 = mu1_sq + mu2_sq + C1
    t4 = sigma1_sq + sigma2_sq + C2

    ssim_map = (t1 * t2) / (t3 * t4)
    return ssim_map.mean()

def get_pil_font(path, size):
    """PIL 폰트 로드 헬퍼"""
    try:
        return ImageFont.truetype(path, size=size)
    except IOError:
        return ImageFont.load_default()

def get_text_size(draw, text, font):
    """Pillow 버전 호환 텍스트 크기 계산"""
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    else:
        return draw.textsize(text, font=font)

def calculate_best_cut_point(img, min_x, max_x):
    """이미지에서 최적의 자르기 위치(세로선)를 찾습니다."""
    h, w = img.shape[:2]
    if min_x >= max_x or max_x > w:
        return None
        
    roi = img[:, min_x:max_x]
    
    # 1. 전처리: 그레이스케일 -> 이진화
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 2. 세로선 추출
    line_height = max(int(h * 0.3), 10) 
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_height))
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    # 3. 수직 투영
    col_sums = np.sum(vertical_lines, axis=0) / 255
    
    # 4. 피크 검출
    candidates = []
    min_line_pixels = line_height * 0.5 
    
    for x in range(1, len(col_sums) - 1):
        val = col_sums[x]
        if val > min_line_pixels:
            if val >= col_sums[x-1] and val >= col_sums[x+1]:
                if not candidates or (min_x + x) - candidates[-1][0] > 5:
                    candidates.append((min_x + x, val))
    
    if candidates:
        candidates.sort(key=lambda item: (item[1], item[0]), reverse=True)
        best_x = candidates[0][0]
        return best_x + 5
        
    # 5. 공백 찾기
    inverted_gray = 255 - gray
    col_sums_gray = np.sum(inverted_gray, axis=0)
    
    kernel_size = 5
    smoothed = np.convolve(col_sums_gray, np.ones(kernel_size)/kernel_size, mode='valid')
    
    if len(smoothed) > 0:
        min_val_idx = np.argmin(smoothed)
        return min_x + min_val_idx + (kernel_size // 2)
        
    return min_x + np.argmin(col_sums_gray)

class SlicerCanvas(QWidget):
    point_added = Signal(int)
    point_removed = Signal(int)

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.scale_factor = 1.0
        self.cut_points = []
        self.setFixedSize(pixmap.size())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.hover_x = -1

    def set_cut_points(self, points):
        self.cut_points = sorted(list(set(points)))
        self.update()

    def perform_zoom(self, delta_y):
        if delta_y > 0:
            self.scale_factor *= 1.1
        else:
            self.scale_factor /= 1.1
        
        self.scale_factor = max(0.1, min(self.scale_factor, 5.0))
        
        new_size = self.pixmap.size() * self.scale_factor
        self.setFixedSize(new_size)
        self.update()

    def mouseMoveEvent(self, event):
        self.hover_x = int(event.position().x() / self.scale_factor)
        self.update()

    def mousePressEvent(self, event):
        sx = event.position().x()
        x = int(sx / self.scale_factor)
        x = max(0, min(x, self.pixmap.width()))
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.cut_points.append(x)
            self.cut_points.sort()
            self.point_added.emit(x)
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            closest = -1
            min_dist_screen = 20
            for p in self.cut_points:
                p_screen = p * self.scale_factor
                dist = abs(p_screen - sx)
                if dist < min_dist_screen:
                    min_dist_screen = dist
                    closest = p
            if closest != -1:
                self.cut_points.remove(closest)
                self.point_removed.emit(closest)
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.drawPixmap(0, 0, self.pixmap)
        
        pen = QPen(QColor(255, 0, 0), 2.0 / self.scale_factor)
        painter.setPen(pen)
        h = self.pixmap.height()
        for x in self.cut_points:
            painter.drawLine(x, 0, x, h)
            
        if 0 <= self.hover_x < self.pixmap.width():
            pen_hover = QPen(QColor(0, 120, 212, 150), 1.0 / self.scale_factor, Qt.PenStyle.DashLine)
            painter.setPen(pen_hover)
            painter.drawLine(self.hover_x, 0, self.hover_x, h)

class ScrollSlicerDialog(QDialog):
    def __init__(self, image, target_width, parent=None, initial_points=None):
        super().__init__(parent)
        self.setWindowTitle("스크롤 캡처 자르기 편집")
        self.resize(1200, 800)
        self.image = image
        self.target_width = target_width
        
        layout = QVBoxLayout(self)
        
        info_layout = QHBoxLayout()
        lbl_info = QLabel("✂️ 이미지를 클릭하여 자를 위치(빨간선)를 추가하세요. (우클릭: 삭제, Ctrl+휠: 확대/축소)")
        lbl_info.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        info_layout.addWidget(lbl_info)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.pixmap = cv2_to_qpixmap(image)
        self.canvas = SlicerCanvas(self.pixmap)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll)
        
        self.scroll.installEventFilter(self)
        self.scroll.viewport().installEventFilter(self)

        btn_layout = QHBoxLayout()
        
        btn_auto = QPushButton("자동 감지 실행")
        btn_auto.setMinimumHeight(40)
        btn_auto.clicked.connect(self.run_auto_detect)
        
        btn_clear = QPushButton("모두 지우기")
        btn_clear.setMinimumHeight(40)
        btn_clear.clicked.connect(self.clear_all_points)
        
        self.lbl_count = QLabel("예상 조각 수: -개")
        self.lbl_count.setStyleSheet("font-size: 13px; font-weight: bold; color: #0078d4; margin-left: 15px;")
        
        btn_cancel = QPushButton("취소")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("자르기 및 저장")
        btn_save.setMinimumHeight(40)
        btn_save.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_auto)
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(self.lbl_count)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
        self.canvas.point_added.connect(lambda _: self.update_slice_count())
        self.canvas.point_removed.connect(lambda _: self.update_slice_count())
        
        if initial_points:
            QTimer.singleShot(100, lambda: self.ask_restore(initial_points))
        else:
            QTimer.singleShot(100, self.run_auto_detect)
            
        apply_window_theme(self, parent)

    def ask_restore(self, points):
        reply = show_message(
            self, "이전 편집 복구", 
            "이전에 편집했던 자르기 위치를 불러오시겠습니까?",
            QMessageBox.Icon.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.set_cut_points(points)
            self.update_slice_count()
        else:
            self.clear_all_points()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.canvas.perform_zoom(event.angleDelta().y())
                return True
            else:
                self.scroll.horizontalScrollBar().setValue(
                    self.scroll.horizontalScrollBar().value() - event.angleDelta().y()
                )
                return True
        return super().eventFilter(source, event)

    def clear_all_points(self):
        self.canvas.set_cut_points([])
        self.update_slice_count()

    def run_auto_detect(self):
        points = []
        total_width = self.image.shape[1]
        current_x = 0
        
        while current_x < total_width:
            if total_width - current_x <= self.target_width * 1.2:
                break
            
            search_min = int(self.target_width * 0.8)
            search_max = int(self.target_width * 1.2)
            
            cut_x = calculate_best_cut_point(self.image, current_x + search_min, current_x + search_max)
            
            if cut_x:
                points.append(cut_x)
                current_x = cut_x
            else:
                current_x += self.target_width
                points.append(current_x)
        
        self.canvas.set_cut_points(points)
        self.update_slice_count()

    def update_slice_count(self):
        points = sorted(list(set(self.canvas.cut_points)))
        count = 0
        start_x = 0
        h, w = self.image.shape[:2]
        
        calc_points = points.copy()
        if not calc_points or calc_points[-1] < w:
            calc_points.append(w)
            
        for x in calc_points:
            if x > start_x:
                x = min(x, w)
                if x - start_x > 50:
                    count += 1
                start_x = x
        
        self.lbl_count.setText(f"예상 조각 수: {count}개")

    def get_sliced_images(self):
        points = sorted(list(set(self.canvas.cut_points)))
        images = []
        start_x = 0
        h, w = self.image.shape[:2]
        
        if not points or points[-1] < w:
            points.append(w)
            
        for x in points:
            if x > start_x:
                x = min(x, w)
                img_chunk = self.image[:, start_x:x]
                if img_chunk.shape[1] > 50:
                    images.append(img_chunk)
                start_x = x
        return images

class DraggableScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.last_pos = QPoint()
        self.scale_factor = 1.0
        self.original_pixmap = None
        self.label = None

    def set_image(self, image_path, use_basic=False, invert=False, image_data=None, use_high=False, adaptive=False):
        if image_data is not None:
            img = image_data
            if adaptive:
                img = apply_natural_grayscale(img)

            if invert:
                img = cv2.bitwise_not(img)
            self.original_pixmap = cv2_to_qpixmap(img)
        elif use_basic or use_high or invert or adaptive:
            img = imread_unicode(image_path)
            if img is not None:
                if use_basic or use_high:
                    img = enhance_score_image(img, use_basic=use_basic, use_high=use_high)
                
                if adaptive:
                    img = apply_natural_grayscale(img)

                if invert:
                    img = cv2.bitwise_not(img)
                self.original_pixmap = cv2_to_qpixmap(img)
            else:
                self.original_pixmap = QPixmap()
        else:
            self.original_pixmap = QPixmap(image_path)
            
        if self.original_pixmap.isNull():
            return
        
        self.label = QLabel()
        self.label.setPixmap(self.original_pixmap)
        self.label.resize(self.original_pixmap.size())
        self.setWidget(self.label)
        self.scale_factor = 1.0

    def wheelEvent(self, event):
        if not self.original_pixmap:
            super().wheelEvent(event)
            return

        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.1
        else:
            self.scale_factor /= 1.1
        
        self.scale_factor = max(0.1, min(self.scale_factor, 5.0))
        
        new_w = int(self.original_pixmap.width() * self.scale_factor)
        new_h = int(self.original_pixmap.height() * self.scale_factor)
        
        self.label.setPixmap(self.original_pixmap.scaled(
            new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))
        self.label.resize(new_w, new_h)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position().toPoint() - self.last_pos
            self.last_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

class ImageDetailDialog(QDialog):
    def __init__(self, image_path, use_basic=False, invert=False, parent=None, image_data=None, use_high=False, adaptive=False):
        super().__init__(parent)
        self.setWindowTitle("이미지 상세 보기 (드래그:이동, 휠:확대/축소)")
        self.resize(1000, 800)
        
        layout = QVBoxLayout(self)
        
        scroll = DraggableScrollArea()
        scroll.set_image(image_path, use_basic, invert, image_data=image_data, use_high=use_high, adaptive=adaptive)
        layout.addWidget(scroll)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        btn_close.setMinimumHeight(40)
        layout.addWidget(btn_close)
        
        apply_window_theme(self, parent)

def create_colored_pixmap(path, color):
    """SVG 파일의 색상을 변경하여 Pixmap으로 반환"""
    if not os.path.exists(path):
        return QPixmap()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_content = svg_content.replace("currentColor", color)
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(svg_content.encode('utf-8')))
        return pixmap
    except:
        return QPixmap()

class ListItemDelegate(QStyledItemDelegate):
    """리스트 햄버거 아이콘 델리게이트"""
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        
        painter.save()
        
        if opt.state & QStyle.StateFlag.State_Selected:
            color = opt.palette.color(QPalette.ColorRole.HighlightedText)
        else:
            color = opt.palette.color(QPalette.ColorRole.Text)
        painter.setPen(color)
        
        rect = opt.rect
        text_rect = rect.adjusted(8, 0, -30, 0)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, 
                        opt.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()))
        
        x = rect.right() - 22
        cy = rect.center().y()
        
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        
        painter.drawLine(x, cy - 4, x + 12, cy - 4)
        painter.drawLine(x, cy, x + 12, cy)
        painter.drawLine(x, cy + 4, x + 12, cy + 4)
            
        painter.restore()

class ImageEnhancerWorker(QObject):
    progress = Signal(int)
    finished = Signal(dict)
    
    def __init__(self, files, use_basic=False, use_high=False, cache_dir=None):
        super().__init__()
        self.files = files
        self.use_basic = use_basic
        self.use_high = use_high
        self.cache_dir = cache_dir
        self.is_running = True

    def run(self):
        results = {}
        cache_type = 'hq' if self.use_high else 'basic'
        try:
            for i, path in enumerate(self.files):
                if not self.is_running: break
                try:
                    img = imread_unicode(path)
                    if img is not None:
                        res = enhance_score_image(img, use_basic=self.use_basic, use_high=self.use_high)
                        if self.cache_dir:
                            base_name = os.path.basename(path)
                            name, ext = os.path.splitext(base_name)
                            cached_filename = f"{name}_{cache_type}{ext}"
                            cached_path = os.path.join(self.cache_dir, cached_filename)
                            if imwrite_unicode(cached_path, res):
                                results[path] = cached_path
                        else:
                            results[path] = res
                except Exception:
                    pass
                self.progress.emit(i + 1)
        except Exception:
            pass
        finally:
            self.finished.emit(results)

    def stop(self):
        self.is_running = False

class ScoreEditorWidget(QWidget):
    """PDF 생성 전 메타데이터 입력 및 미리보기 위젯"""
    save_requested = Signal(dict)
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_files = []
        self.hq_cache = {}
        self.basic_cache = {}
        self.font_bold = "Arial"
        self.font_regular = "Arial"
        self.invert_mode = "both"
        
        # 캐시 디렉토리 설정
        self.cache_dir = os.path.join(OUTPUT_FOLDER, "cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.refresh_preview)
        
        # 메인 레이아웃 (세로 배치)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 5, 20, 10)
        main_layout.setSpacing(10)

        # 설정 접기/펴기 버튼
        self.btn_toggle_settings = QPushButton("▼ 설정 접기")
        self.btn_toggle_settings.setCheckable(True)
        self.btn_toggle_settings.setChecked(True)
        self.btn_toggle_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_settings.setStyleSheet("""
            QPushButton {
                text-align: left;
                background-color: transparent;
                border: none;
                font-weight: bold;
                color: #0078d4;
                padding: 5px;
            }
            QPushButton:hover { background-color: rgba(0, 120, 212, 0.1); border-radius: 4px; }
        """)
        self.btn_toggle_settings.toggled.connect(self.toggle_settings_visibility)
        main_layout.addWidget(self.btn_toggle_settings)

        # --- 상단 설정 영역 (가로 배치) ---
        self.settings_container = QWidget()
        settings_layout = QHBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(20)

        # 1. 메타데이터 입력
        info_group = QGroupBox("기본 정보")
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(10)
        
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("노래 제목")
        self.title_edit.setMinimumHeight(30)
        
        self.composer_edit = QLineEdit()
        self.composer_edit.setPlaceholderText("아티스트")
        self.composer_edit.setMinimumHeight(30)

        self.bpm_edit = QLineEdit()
        self.bpm_edit.setPlaceholderText("BPM (예: 120)")
        self.bpm_edit.setMinimumHeight(30)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("URL (QR코드, 예: 유튜브 링크)")
        self.url_edit.setMinimumHeight(30)
        
        self.title_edit.textChanged.connect(self.trigger_refresh)
        self.composer_edit.textChanged.connect(self.trigger_refresh)
        self.bpm_edit.textChanged.connect(self.trigger_refresh)
        self.url_edit.textChanged.connect(self.trigger_refresh)
        
        form_layout.addRow("제목:", self.title_edit)
        form_layout.addRow("아티스트:", self.composer_edit)
        form_layout.addRow("BPM:", self.bpm_edit)
        form_layout.addRow("URL (QR):", self.url_edit)
        info_group.setLayout(form_layout)
        settings_layout.addWidget(info_group)
        
        # 2. PDF 설정
        settings_group = QGroupBox("레이아웃 설정")
        settings_form = QFormLayout()
        settings_form.setSpacing(10)
        
        self.margin_edit = QLineEdit(DEFAULT_MARGIN)
        self.margin_edit.setValidator(QIntValidator(0, 9999, self))
        self.margin_edit.editingFinished.connect(self.validate_margin)
        self.margin_edit.setMinimumHeight(30)
        self.spacing_edit = QLineEdit(DEFAULT_SPACING)
        self.spacing_edit.setValidator(QIntValidator(0, 9999, self))
        self.spacing_edit.editingFinished.connect(self.validate_spacing)
        self.spacing_edit.setMinimumHeight(30)
        
        self.page_num_pos = QComboBox()
        self.page_num_pos.addItems(["하단 중앙", "하단 우측", "상단 우측", "없음"])
        self.page_num_pos.setMinimumHeight(30)
        
        self.chk_enhance = QCheckBox("선명하게 (기본)")
        self.chk_enhance.setChecked(False)
        self.chk_enhance.toggled.connect(self.on_enhance_toggled)
        
        self.chk_high_quality = QCheckBox("초고화질 변환 (느림)")
        self.chk_high_quality.setChecked(False)
        self.chk_high_quality.setEnabled(True)
        self.chk_high_quality.toggled.connect(self.on_high_quality_toggled)

        vbox_enhance = QVBoxLayout()
        vbox_enhance.setSpacing(5)
        vbox_enhance.addWidget(self.chk_enhance)
        vbox_enhance.addWidget(self.chk_high_quality)

        self.chk_invert = QCheckBox("다크모드 (색상 반전)")
        self.chk_invert.setChecked(False)
        self.chk_invert.stateChanged.connect(self.on_invert_state_changed)
        
        self.chk_adaptive = QCheckBox("자연스러운 흑백 (스캔 효과)")
        self.chk_adaptive.setChecked(False)
        self.chk_adaptive.stateChanged.connect(self.refresh_preview)

        vbox_filter = QVBoxLayout()
        vbox_filter.setSpacing(5)
        vbox_filter.addWidget(self.chk_invert)
        vbox_filter.addWidget(self.chk_adaptive)

        chk_layout = QHBoxLayout()
        chk_layout.addLayout(vbox_enhance)
        chk_layout.addLayout(vbox_filter)
        
        settings_form.addRow("여백 (px):", self.margin_edit)
        settings_form.addRow("간격 (px):", self.spacing_edit)
        settings_form.addRow("페이지 번호:", self.page_num_pos)
        settings_form.addRow("옵션:", chk_layout)
        settings_group.setLayout(settings_form)
        settings_layout.addWidget(settings_group)
        
        self.margin_edit.textChanged.connect(self.trigger_refresh)
        self.spacing_edit.textChanged.connect(self.trigger_refresh)
        self.page_num_pos.currentIndexChanged.connect(self.refresh_preview)

        main_layout.addWidget(self.settings_container)

        # --- 중앙 미리보기 영역 ---
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_frame.setStyleSheet("background-color: #525659; border: 1px solid #444;")
        
        preview_layout_inner = QVBoxLayout(preview_frame)
        preview_layout_inner.setContentsMargins(0, 0, 0, 0)
        preview_layout_inner.setSpacing(0)

        # 툴바
        preview_toolbar = QFrame()
        preview_toolbar.setStyleSheet("background-color: #333333; border-bottom: 1px solid #222;")
        preview_toolbar.setFixedHeight(40)
        tb_layout = QHBoxLayout(preview_toolbar)
        tb_layout.setContentsMargins(15, 0, 15, 0)
        
        lbl_preview_title = QLabel("미리보기")
        lbl_preview_title.setStyleSheet("color: #f0f0f0; font-weight: bold; font-size: 13px;")
        tb_layout.addWidget(lbl_preview_title)
        tb_layout.addStretch()
        lbl_guide = QLabel("이미지를 클릭하면 크게 볼 수 있습니다")
        lbl_guide.setStyleSheet("color: #aaa; font-size: 11px;")
        tb_layout.addWidget(lbl_guide)
        
        preview_layout_inner.addWidget(preview_toolbar)

        # 스크롤 영역
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: #525659; }")
        
        self.preview_content = QWidget()
        self.preview_content.setStyleSheet("background-color: #525659;")
        self.preview_layout = QVBoxLayout(self.preview_content)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.preview_layout.setSpacing(30)
        self.preview_layout.setContentsMargins(40, 40, 40, 40)
        
        self.scroll.setWidget(self.preview_content)
        preview_layout_inner.addWidget(self.scroll)
        
        main_layout.addWidget(preview_frame)

        # --- 하단 버튼 ---
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton("뒤로 가기")
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        
        self.btn_save = QPushButton("저장하기")
        self.btn_save.setObjectName("captureButton")
        self.btn_save.setMinimumHeight(38)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(lambda: self.save_requested.emit({
            'title': self.title_edit.text(),
            'composer': self.composer_edit.text(),
            'bpm': self.bpm_edit.text(),
            'url': self.url_edit.text(),
            'margin': self.margin_edit.text(),
            'spacing': self.spacing_edit.text(),
            'page_num_pos': self.page_num_pos.currentText(),
            'enhance': self.chk_enhance.isChecked(),
            'high_quality': self.chk_high_quality.isChecked(),
            'invert': self.chk_invert.isChecked(),
            'invert_mode': getattr(self, 'invert_mode', 'both'),
            'adaptive': self.chk_adaptive.isChecked()
        }))
        
        btn_layout.addWidget(self.btn_cancel, 1)
        btn_layout.addWidget(self.btn_save, 1)
        
        main_layout.addLayout(btn_layout)

    def on_invert_state_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            dialog = QDialog(self)
            dialog.setWindowTitle("다크모드 옵션")
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            lbl = QLabel("다크모드 적용 범위를 선택하세요:")
            lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
            layout.addWidget(lbl)
            
            btn_layout = QVBoxLayout()
            btn_layout.setSpacing(10)
            
            btn_score = QPushButton("악보만 반전 (흰 배경)")
            btn_score.setMinimumHeight(40)
            btn_score.setCursor(Qt.CursorShape.PointingHandCursor)
            
            btn_bg = QPushButton("배경만 반전 (검은 배경)")
            btn_bg.setMinimumHeight(40)
            btn_bg.setCursor(Qt.CursorShape.PointingHandCursor)
            
            btn_both = QPushButton("모두 반전 (악보 + 배경)")
            btn_both.setMinimumHeight(40)
            btn_both.setCursor(Qt.CursorShape.PointingHandCursor)
            
            btn_layout.addWidget(btn_score)
            btn_layout.addWidget(btn_bg)
            btn_layout.addWidget(btn_both)
            layout.addLayout(btn_layout)
            
            # 임시 변수 초기화 (기본값 both)
            self.temp_invert_mode = "both"
            
            # 람다 대신 내부 함수 사용 (가독성 유지)
            def select_score(): 
                self.temp_invert_mode = "score" 
                dialog.accept()
                
            def select_bg(): 
                self.temp_invert_mode = "bg" 
                dialog.accept()
                
            def select_both(): 
                self.temp_invert_mode = "both" 
                dialog.accept()
            
            btn_score.clicked.connect(select_score)
            btn_bg.clicked.connect(select_bg)
            btn_both.clicked.connect(select_both)
            
            # 테마 적용 함수가 있다면 호출
            apply_window_theme(dialog, self)
            
            # 다이얼로그 실행 및 결과 처리
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.invert_mode = self.temp_invert_mode
                self.refresh_preview()
            else:
                # 취소하거나 닫았을 경우 체크박스 해제 (QTimer를 사용하여 이벤트 루프 정리 후 실행)
                QTimer.singleShot(0, lambda: self.chk_invert.setChecked(False))
        
        # 체크박스가 '해제' 되었을 때
        else:
            self.invert_mode = None
            self.refresh_preview()

    def toggle_settings_visibility(self, checked):
        self.settings_container.setVisible(checked)
        self.btn_toggle_settings.setText("▼ 설정 접기" if checked else "▶ 설정 펼치기")

    def validate_margin(self):
        try:
            text = self.margin_edit.text()
            val = int(text) if text else -1
            if not (0 <= val <= 200):
                raise ValueError
        except ValueError:
            show_message(self, "입력 오류", "여백은 0 ~ 200px 사이여야 합니다.\n기본값(60)으로 초기화됩니다.", QMessageBox.Icon.Warning)
            self.margin_edit.setText(DEFAULT_MARGIN)

    def validate_spacing(self):
        try:
            text = self.spacing_edit.text()
            val = int(text) if text else -1
            if not (0 <= val <= 200):
                raise ValueError
        except ValueError:
            show_message(self, "입력 오류", "간격은 0 ~ 200px 사이여야 합니다.\n기본값(40)으로 초기화됩니다.", QMessageBox.Icon.Warning)
            self.spacing_edit.setText(DEFAULT_SPACING)

    def set_font_families(self, bold_family, regular_family):
        self.font_bold = bold_family
        self.font_regular = regular_family

    def on_enhance_toggled(self, checked):
        if checked and self.chk_high_quality.isChecked():
            self.chk_high_quality.blockSignals(True)
            self.chk_high_quality.setChecked(False)
            self.chk_high_quality.blockSignals(False)
        self.refresh_preview()

    def on_high_quality_toggled(self, checked):
        if checked and self.chk_enhance.isChecked():
            self.chk_enhance.blockSignals(True)
            self.chk_enhance.setChecked(False)
            self.chk_enhance.blockSignals(False)
        self.refresh_preview()

    def clear_image_cache(self):
        self.hq_cache = {}
        self.basic_cache = {}
        if os.path.exists(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir)
            except: pass

    def _save_to_cache(self, img, original_path, cache_type):
        if img is None: return None
        base_name = os.path.basename(original_path)
        name, ext = os.path.splitext(base_name)
        cached_filename = f"{name}_{cache_type}{ext}"
        cached_path = os.path.join(self.cache_dir, cached_filename)
        if imwrite_unicode(cached_path, img):
            return cached_path
        return None

    def reset_fields(self):
        self.title_edit.clear()
        self.composer_edit.clear()
        self.bpm_edit.clear()
        self.url_edit.clear()
        self.margin_edit.setText(DEFAULT_MARGIN)
        self.spacing_edit.setText(DEFAULT_SPACING)
        self.page_num_pos.setCurrentIndex(0)
        self.chk_enhance.setChecked(False)
        self.chk_invert.setChecked(False)
        self.invert_mode = "both"
        self.chk_adaptive.setChecked(False)
        self.current_files = []
        self.clear_image_cache()
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_large_image(self, path):
        if os.path.exists(path):
            do_invert = self.chk_invert.isChecked()
            invert_mode = getattr(self, 'invert_mode', 'both')
            invert_score = do_invert and (invert_mode in ["score", "both"])
            use_basic = self.chk_enhance.isChecked()
            use_high = self.chk_high_quality.isChecked()
            adaptive = self.chk_adaptive.isChecked()
            
            cached_path = None
            if use_high and path in self.hq_cache:
                cached_path = self.hq_cache[path]
            elif use_basic and path in self.basic_cache:
                cached_path = self.basic_cache[path]
            
            if cached_path:
                dlg = ImageDetailDialog(cached_path, use_basic=False, invert=invert_score, parent=self, image_data=None, adaptive=adaptive)
            else:
                dlg = ImageDetailDialog(path, use_basic=use_basic, invert=invert_score, parent=self, use_high=use_high, adaptive=adaptive)
            dlg.exec()

    def trigger_refresh(self):
        self.debounce_timer.start(500)

    def refresh_preview(self):
        target_cache = None
        if self.chk_high_quality.isChecked():
            target_cache = self.hq_cache
        elif self.chk_enhance.isChecked():
            target_cache = self.basic_cache

        if target_cache is not None and self.current_files:
            uncached = [f for f in self.current_files if f not in target_cache]
            if uncached:
                self.run_enhancement_worker(uncached)
                return
        self.render_preview_content()

    def run_enhancement_worker(self, files):
        self.progress_dlg = QProgressDialog("고화질 변환 처리 중... (시간이 걸릴 수 있습니다)", "취소", 0, len(files), self)
        self.progress_dlg.setWindowTitle("고화질 변환")
        self.progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dlg.setMinimumDuration(0)
        self.progress_dlg.setAutoClose(False)
        self.progress_dlg.setValue(0)
        
        self.worker_thread = QThread()
        self.worker = ImageEnhancerWorker(files, use_basic=self.chk_enhance.isChecked(), use_high=self.chk_high_quality.isChecked(), cache_dir=self.cache_dir)
        self.worker.moveToThread(self.worker_thread)
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress_dlg.setValue)
        self.worker.finished.connect(self.on_enhancement_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        self.progress_dlg.canceled.connect(self.cancel_enhancement)
        self.worker_thread.start()

    def cancel_enhancement(self):
        if hasattr(self, 'worker') and self.worker:
            self.worker.stop()
        
        thread = getattr(self, 'worker_thread', None)

        if thread and thread.isRunning():
            # 종료 대기 알림창 표시
            wait_dlg = QProgressDialog("작업을 취소하고 있습니다...\n잠시만 기다려주세요.", "", 0, 0, self)
            wait_dlg.setWindowTitle("취소 중")
            wait_dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            wait_dlg.setCancelButton(None)
            wait_dlg.setWindowFlags(wait_dlg.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
            wait_dlg.setMinimumDuration(0)
            wait_dlg.setRange(0, 0)
            apply_window_theme(wait_dlg, self)
            wait_dlg.show()
            QApplication.processEvents()

            thread.quit()
            # 현재 진행 중인 이미지 처리가 끝날 때까지 대기
            while not thread.wait(50):
                QApplication.processEvents()
            wait_dlg.close()

        self.chk_enhance.blockSignals(True)
        self.chk_enhance.setChecked(False)
        self.chk_enhance.blockSignals(False)
        self.chk_high_quality.blockSignals(True)
        self.chk_high_quality.setChecked(False)
        self.chk_high_quality.blockSignals(False)
        self.render_preview_content()

    def on_enhancement_finished(self, results):
        if self.chk_high_quality.isChecked():
            self.hq_cache.update(results)
        elif self.chk_enhance.isChecked():
            self.basic_cache.update(results)
        try:
            self.progress_dlg.canceled.disconnect(self.cancel_enhancement)
        except Exception:
            pass
        self.progress_dlg.close()
        self.render_preview_content()

    def load_preview(self, file_paths):
        self.current_files = file_paths
        
        # 목록에서 제거된 파일은 캐시에서도 삭제
        current_set = set(file_paths)
        self.hq_cache = {k: v for k, v in self.hq_cache.items() if k in current_set}
        self.basic_cache = {k: v for k, v in self.basic_cache.items() if k in current_set}

        self.refresh_preview()

    def render_preview_content(self):
        file_paths = self.current_files
        
        progress = QProgressDialog("미리보기 갱신 중...", None, 0, len(file_paths), self)
        progress.setWindowTitle("처리 중")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        apply_window_theme(progress, self)
        if file_paths:
            progress.show()
            QApplication.processEvents()

        # 기존 위젯 제거
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not file_paths:
            progress.close()
            return

        try:
            # 설정값 파싱
            try:
                margin = int(self.margin_edit.text())
                spacing = int(self.spacing_edit.text())
            except ValueError:
                margin = int(DEFAULT_MARGIN)
                spacing = int(DEFAULT_SPACING)
            page_num_pos_str = self.page_num_pos.currentText()

            # 다크모드 설정
            is_invert = self.chk_invert.isChecked()
            invert_mode = getattr(self, 'invert_mode', 'both')
            
            invert_bg = is_invert and (invert_mode in ["bg", "both"])
            invert_score = is_invert and (invert_mode in ["score", "both"])
            
            is_adaptive = self.chk_adaptive.isChecked()
            bg_color_hex = "#000000" if invert_bg else "#ffffff"
            text_color_hex = "#ffffff" if invert_bg else "#000000"

            # 화질 개선 시 여백/간격도 2배로 조정하여 비율 유지
            enhance_ratio = 1
            if self.chk_enhance.isChecked() or self.chk_high_quality.isChecked():
                margin *= 2
                spacing *= 2
                enhance_ratio = 2

            # 첫 번째 이미지로 기준 너비 설정 (PDF 생성 로직과 동일하게)
            # 화질 개선 여부에 따라 기준 너비가 달라짐
            first_img_cv = imread_unicode(file_paths[0])
            if first_img_cv is None: return
            
            if self.chk_enhance.isChecked() or self.chk_high_quality.isChecked():
                # 업스케일링 된 크기 예측 (2배)
                base_width = first_img_cv.shape[1] * 2
            else:
                base_width = first_img_cv.shape[1]
                
            # A4 비율 (210x297mm) -> 높이 계산
            page_height = int(base_width * (297 / 210))
            
            # 화면 표시용 스케일 (미리보기 너비 600px 기준)
            PREVIEW_WIDTH = 600
            scale = PREVIEW_WIDTH / base_width
            
            preview_height = int(page_height * scale)
            
            # 폰트 크기 계산 (PDF 생성 로직과 비율 맞춤)
            title_font_size = max(10, int((base_width / 30) * scale))
            comp_font_size = max(8, int((base_width / 60) * scale))
            
            current_y = margin
            
            title = self.title_edit.text().strip()
            composer = self.composer_edit.text().strip()
            bpm = self.bpm_edit.text().strip()
            url = self.url_edit.text().strip()
            
            current_page_num = 1
            
            # 페이지 컨테이너 생성 함수
            def create_page_widget(page_num):
                widget = QWidget()
                widget.setFixedSize(PREVIEW_WIDTH, preview_height)
                # 검정색 테두리 스타일
                widget.setStyleSheet(f"""
                    background-color: {bg_color_hex}; 
                    border: 1px solid {text_color_hex};
                    color: {text_color_hex};
                """)
                
                # 상단 식별자
                lbl = QLabel(f"Page {page_num}", widget)
                lbl.setStyleSheet("background-color: transparent; color: #999; font-size: 10px; padding: 2px; border: none;")
                lbl.move(5, 5)
                lbl.show()
                
                return widget

            current_page_widget = create_page_widget(current_page_num)
            self.preview_layout.addWidget(current_page_widget)

            # 헤더 (제목/작곡가) 처리 - 절대 좌표 사용
            header_offset = 0
            qr_height_val = 0

            # QR 코드 생성 및 배치
            if url and qrcode:
                try:
                    qr_fill = "white" if invert_bg else "black"
                    qr_back = "black" if invert_bg else "white"
                    qr = qrcode.QRCode(box_size=10, border=2)
                    qr.add_data(url)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color=qr_fill, back_color=qr_back)
                    
                    # QPixmap 변환
                    data = qr_img.convert("RGBA").tobytes("raw", "RGBA")
                    qim = QImage(data, qr_img.size[0], qr_img.size[1], QImage.Format_RGBA8888)
                    qr_pix = QPixmap.fromImage(qim)
                    
                    # 크기 조정 (페이지 폭의 12%)
                    qr_size = int(base_width * 0.12)
                    qr_pix = qr_pix.scaled(qr_size, qr_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    
                    lbl_qr = QLabel(current_page_widget)
                    lbl_qr.setPixmap(qr_pix)
                    lbl_qr.setScaledContents(True)
                    
                    # 위치: 좌측 상단 (여백 위치)
                    display_qr_size = int(qr_size * scale)
                    lbl_qr.setFixedSize(display_qr_size, display_qr_size)
                    lbl_qr.move(int(margin * scale), int(margin * scale))
                    lbl_qr.show()
                    
                    qr_height_val = qr_size
                except Exception as e:
                    show_message(self, "QR 코드 오류", f"QR 코드 생성 중 오류가 발생했습니다:\n{e}", QMessageBox.Icon.Warning)

            if title or composer or bpm:
                if title:
                    lbl_title = QLabel(title, current_page_widget)
                    lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    font = QFont(self.font_bold, int(title_font_size/1.3), QFont.Weight.Bold)
                    lbl_title.setFont(font)
                    lbl_title.adjustSize()
                    
                    t_w = lbl_title.width()
                    t_h = lbl_title.height()
                    
                    x_pos = int((PREVIEW_WIDTH - t_w) / 2)
                    y_pos = int(current_y * scale)
                    
                    lbl_title.move(x_pos, y_pos)
                    lbl_title.show()
                    
                    header_offset += (t_h / scale) + (20 * enhance_ratio)

                if composer:
                    lbl_comp = QLabel(composer, current_page_widget)
                    lbl_comp.setAlignment(Qt.AlignmentFlag.AlignRight)
                    font = QFont(self.font_regular, int(comp_font_size/1.3))
                    lbl_comp.setFont(font)
                    lbl_comp.adjustSize()
                    
                    c_w = lbl_comp.width()
                    c_h = lbl_comp.height()
                    
                    x_pos = int((base_width - margin) * scale) - c_w
                    y_pos = int((current_y + header_offset) * scale)
                    
                    lbl_comp.move(x_pos, y_pos)
                    lbl_comp.show()
                    
                    header_offset += (c_h / scale) + (20 * enhance_ratio)

                if bpm:
                    lbl_bpm = QLabel(f"BPM: {bpm}", current_page_widget)
                    lbl_bpm.setAlignment(Qt.AlignmentFlag.AlignLeft)
                    font = QFont(self.font_bold, int(comp_font_size/1.3), QFont.Weight.Bold)
                    lbl_bpm.setFont(font)
                    lbl_bpm.adjustSize()
                    
                    b_w = lbl_bpm.width()
                    b_h = lbl_bpm.height()
                    
                    x_pos = int(margin * scale)
                    # QR 코드가 있고 높이가 겹치면 아래로 내리기 (좌측 정렬 유지)
                    if qr_height_val > 0 and header_offset < qr_height_val:
                        header_offset = qr_height_val + (10 * enhance_ratio)

                    y_pos = int((current_y + header_offset) * scale)
                    lbl_bpm.move(x_pos, y_pos)
                    lbl_bpm.show()
                    header_offset += (b_h / scale) + (10 * enhance_ratio)
                
            # 헤더 높이 결정 (텍스트와 QR 중 더 큰 것 기준)
            final_header_height = max(header_offset, qr_height_val)
            
            if final_header_height > 0:
                current_y += final_header_height + (40 * enhance_ratio)

            # 이미지 배치
            content_width_pdf = base_width - (margin * 2)
            if content_width_pdf < 1: content_width_pdf = 1
            
            display_content_width = int(content_width_pdf * scale)
            display_margin_left = int(margin * scale)

            for i, path in enumerate(file_paths):
                progress.setValue(i)
                QApplication.processEvents()

                if not os.path.exists(path):
                    continue
                
                img_cv = None
                if self.chk_high_quality.isChecked():
                    if path in self.hq_cache:
                        img_cv = imread_unicode(self.hq_cache[path])
                    else:
                        raw_img = imread_unicode(path)
                        if raw_img is not None:
                            img_cv = enhance_score_image(raw_img, use_basic=False, use_high=True)
                            cached_path = self._save_to_cache(img_cv, path, 'hq')
                            if cached_path:
                                self.hq_cache[path] = cached_path
                elif self.chk_enhance.isChecked():
                    if path in self.basic_cache:
                        img_cv = imread_unicode(self.basic_cache[path])
                    else:
                        raw_img = imread_unicode(path)
                        if raw_img is not None:
                            img_cv = enhance_score_image(raw_img, use_basic=True, use_high=False)
                            cached_path = self._save_to_cache(img_cv, path, 'basic')
                            if cached_path:
                                self.basic_cache[path] = cached_path
                
                if img_cv is None:
                    img_cv = imread_unicode(path)
                    
                if img_cv is None: continue
                
                if is_adaptive:
                    img_cv = apply_natural_grayscale(img_cv)

                if invert_score:
                    img_cv = cv2.bitwise_not(img_cv)
                
                pix = cv2_to_qpixmap(img_cv)
                
                img_w = pix.width()
                img_h = pix.height()
                
                if img_w != content_width_pdf:
                    new_h_pdf = int(img_h * (content_width_pdf / img_w))
                else:
                    new_h_pdf = img_h
                
                # 페이지 넘김 체크
                if current_y + new_h_pdf + margin > page_height:
                    current_page_num += 1
                    current_page_widget = create_page_widget(current_page_num)
                    self.preview_layout.addWidget(current_page_widget)
                    current_y = margin
                
                # 이미지 그리기
                display_h = int(new_h_pdf * scale)
                scaled_pix = pix.scaled(display_content_width, display_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                lbl_img = ClickableLabel(current_page_widget)
                lbl_img.setCursor(Qt.CursorShape.PointingHandCursor)
                lbl_img.setToolTip("클릭하여 크게 보기")
                lbl_img.clicked.connect(lambda p=path: self.show_large_image(p))
                lbl_img.setPixmap(scaled_pix)
                lbl_img.setFixedSize(display_content_width, display_h)
                lbl_img.move(display_margin_left, int(current_y * scale))
                lbl_img.show()
                
                current_y += new_h_pdf + spacing

            # 페이지 번호 추가
            if page_num_pos_str != "없음":
                total_pages = self.preview_layout.count()
                for i in range(total_pages):
                    page_widget = self.preview_layout.itemAt(i).widget()
                    if not page_widget: continue
                    
                    txt = f"{i+1} / {total_pages}"
                    lbl_num = QLabel(txt, page_widget)
                    font = QFont(self.font_regular, max(8, int((base_width/50)*scale/1.3)))
                    lbl_num.setFont(font)
                    lbl_num.adjustSize()
                    
                    nw = lbl_num.width()
                    nh = lbl_num.height()
                    
                    px_margin = int(margin * scale)
                    px_page_h = preview_height
                    
                    x_pos, y_pos = 0, 0
                    
                    if "하단" in page_num_pos_str:
                        y_pos = px_page_h - int(px_margin/2) - nh
                    elif "상단" in page_num_pos_str:
                        y_pos = int(px_margin/2)
                    
                    if "중앙" in page_num_pos_str:
                        x_pos = int((PREVIEW_WIDTH - nw) / 2)
                    elif "우측" in page_num_pos_str:
                        x_pos = PREVIEW_WIDTH - px_margin - nw
                        
                    lbl_num.move(x_pos, y_pos)
                    lbl_num.show()

        except Exception as e:
            show_message(self, "미리보기 오류", f"미리보기 생성 중 오류가 발생했습니다:\n{e}", QMessageBox.Icon.Warning)
        finally:
            progress.setValue(len(file_paths))
            progress.close()

class CaptureWorker(QObject):
    """캡처 및 이미지 처리를 담당하는 워커 스레드"""
    finished_processing = Signal()
    request_clean_capture = Signal()
    image_saved = Signal(str, object)  # filename, img_bgr
    scroll_updated = Signal(object)    # img_bgr
    status_updated = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.last_captured_gray = None
        self.last_hash = None
        self.scroll_chunks = []
        self.total_scroll_width = 0
        self.capture_counter = 0

    def reset_state(self):
        self.last_captured_gray = None
        self.last_hash = None
        self.scroll_chunks = []
        self.total_scroll_width = 0
        self.capture_counter = 0

    def _get_tail(self, width):
        """마지막 청크들로부터 지정된 너비만큼의 이미지를 구성하여 반환"""
        if not self.scroll_chunks:
            return None
        current_width = 0
        tail_chunks = []
        for chunk in reversed(self.scroll_chunks):
            tail_chunks.insert(0, chunk)
            current_width += chunk.shape[1]
            if current_width >= width:
                break
        if not tail_chunks:
            return None
        tail_img = np.hstack(tail_chunks)
        if tail_img.shape[1] > width:
            return tail_img[:, -width:]
        return tail_img

    def process_frame(self, img_bgr, mode_index, sensitivity):
        try:
            if mode_index == 0:  # 페이지 넘김 모드
                # 테두리 크롭 (비교 정확도 향상)
                h, w = img_bgr.shape[:2]
                border_crop = 5
                if w > 2 * border_crop and h > 2 * border_crop:
                    img_proc = img_bgr[border_crop:-border_crop, border_crop:-border_crop]
                else:
                    img_proc = img_bgr

                img_gray = cv2.cvtColor(img_proc, cv2.COLOR_BGR2GRAY)
                should_save = False

                if self.last_captured_gray is None:
                    should_save = True
                else:
                    if self.last_captured_gray.shape == img_gray.shape:
                        score = calculate_ssim(self.last_captured_gray, img_gray)
                        if score < sensitivity:
                            should_save = True
                    else:
                        should_save = True

                if should_save:
                    self.request_clean_capture.emit()
                    # 저장 완료될 때까지 finished_processing을 보내지 않음 (Main에서 save_clean 호출 대기)
                else:
                    self.finished_processing.emit()

            else:  # 스크롤 모드
                if not self.scroll_chunks:
                    self.scroll_chunks.append(img_bgr)
                    self.total_scroll_width = img_bgr.shape[1]
                    self.status_updated.emit("스크롤 캡처 시작 (버퍼링...)")
                    self.scroll_updated.emit(img_bgr)
                else:
                    # 템플릿 매칭
                    template_width = 200
                    tail_img = self._get_tail(template_width)
                    
                    if tail_img is not None and tail_img.shape[1] >= template_width and img_bgr.shape[1] >= template_width:
                        template = tail_img[:, -template_width:]
                        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

                        res = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)

                        if max_val > 0.7:
                            match_x = max_loc[0]
                            new_part_start = match_x + template_width
                            if new_part_start < img_bgr.shape[1]:
                                new_part = img_bgr[:, new_part_start:]
                                if new_part.shape[1] > 0:
                                    self.scroll_chunks.append(new_part)
                                    self.total_scroll_width += new_part.shape[1]
                                    self.status_updated.emit(f"이어붙이기 중... (전체 폭: {self.total_scroll_width}px)")
                                    self.scroll_updated.emit(new_part)
                
                self.finished_processing.emit()
        except Exception as e:
            self.error_occurred.emit(f"이미지 처리 오류: {e}")
            self.finished_processing.emit()

    def save_clean_image(self, img_bgr):
        try:
            # 해시 비교 (중복 저장 방지)
            pil_img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
            curr_hash = imagehash.phash(pil_img)

            if self.last_hash is None or (curr_hash - self.last_hash > 5):
                self.capture_counter += 1
                filename = os.path.join(OUTPUT_FOLDER, f"score_{self.capture_counter:03d}.png")
                imwrite_unicode(filename, img_bgr)
                
                # 다음 비교를 위해 크롭된 그레이스케일 저장
                h, w = img_bgr.shape[:2]
                border_crop = 5
                if w > 2 * border_crop and h > 2 * border_crop:
                    clean_proc = img_bgr[border_crop:-border_crop, border_crop:-border_crop]
                else:
                    clean_proc = img_bgr
                
                self.last_captured_gray = cv2.cvtColor(clean_proc, cv2.COLOR_BGR2GRAY)
                self.last_hash = curr_hash
                
                self.image_saved.emit(filename, img_bgr)
            
        except Exception as e:
            self.error_occurred.emit(f"저장 오류: {e}")
        finally:
            self.finished_processing.emit()

class UpdateChecker(QThread):
    update_available = Signal(str, str)

    def run(self):
        api_url = VERSION_INFO.get("repo_api_url")
        if not api_url:
            return

        try:
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', 'ScoreCapturePro')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    latest_version = data.get("tag_name", "").lstrip("v")
                    current_version = VERSION_INFO.get("version", "0.0.0")

                    if self.compare_versions(latest_version, current_version):
                        self.update_available.emit(latest_version, data.get("html_url", ""))
        except Exception:
            pass

    def compare_versions(self, v1, v2):
        def normalize(v):
            return [int(x) for x in re.sub(r'[^0-9.]', '', v).split(".") if x.isdigit()]
        try:
            return normalize(v1) > normalize(v2)
        except:
            return v1 > v2

class AboutDialog(QDialog):
    easter_egg_activated = Signal()

    def __init__(self, parent=None, is_secret_active=False):
        super().__init__(parent)
        self.setWindowTitle("정보")
        self.resize(300, 250)
        layout = QVBoxLayout(self)
        
        self.click_count = 0
        self.last_click_time = 0
        self.is_secret_active = is_secret_active
        
        # 로고 이미지
        self.logo_lbl = ClickableLabel()
        self.logo_lbl.clicked.connect(self.activate_easter_egg)
        self.logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo_lbl)
        
        # 제목 및 버전 정보
        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_lbl)
        
        ver = QLabel(f"Version {VERSION_INFO.get('version', '1.0.0')}")
        ver.setStyleSheet("color: #888; margin-bottom: 10px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)
        
        # 개발자 정보
        dev = QLabel(f"Developed by {VERSION_INFO.get('developer', '')}")
        dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dev)
        
        # 깃허브 저장소 링크
        github_url = VERSION_INFO.get('github', '')
        if github_url:
            link = QLabel(f'<a href="{github_url}" style="color: #0078d4; text-decoration: none;">GitHub Repository</a>')
            link.setOpenExternalLinks(True)
            link.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(link)
            
        layout.addStretch()
            
        btn_ok = QPushButton("확인")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        
        self.update_ui_state(is_secret_active)
        apply_window_theme(self, parent)

    def update_ui_state(self, is_secret):
        """상태에 따라 UI 업데이트 (일반 모드/이스터 에그)"""
        target_path = ICON_PNG_PATH
        title_text = APP_TITLE
        
        if is_secret:
            secret_path = EASTER_EGG_IMAGE_PATH
            if os.path.exists(secret_path):
                target_path = secret_path
            title_text = EASTER_EGG_TITLE
            self.setStyleSheet(EASTER_EGG_STYLE)
            set_window_theme(self, "dark")

        if os.path.exists(target_path):
            pm = QPixmap(target_path)
            self.logo_lbl.setPixmap(pm.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.setWindowIcon(QIcon(target_path))
        
        self.title_lbl.setText(title_text)

    def activate_easter_egg(self):
        import base64
        current_time = time.time()
        # 0.5초 이내에 연속 클릭하지 않으면 카운트 초기화
        if current_time - self.last_click_time > 0.5:
            self.click_count = 0
        self.last_click_time = current_time
        self.click_count += 1
        
        if self.click_count >= EASTER_EGG_TRIGGER_COUNT:
            self.click_count = 0
            self.is_secret_active = True
            self.easter_egg_activated.emit()
            self.update_ui_state(True)

def check_screen_recording_permission():
    """macOS 화면 녹화 권한 확인 및 요청"""
    if sys.platform != "darwin":
        return True
        
    try:
        import Quartz
        
        if hasattr(Quartz, 'CGPreflightScreenCaptureAccess'):
            if not Quartz.CGPreflightScreenCaptureAccess():
                if hasattr(Quartz, 'CGRequestScreenCaptureAccess'):
                    Quartz.CGRequestScreenCaptureAccess()
                
                msg = QMessageBox()
                msg.setWindowTitle("화면 녹화 권한 필요")
                msg.setText("화면을 캡처하려면 '화면 기록' 권한이 필요합니다.")
                msg.setInformativeText("시스템 설정에서 권한을 허용한 후 앱을 재시작해주세요.")
                msg.setIcon(QMessageBox.Icon.Warning)
                
                btn_settings = msg.addButton("설정 열기", QMessageBox.ButtonRole.ActionRole)
                btn_quit = msg.addButton("종료", QMessageBox.ButtonRole.RejectRole)
                btn_ignore = msg.addButton("무시하고 계속", QMessageBox.ButtonRole.AcceptRole)
                msg.setDefaultButton(btn_settings)
                
                msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                msg.exec()
                
                if msg.clickedButton() == btn_settings:
                    import subprocess
                    subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"])
                elif msg.clickedButton() == btn_ignore:
                    return True
                
                return False
        return True
    except Exception:
        return True

class MainWindow(QMainWindow):
    # 워커 스레드 통신용 시그널
    sig_process_frame = Signal(object, int, float)
    sig_save_clean = Signal(object)
    sig_reset_worker = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_WINDOW_TITLE)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1200, 700)
        self.capture_area_dict = None
        self.captured_files = []
        self.is_saved = True
        self.capture_counter = 0
        self.is_capturing = False  # 캡처 상태 추적
        self.area_indicator = None # 선택 영역 표시 위젯
        self.current_original_pixmap = None

        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self.perform_capture)
        self.current_theme = get_system_theme()  # 'light' 또는 'dark'
        self.last_system_theme = self.current_theme

        self.countdown_value = -1
        self.current_scroll_chunks = [] # UI 표시용 청크 리스트
        self.current_scroll_filename = None
        self.last_stitched_image = None
        self.last_cut_points = None
        self.is_worker_busy = False
        self.is_easter_egg_active = False
        self.is_first_capture = False

        self.font_bold_family = "Arial"
        self.font_regular_family = "Arial"
        self.load_fonts()

        self.setup_ui()
        self.apply_stylesheet()
        self.setup_worker()
        
        # 업데이트 확인 (GitHub Releases)
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.show_update_notification)
        self.update_checker.start()

        # 리스트 델리게이트 설정
        self.list_delegate = ListItemDelegate(self.list_widget)
        self.list_widget.setItemDelegate(self.list_delegate)
        
    def changeEvent(self, event):
        """시스템 테마 변경 이벤트 감지"""
        if event.type() == QEvent.ThemeChange:
            self.watch_system_theme()
        super().changeEvent(event)

    def watch_system_theme(self):
        """시스템 테마 변경을 확인하여 반영"""
        if self.is_easter_egg_active:
            return
        sys_theme = get_system_theme()
        if sys_theme != self.last_system_theme:
            self.last_system_theme = sys_theme
            self.current_theme = sys_theme
            self.update_theme_icon()
            self.update_mode_icon()
            self.apply_stylesheet()

    def update_ui_state(self):
        """UI 상태(미니모드/캡처중)에 따라 버튼 스타일과 텍스트 업데이트"""
        if self.is_easter_egg_active:
            is_mini = self.btn_mini.isChecked()
            is_capturing = self.is_capturing
            
            if is_mini:
                self.btn_capture.setFixedHeight(32)
                self.btn_capture.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self.btn_capture.setText("중지" if is_capturing else "2. 캡처")
                self.btn_capture.setStyleSheet("background-color: #000000; color: #00ff00; border: 1px solid #00ff00; font-weight: bold;")
                
                self.btn_select.setText("1. 영역")
                self.btn_select.setFixedHeight(32)
                self.btn_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self.btn_select.setStyleSheet("background-color: #000000; color: #00ff00; border: 1px solid #00ff00; font-weight: bold;")
            else:
                self.btn_capture.setMinimumHeight(42)
                self.btn_capture.setMaximumHeight(16777215)
                self.btn_capture.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
                self.btn_capture.setStyleSheet("")
                
                if is_capturing:
                    self.btn_capture.setText("■ 캡처 중지")
                else:
                    self.btn_capture.setText("2. 캡처 시작")
                
                self.btn_select.setText("1. 영역 선택")
                self.btn_select.setMinimumHeight(36)
                self.btn_select.setMaximumHeight(16777215)
                self.btn_select.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
                self.btn_select.setStyleSheet("")
            return

        is_mini = self.btn_mini.isChecked()
        is_capturing = self.is_capturing
        
        # 1. 캡처 버튼 설정
        if is_mini:
            self.btn_capture.setFixedHeight(32)
            self.btn_capture.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if is_capturing:
                self.btn_capture.setText("중지")
                self.btn_capture.setStyleSheet("font-size: 12px; font-weight: bold; border-radius: 4px; border: none; color: white; background-color: #dc3545;")
            else:
                self.btn_capture.setText("2. 캡처")
                self.btn_capture.setStyleSheet("font-size: 12px; font-weight: bold; border-radius: 4px; border: none; color: white; background-color: #28a745;")
        else:
            self.btn_capture.setMinimumHeight(42)
            self.btn_capture.setMaximumHeight(16777215)
            self.btn_capture.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.btn_capture.setStyleSheet("") # Reset to use global stylesheet
            
            if is_capturing:
                self.btn_capture.setText("■ 캡처 중지")
                self.btn_capture.setObjectName("captureButtonActive")
            else:
                self.btn_capture.setText("2. 캡처 시작")
                self.btn_capture.setObjectName("captureButton")
            
            self.apply_stylesheet()

        # 2. 선택 버튼 설정 (미니모드일 때만 스타일 변경)
        if is_mini:
            self.btn_select.setText("1. 영역")
            self.btn_select.setFixedHeight(32)
            self.btn_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.btn_select.setStyleSheet("font-size: 12px; font-weight: bold; border-radius: 4px; border: none; color: white; background-color: #6a5acd;")
        else:
            self.btn_select.setText("1. 영역 선택")
            self.btn_select.setMinimumHeight(36)
            self.btn_select.setMaximumHeight(16777215)
            self.btn_select.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.btn_select.setStyleSheet("")

    def setup_worker(self):
        """워커 스레드 초기화"""
        self.worker_thread = QThread()
        self.worker = CaptureWorker()
        self.worker.moveToThread(self.worker_thread)
        
        # 시그널 연결
        self.sig_process_frame.connect(self.worker.process_frame)
        self.sig_save_clean.connect(self.worker.save_clean_image)
        self.sig_reset_worker.connect(self.worker.reset_state)
        
        self.worker.finished_processing.connect(self.on_worker_finished)
        self.worker.request_clean_capture.connect(self.on_request_clean_capture)
        self.worker.image_saved.connect(self.on_image_saved)
        self.worker.scroll_updated.connect(self.on_scroll_updated)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.error_occurred.connect(self.show_error_message)
        
        self.worker_thread.start()

    def load_fonts(self):
        """폰트 파일 로드"""
        if os.path.exists(FONT_BOLD_PATH):
            id = QFontDatabase.addApplicationFont(FONT_BOLD_PATH)
            if id != -1:
                families = QFontDatabase.applicationFontFamilies(id)
                if families: self.font_bold_family = families[0]
        
        if os.path.exists(FONT_REGULAR_PATH):
            id = QFontDatabase.addApplicationFont(FONT_REGULAR_PATH)
            if id != -1:
                families = QFontDatabase.applicationFontFamilies(id)
                if families: self.font_regular_family = families[0]

    def apply_stylesheet(self):
        """현재 테마에 맞는 스타일시트 적용"""
        if self.is_easter_egg_active:
            return
        style = DARK_STYLE if self.current_theme == "dark" else LIGHT_STYLE
        
        if self.font_regular_family != "Arial":
            style = style.replace("'Segoe UI', 'Apple SD Gothic Neo', sans-serif", f"'{self.font_regular_family}', sans-serif")
        self.setStyleSheet(style)
        self.update_title_bar_color()

    def update_title_bar_color(self):
        """타이틀바 색상 변경"""
        if self.is_easter_egg_active:
            set_window_theme(self, "dark")
        else:
            set_window_theme(self, self.current_theme)

    def toggle_theme(self):
        """테마 토글 (라이트 ↔ 다크)"""
        if self.is_easter_egg_active:
            return
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        
        # 버튼 아이콘 변경
        self.update_theme_icon()
        self.update_mode_icon()
        
        # 스타일시트 적용
        self.apply_stylesheet()

    def update_theme_icon(self):
        """현재 테마에 맞는 SVG 아이콘 설정"""
        icon_path = SUN_ICON_PATH if self.current_theme == "light" else MOON_ICON_PATH
        self.btn_theme.setIcon(QIcon(icon_path))
        self.btn_theme.setIconSize(QSize(20, 20))

    def create_colored_icon(self, path, color):
        pixmap = create_colored_pixmap(path, color)
        return QIcon(pixmap)

    def update_mode_icon(self):
        """현재 모드에 맞는 SVG 아이콘 설정"""
        is_mini = self.btn_mini.isChecked()
        icon_path = EXPAND_ICON_PATH if is_mini else COMPACT_ICON_PATH
        tooltip = "일반 모드로 전환" if is_mini else "미니 모드로 전환"
        
        # 테마에 따른 색상 설정
        if self.is_easter_egg_active:
            color = "#00ff00"
        else:
            color = "#333333" if self.current_theme == "light" else "#e0e0e0"
        self.btn_mini.setIcon(self.create_colored_icon(icon_path, color))
        self.btn_mini.setIconSize(QSize(20, 20))
        self.btn_mini.setToolTip(tooltip)

    def toggle_mini_mode_with_icon(self, checked):
        """아이콘 업데이트를 포함한 미니모드 토글"""
        self.update_mode_icon()
        self.toggle_mini_mode(checked)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- 왼쪽 패널 ---
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setMaximumWidth(320)
        left_panel.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        
        # 헤더
        header_widget = QWidget()
        header_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.header_layout = QHBoxLayout(header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(4)

        # 로고 아이콘 추가
        logo_path = ICON_PNG_PATH if os.path.exists(ICON_PNG_PATH) else ICON_PATH
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setObjectName("logoLabel")
            pm = QPixmap(logo_path)
            if not pm.isNull():
                logo_lbl.setPixmap(pm.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                logo_lbl.setFixedSize(24, 24)
                self.header_layout.addWidget(logo_lbl)

        header_label = QLabel(APP_TITLE)
        header_label.setObjectName("headerLabel")
        self.header_layout.addWidget(header_label)
        
        self.header_layout.addStretch()

        # 버튼 컨테이너 (아이콘 버튼들)
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)

        # 테마 토글 버튼
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("themeButton")
        self.btn_theme.setFixedSize(32, 32)
        self.update_theme_icon()
        self.btn_theme.setToolTip("테마 전환 (라이트/다크)")
        self.btn_theme.clicked.connect(self.toggle_theme)

        # 미니모드 토글 버튼 (아이콘 버전)
        self.btn_mini = QPushButton()
        self.btn_mini.setObjectName("themeButton")  # 동일한 스타일 적용
        self.btn_mini.setCheckable(True)
        self.btn_mini.setFixedSize(32, 32)
        self.update_mode_icon()
        self.btn_mini.clicked.connect(self.toggle_mini_mode_with_icon)

        button_layout.addWidget(self.btn_theme)
        button_layout.addWidget(self.btn_mini)

        self.header_layout.addWidget(button_container)

        left_layout.addWidget(header_widget)
        
        # 2. 설정 + 제어 통합
        control_group = QGroupBox("캡처 설정 및 제어")
        control_layout = QVBoxLayout()
        control_layout.setSpacing(6)
        control_layout.setContentsMargins(8, 8, 8, 8)
        
        # 모드 선택
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("모드:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["페이지 넘김 (기본)", "가로 스크롤 (이어붙이기)"])
        mode_layout.addWidget(self.mode_combo, 1)
        control_layout.addLayout(mode_layout)

        # 설정 (가로 배치)
        settings_h = QHBoxLayout()
        settings_h.addWidget(QLabel("민감도:"))
        self.sensitivity_input = QLineEdit(DEFAULT_SENSITIVITY)
        sens_validator = QDoubleValidator(0.0, 9999.0, 2, self)
        sens_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.sensitivity_input.setValidator(sens_validator)
        self.sensitivity_input.editingFinished.connect(self.validate_sensitivity)
        self.sensitivity_input.setMaximumWidth(50)
        self.sensitivity_input.setMinimumHeight(28)
        settings_h.addWidget(self.sensitivity_input)
        
        settings_h.addWidget(QLabel("딜레이:"))
        self.delay_input = QLineEdit(DEFAULT_DELAY)
        self.delay_input.setValidator(QIntValidator(0, 9999, self))
        self.delay_input.editingFinished.connect(self.validate_delay)
        self.delay_input.setMaximumWidth(50)
        self.delay_input.setMinimumHeight(28)
        settings_h.addWidget(self.delay_input)
        settings_h.addWidget(QLabel("초"))
        settings_h.addStretch()
        
        control_layout.addLayout(settings_h)

        # 투명도 조절
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("투명도:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setRange(MIN_OPACITY, DEFAULT_OPACITY)
        self.opacity_slider.setValue(DEFAULT_OPACITY)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        opacity_layout.addWidget(self.opacity_slider)
        
        self.chk_always_on_top = QCheckBox("항상 위")
        self.chk_always_on_top.setStyleSheet("margin-left: 5px;")
        self.chk_always_on_top.stateChanged.connect(self.toggle_always_on_top)
        opacity_layout.addWidget(self.chk_always_on_top)
        control_layout.addLayout(opacity_layout)
        
        # 버튼들
        self.btn_select = QPushButton("1. 영역 선택")
        self.btn_select.setObjectName("selectButton")
        self.btn_select.setMinimumHeight(36)
        self.btn_select.clicked.connect(self.toggle_selection_mode)
        
        # 캡처 토글 버튼 (시작/중지 통합)
        self.btn_capture = QPushButton("2. 캡처 시작")
        self.btn_capture.setObjectName("captureButton")
        self.btn_capture.setMinimumHeight(42)
        self.btn_capture.setEnabled(False)
        self.btn_capture.clicked.connect(self.toggle_capture)

        self.buttons_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.buttons_layout.addWidget(self.btn_select)
        self.buttons_layout.addWidget(self.btn_capture)
        control_layout.addLayout(self.buttons_layout)
        control_group.setLayout(control_layout)
        left_layout.addWidget(control_group)

        # 3. 캡처 목록 + 미리보기 통합
        self.capture_group = QGroupBox("캡처된 이미지")
        capture_layout = QVBoxLayout()
        capture_layout.setSpacing(6)
        capture_layout.setContentsMargins(8, 8, 8, 8)
        
        # 미리보기 라벨은 오른쪽 패널로 이동
        
        # 목록 (아래)
        list_section = QLabel("목록")
        list_section.setObjectName("sectionLabel")
        capture_layout.addWidget(list_section)
        
        self.list_container = QFrame()
        self.list_container.setObjectName("listContainer")
        list_cont_layout = QVBoxLayout(self.list_container)
        list_cont_layout.setContentsMargins(0, 0, 0, 0)
        list_cont_layout.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setMinimumHeight(100)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemClicked.connect(self.show_image_preview)
        self.list_widget.model().rowsMoved.connect(self.on_list_order_changed)
        self.list_widget.model().rowsRemoved.connect(self.on_list_order_changed)
        list_cont_layout.addWidget(self.list_widget)
        capture_layout.addWidget(self.list_container)
        
        # 버튼 레이아웃 (선택 삭제 / 전체 초기화)
        list_btn_layout = QHBoxLayout()
        
        self.btn_reslice = QPushButton("다시 자르기")
        self.btn_reslice.setMinimumHeight(28)
        self.btn_reslice.clicked.connect(self.reslice_last_scroll)
        self.btn_reslice.hide()
        self.btn_reslice.setStyleSheet("""
            QPushButton { background-color: #17a2b8; color: white; border: none; border-radius: 4px; padding: 0px 2px; font-size: 11px; }
            QPushButton:hover { background-color: #138496; }
            QPushButton:pressed { background-color: #117a8b; }
            QPushButton:disabled { background-color: #e0e0e0; color: #a0a0a0; }
        """)

        self.btn_delete = QPushButton("선택 삭제")
        self.btn_delete.setMinimumHeight(28)
        self.btn_delete.clicked.connect(self.delete_selected_item)
        self.btn_delete.setStyleSheet("""
            QPushButton { background-color: #6c757d; color: white; border: none; border-radius: 4px; padding: 0px 2px; font-size: 11px; }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:pressed { background-color: #545b62; }
        """)
        
        self.btn_reset = QPushButton("전체 초기화")
        self.btn_reset.setMinimumHeight(28)
        self.btn_reset.setStyleSheet("""
            QPushButton { background-color: #d9534f; color: white; border: none; border-radius: 4px; padding: 0px 2px; font-size: 11px; }
            QPushButton:hover { background-color: #c9302c; }
            QPushButton:pressed { background-color: #ac2925; }
        """)
        self.btn_reset.clicked.connect(self.reset_all)
        
        list_btn_layout.addWidget(self.btn_reslice, 1)
        list_btn_layout.addWidget(self.btn_reset, 1)
        list_btn_layout.addWidget(self.btn_delete, 1)
        capture_layout.addLayout(list_btn_layout)
        
        self.capture_group.setLayout(capture_layout)
        left_layout.addWidget(self.capture_group, 1)

        # 미니 모드용 미리보기 (초기엔 숨김)
        self.mini_preview_label = QLabel()
        self.mini_preview_label.setObjectName("miniPreviewLabel")
        self.mini_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mini_preview_label.setMinimumHeight(150)
        self.mini_preview_label.hide()
        left_layout.addWidget(self.mini_preview_label)

        # 4. PDF 생성
        self.btn_pdf = QPushButton("3. 편집 및 저장")
        self.btn_pdf.setObjectName("pdfButton")
        self.btn_pdf.setMinimumHeight(42)
        self.btn_pdf.setEnabled(False)
        self.btn_pdf.clicked.connect(self.switch_to_editor)
        left_layout.addWidget(self.btn_pdf)

        # 5. 상태
        self.status_label = QLabel("준비 완료")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(32)
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        # --- 오른쪽 패널 (대형 미리보기 및 에디터) ---
        self.right_stack = QStackedWidget()
        
        # 페이지 0: 캡처 대기/결과 화면
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        
        self.image_preview_label = QLabel("영역을 선택하고 캡처를 시작하세요.\n캡처된 이미지가 여기에 표시됩니다.")
        self.image_preview_label.setObjectName("previewLabel")
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        
        # 헤더 레이아웃 (제목 + 정보 버튼)
        preview_header = QHBoxLayout()
        preview_title = QLabel("현재 캡처 미리보기")
        preview_title.setStyleSheet("font-weight:bold; font-size:14px;")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()

        # 정보(About) 버튼
        self.btn_info = QPushButton()
        self.btn_info.setObjectName("themeButton")
        self.btn_info.setFixedSize(32, 32)
        self.btn_info.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.btn_info.setToolTip("정보")
        self.btn_info.clicked.connect(self.show_about_dialog)
        preview_header.addWidget(self.btn_info)

        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.image_preview_label, 1)
        
        self.right_stack.addWidget(preview_container)
        
        # 페이지 1: 에디터
        self.editor_widget = ScoreEditorWidget()
        self.editor_widget.save_requested.connect(self.generate_pdf_final)
        self.editor_widget.cancel_requested.connect(self.switch_to_capture)
        self.editor_widget.set_font_families(self.font_bold_family, self.font_regular_family)
        
        self.right_stack.addWidget(self.editor_widget)

        self.overlay = SelectionOverlay(font_family=self.font_bold_family)
        self.overlay.selection_finished.connect(self.finish_selection)
        self.overlay.selection_cancelled.connect(self.on_selection_cancelled)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.right_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1000])
        
        main_layout.addWidget(splitter)

    def validate_sensitivity(self):
        try:
            text = self.sensitivity_input.text()
            val = float(text) if text else -1.0
            if not (0.0 <= val <= 1.0):
                raise ValueError
        except ValueError:
            show_message(self, "입력 오류", "민감도는 0.0 ~ 1.0 사이여야 합니다.\n기본값(0.9)으로 초기화됩니다.", QMessageBox.Icon.Warning)
            self.sensitivity_input.setText(DEFAULT_SENSITIVITY)

    def validate_delay(self):
        try:
            text = self.delay_input.text()
            val = int(text) if text else -1
            if not (0 <= val <= 60):
                raise ValueError
        except ValueError:
            show_message(self, "입력 오류", "딜레이는 0 ~ 60초 사이여야 합니다.\n기본값(3)으로 초기화됩니다.", QMessageBox.Icon.Warning)
            self.delay_input.setText(DEFAULT_DELAY)

    def toggle_mini_mode(self, checked):
        left_panel = self.findChild(QFrame, "leftPanel")
        
        # 스타일 업데이트를 위한 속성 설정
        if left_panel: left_panel.setProperty("miniMode", checked)
        self.status_label.setProperty("miniMode", checked)

        self.buttons_layout.setDirection(QBoxLayout.Direction.LeftToRight if checked else QBoxLayout.Direction.TopToBottom)

        if checked:
            self.right_stack.hide()
            self.capture_group.hide()
            self.mini_preview_label.show()
            self.chk_always_on_top.hide()
            
            if left_panel:
                left_panel.setMaximumWidth(16777215)
                left_panel.setMinimumWidth(0)
                if left_panel.layout():
                    left_panel.layout().setContentsMargins(5, 5, 5, 5)

            if hasattr(self, 'header_layout'):
                self.header_layout.setContentsMargins(5, 2, 5, 2)

            self.setFixedSize(320, 460)
            flags = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | \
                    Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint | \
                    Qt.WindowType.WindowMinimizeButtonHint
            flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            
            self.status_label.setFixedHeight(28)
            self.status_label.setWordWrap(False)
        else:
            self.right_stack.show()
            self.capture_group.show()
            self.mini_preview_label.hide()
            self.chk_always_on_top.show()
            
            if left_panel:
                left_panel.setMaximumWidth(320)
                left_panel.setMinimumWidth(300)
                if left_panel.layout():
                    left_panel.layout().setContentsMargins(10, 10, 10, 10)
            
            if hasattr(self, 'header_layout'):
                self.header_layout.setContentsMargins(0, 0, 0, 0)

            self.setMinimumSize(1000, 600)
            self.setMaximumSize(16777215, 16777215)
            self.resize(1200, 700)
            
            # 일반 모드로 돌아올 때 '항상 위' 체크 여부 확인
            flags = Qt.WindowType.Window
            if hasattr(self, 'chk_always_on_top') and self.chk_always_on_top.isChecked():
                flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            
            self.status_label.setMinimumHeight(32)
            self.status_label.setMaximumHeight(16777215)
            self.status_label.setWordWrap(True)

        self.update_ui_state()
        self.update_mode_icon()
        self.show()
        self.raise_()
        self.activateWindow()
        self.update_mini_preview()
        self.update_title_bar_color()
        
        # 스타일 강제 업데이트 (속성 변경 반영)
        if left_panel:
            self.style().unpolish(left_panel)
            self.style().polish(left_panel)
        self.style().unpolish(self.status_label)
        self.style().polish(self.status_label)

    def toggle_always_on_top(self, state):
        pos = self.pos()
        self.hide()

        is_checked = (state == Qt.CheckState.Checked.value)

        if self.btn_mini.isChecked():
            flags = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | \
                    Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint | \
                    Qt.WindowType.WindowMinimizeButtonHint
        else:
            flags = Qt.WindowType.Window

        if is_checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()
        self.update_title_bar_color()

    def change_opacity(self, value):
        self.setWindowOpacity(value / 100.0)

    def toggle_selection_mode(self):
        self.switch_to_capture()
        # 메인 윈도우를 숨겨서 화면 전체를 선택할 수 있게 함
        self.hide()
        if self.area_indicator:
            self.area_indicator.close()
            self.area_indicator = None
        self.overlay.start()
        self.status_label.setText("영역 선택 중...")

    def finish_selection(self, area_dict):
        self.show() # 메인 윈도우 복구
        self.capture_area_dict = area_dict
        
        # 선택 영역 표시 위젯 생성
        if self.area_indicator:
            self.area_indicator.close()
        self.area_indicator = CaptureAreaIndicator(
            area_dict['left'], area_dict['top'], 
            area_dict['width'], area_dict['height']
        )
        
        self.btn_capture.setEnabled(True)
        self.update_ui_state()
        self.status_label.setText(f"영역 설정됨 ({area_dict['width']}×{area_dict['height']})")
        
    def on_selection_cancelled(self):
        self.show()
        if self.capture_area_dict:
            if self.area_indicator:
                self.area_indicator.close()
            self.area_indicator = CaptureAreaIndicator(
                self.capture_area_dict['left'], 
                self.capture_area_dict['top'], 
                self.capture_area_dict['width'], 
                self.capture_area_dict['height']
            )
            self.status_label.setText(f"영역 설정됨 ({self.capture_area_dict['width']}×{self.capture_area_dict['height']})")
        else:
            self.status_label.setText("준비 완료")

    def switch_to_editor(self):
        """에디터 모드로 전환"""
        if self.is_capturing:
            self.stop_capture()

        if self.btn_mini.isChecked():
            self.btn_mini.setChecked(False)
            self.toggle_mini_mode(False)

        files = self.get_ordered_files()
        if not files:
            return
        
        self.editor_widget.load_preview(files)
        self.right_stack.setCurrentIndex(1)
        self.status_label.setText("PDF 편집 모드")
        
        if self.area_indicator:
            self.area_indicator.hide()

    def switch_to_capture(self):
        """캡처 모드로 복귀"""
        self.right_stack.setCurrentIndex(0)
        self.status_label.setText("캡처 모드")
        self.btn_select.setEnabled(True)
        self.btn_capture.setEnabled(True)
        
        if self.area_indicator and self.capture_area_dict:
            self.area_indicator.show()

    def toggle_capture(self):
        """캡처 시작/중지 토글"""
        if not self.is_capturing:
            if self.captured_files:
                reply = show_message(self, '새 캡처 시작', 
                                   '새로운 캡처를 시작하면 기존 캡처 데이터가 모두 삭제됩니다.\n계속하시겠습니까?',
                                   QMessageBox.Icon.Question,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                   QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    return
            self.start_capture()
        else:
            self.stop_capture()

    def start_capture(self):
        self.switch_to_capture()
        self.is_capturing = True
        self.update_ui_state()
        
        if self.area_indicator:
            self.area_indicator.set_color(QColor(255, 0, 0)) # 빨간색 (녹화 중)
        
        self.btn_select.setEnabled(False)
        self.btn_pdf.setEnabled(False)
        
        self.captured_files = []
        self.list_widget.clear()
        self.btn_reslice.hide()
        self.last_stitched_image = None
        self.image_preview_label.setText("캡처 진행 중...")
        self.current_original_pixmap = None
        self.update_mini_preview()
        self.current_scroll_chunks = []
        self.current_scroll_filename = None
        self.sig_reset_worker.emit()
        self.editor_widget.clear_image_cache()
        self.is_first_capture = True
        
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        try:
            float(self.sensitivity_input.text())
        except ValueError:
            self.sensitivity_input.setText(DEFAULT_SENSITIVITY)

        try:
            self.countdown_value = int(self.delay_input.text())
        except ValueError:
            self.countdown_value = int(DEFAULT_DELAY)
            self.delay_input.setText(DEFAULT_DELAY)
        self.run_countdown()

    def run_countdown(self):
        if not self.is_capturing:
            return

        if self.countdown_value > 0:
            self.status_label.setText(f"{self.countdown_value}초 후 시작...")
            self.countdown_value -= 1
            QTimer.singleShot(1000, self.run_countdown)
        else:
            self.status_label.setText("캡처 진행 중")
            self.capture_timer.start(1000)

    def stop_capture(self):
        self.is_capturing = False
        self.capture_timer.stop()
        self.update_ui_state()
        
        if self.area_indicator:
            self.area_indicator.set_color(QColor(0, 255, 0)) # 초록색 (대기 중)
        
        # 스크롤 모드: 캡처 종료 시 일괄 자르기 수행
        if self.mode_combo.currentIndex() == 1 and self.current_scroll_chunks:
            self.status_label.setText("편집 창을 여는 중...")
            QApplication.processEvents()
            
            full_img = np.hstack(self.current_scroll_chunks)
            self.last_stitched_image = full_img
            self.btn_reslice.show()
            
            dlg = ScrollSlicerDialog(full_img, self.capture_area_dict['width'], self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.last_cut_points = dlg.canvas.cut_points
                sliced_images = dlg.get_sliced_images()
                for img in sliced_images:
                    self._save_image_to_list(img)
                self.status_label.setText(f"스크롤 캡처 완료 ({len(sliced_images)}장)")
                self.switch_to_editor()
            else:
                self.status_label.setText("스크롤 캡처 취소됨")
            
            self.current_scroll_chunks = []

        self.btn_select.setEnabled(True)
        self.btn_pdf.setEnabled(len(self.captured_files) > 0)
        
        count = len(self.captured_files)
        self.status_label.setText(f"캡처 중지 (총 {count}개)")

    def _save_image_to_list(self, img):
        """이미지를 저장하고 리스트에 추가하는 내부 함수"""
        self.capture_counter += 1
        filename = os.path.join(OUTPUT_FOLDER, f"score_scroll_{self.capture_counter:03d}.png")
        imwrite_unicode(filename, img)
        self.captured_files.append(filename)
        self.is_saved = False
        
        item = QListWidgetItem(os.path.basename(filename))
        item.setData(Qt.ItemDataRole.UserRole, filename)
        self.list_widget.addItem(item)
        self.list_widget.scrollToBottom()
        self.display_image(filename)

    def reslice_last_scroll(self):
        if self.last_stitched_image is None:
            return
        
        should_clear = False
        if self.list_widget.count() > 0:
            reply = show_message(
                self, 
                "다시 자르기", 
                "기존 캡처 목록을 초기화하시겠습니까?",
                QMessageBox.Icon.Question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
            
            should_clear = (reply == QMessageBox.StandardButton.Yes)
        
        width = self.capture_area_dict['width'] if self.capture_area_dict else self.last_stitched_image.shape[1]
        dlg = ScrollSlicerDialog(self.last_stitched_image, width, self, initial_points=self.last_cut_points)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.last_cut_points = dlg.canvas.cut_points
            # 기존 이미지 삭제 로직 수행
            if should_clear:
                # 디스크에서 파일 삭제
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    path = item.data(Qt.ItemDataRole.UserRole)
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except: pass
                
                self.captured_files = []
                self.list_widget.clear()
                self.image_preview_label.clear()
                self.image_preview_label.setText("영역을 선택하고 캡처를 시작하세요.\n캡처된 이미지가 여기에 표시됩니다.")
                self.current_original_pixmap = None

            sliced_images = dlg.get_sliced_images()
            for img in sliced_images:
                self._save_image_to_list(img)
            
            self.btn_pdf.setEnabled(len(self.captured_files) > 0)
            self.status_label.setText(f"재자르기 완료 ({len(sliced_images)}장)")
            self.switch_to_editor()

    def perform_capture(self):
        if not self.capture_area_dict or self.is_worker_busy:
            return
        
        self.is_worker_busy = True
        # 캡처 영역 크기 가져오기
        w, h = self.capture_area_dict['width'], self.capture_area_dict['height']
            
        try:
            is_scroll_mode = (self.mode_combo.currentIndex() == 1)

            # 스크롤 모드일 경우: 캡처 전 인디케이터 숨김
            if is_scroll_mode and self.area_indicator:
                self.area_indicator.hide()
                
                wait_time = 0.5 if self.is_first_capture else 0.2
                t_end = time.time() + wait_time
                while time.time() < t_end:
                    QApplication.processEvents()
                    time.sleep(0.01)
                if self.is_first_capture: self.is_first_capture = False

            # 화면 캡처 (Global Coordinates)
            pixmap = grab_screen_area(self.capture_area_dict['left'], self.capture_area_dict['top'], w, h)
            
            # 스크롤 모드일 경우: 캡처 후 인디케이터 복구
            if is_scroll_mode and self.area_indicator:
                self.area_indicator.show()

            # QPixmap -> OpenCV 변환 (Main Thread)
            img_bgr = qpixmap_to_cv(pixmap)
            
            # 워커 스레드로 처리 위임
            mode = self.mode_combo.currentIndex()
            try:
                sensitivity = float(self.sensitivity_input.text())
            except ValueError:
                sensitivity = float(DEFAULT_SENSITIVITY)
            self.sig_process_frame.emit(img_bgr, mode, sensitivity)
            
        except Exception as e:
            show_message(self, "캡처 오류", f"화면 캡처 중 오류가 발생했습니다:\n{e}", QMessageBox.Icon.Critical)
            self.status_label.setText(f"캡처 오류")
            self.is_worker_busy = False

    def on_worker_finished(self):
        """워커 처리 완료 시 호출"""
        self.is_worker_busy = False

    def show_error_message(self, message):
        show_message(self, "오류", message, QMessageBox.Icon.Warning)

    def on_request_clean_capture(self):
        """페이지 모드: 변화 감지 시 깨끗한 이미지 캡처 요청"""
        if not self.capture_area_dict:
            self.is_worker_busy = False
            return

        # 인디케이터 숨기고 캡처
        if self.area_indicator:
            self.area_indicator.hide()
            
            wait_time = 0.5 if self.is_first_capture else 0.1
            t_end = time.time() + wait_time
            while time.time() < t_end:
                QApplication.processEvents()
                time.sleep(0.01)
            if self.is_first_capture: self.is_first_capture = False

        pixmap_clean = grab_screen_area(self.capture_area_dict['left'], self.capture_area_dict['top'], 
                                       self.capture_area_dict['width'], self.capture_area_dict['height'])
        
        if self.area_indicator:
            self.area_indicator.show()
        
        img_bgr_clean = qpixmap_to_cv(pixmap_clean)
        self.sig_save_clean.emit(img_bgr_clean)

    def on_image_saved(self, filename, img_bgr):
        """이미지 저장 완료 후 UI 업데이트"""
        self.captured_files.append(filename)
        self.is_saved = False
        item = QListWidgetItem(os.path.basename(filename))
        item.setData(Qt.ItemDataRole.UserRole, filename)
        self.list_widget.addItem(item)
        self.list_widget.scrollToBottom()
        
        self.display_image(filename)
        self.btn_pdf.setEnabled(True)
        
        count = len(self.captured_files)
        self.status_label.setText(f"캡처 완료 (총 {count}개)")

    def on_scroll_updated(self, new_part):
        """스크롤 모드: 버퍼 업데이트 시 미리보기 갱신"""
        self.current_scroll_chunks.append(new_part)
        # 미리보기: 전체 이미지가 아닌 최근 캡처 영역만큼만 표시
        if self.capture_area_dict:
            w = self.capture_area_dict['width']
            current_w = 0
            tail_parts = []
            for part in reversed(self.current_scroll_chunks):
                tail_parts.insert(0, part)
                current_w += part.shape[1]
                if current_w >= w:
                    break
            if tail_parts:
                preview_img = np.hstack(tail_parts)
                if preview_img.shape[1] > w:
                    preview_img = preview_img[:, -w:]
                self.display_cv_image(preview_img)
        
        self.btn_pdf.setEnabled(True)

    def show_image_preview(self, item):
        # UserRole에서 경로 가져오기
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            path = os.path.join(OUTPUT_FOLDER, item.text())
        self.display_image(path)

    def display_cv_image(self, cv_img):
        """OpenCV 이미지를 미리보기 라벨에 표시"""
        self.current_original_pixmap = cv2_to_qpixmap(cv_img)
        self.update_preview_label()
        self.update_mini_preview()

    def display_image(self, filepath):
        if os.path.exists(filepath):
            self.current_original_pixmap = QPixmap(filepath)
            self.update_preview_label()
            self.update_mini_preview()

    def update_preview_label(self):
        if self.current_original_pixmap and not self.current_original_pixmap.isNull():
            # 라벨의 테두리 등을 고려하여 약간 작게 스케일링 (10px 여유)
            target_size = self.image_preview_label.size() - QSize(10, 10)
            if target_size.width() <= 0 or target_size.height() <= 0: target_size = QSize(1, 1)
            
            scaled_pixmap = self.current_original_pixmap.scaled(
                target_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_preview_label.setPixmap(scaled_pixmap)

    def update_mini_preview(self):
        if self.mini_preview_label.isVisible():
            if self.current_original_pixmap and not self.current_original_pixmap.isNull():
                target_size = self.mini_preview_label.size() - QSize(4, 4)
                scaled = self.current_original_pixmap.scaled(
                    target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.mini_preview_label.setPixmap(scaled)
            else:
                self.mini_preview_label.clear()
                self.mini_preview_label.setText("대기 중")

    def resizeEvent(self, event):
        self.update_preview_label()
        self.update_mini_preview()
        super().resizeEvent(event)

    def get_ordered_files(self):
        """리스트 위젯의 순서대로 파일 경로 반환"""
        files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path and os.path.exists(path):
                files.append(path)
        return files

    def delete_selected_item(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
            
        reply = show_message(self, '삭제 확인', f'선택한 {len(items)}개의 이미지를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.',
                           QMessageBox.Icon.Question,
                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                           QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        for item in items:
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            full_path = item.data(Qt.ItemDataRole.UserRole)
            
            if full_path in self.captured_files:
                self.captured_files.remove(full_path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except: pass
            
        if self.list_widget.count() == 0:
            self.image_preview_label.clear()
            self.image_preview_label.setText("선택된 이미지 없음")
            self.btn_pdf.setEnabled(False)
            self.current_original_pixmap = None
            self.is_saved = True
        else:
            last_row = self.list_widget.count() - 1
            self.list_widget.setCurrentRow(last_row)
            self.show_image_preview(self.list_widget.item(last_row))
            self.is_saved = False
        
        self.status_label.setText(f"삭제 완료 (남은 이미지: {self.list_widget.count()}개)")

    def reset_all(self):
        """모든 데이터 초기화 및 캡처 모드 복귀"""
        reply = show_message(self, '초기화 확인', '모든 캡처 데이터를 삭제하고 초기화하시겠습니까?',
                           QMessageBox.Icon.Question,
                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                           QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.current_scroll_chunks = []
            self.last_stitched_image = None
            self.last_cut_points = None
            self.btn_reslice.hide()
            self.stop_capture()
            self.captured_files = []
            self.is_saved = True
            self.list_widget.clear()
            self.image_preview_label.clear()
            self.image_preview_label.setText("영역을 선택하고 캡처를 시작하세요.\n캡처된 이미지가 여기에 표시됩니다.")
            self.current_original_pixmap = None
            self.sig_reset_worker.emit()
            self.update_mini_preview()
            self.btn_pdf.setEnabled(False)
            self.editor_widget.reset_fields()
            self.switch_to_capture()
            self.status_label.setText("초기화 완료")

    def on_list_order_changed(self):
        if self.right_stack.currentIndex() == 1:
            files = self.get_ordered_files()
            self.editor_widget.load_preview(files)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.list_widget.hasFocus():
            self.delete_selected_item()
        super().keyPressEvent(event)

    def create_pdf(self):
        self.switch_to_editor()

    def generate_pdf_final(self, metadata):
        files = self.get_ordered_files()
        if not files:
            return
            
        # 파일 이름 생성 로직
        title = metadata.get('title', '').strip()
        composer = metadata.get('composer', '').strip()
        bpm = metadata.get('bpm', '').strip()
        url = metadata.get('url', '').strip()
        
        if title or composer:
            if title and composer:
                filename_base = f"{title} - {composer} (TAB)"
            else:
                filename_base = title if title else composer
        else:
            filename_base = "Captured Score"
            
        # 파일명 특수문자 제거 (윈도우 파일명 금지 문자)
        filename_base = re.sub(r'[\\/*?:"<>|]', "", filename_base).strip()
        if not filename_base:
            filename_base = "TAB"
            
        path, filter_selected = QFileDialog.getSaveFileName(
            self, 
            "파일 저장", 
            filename_base, 
            "PDF Files (*.pdf);;PNG Images (*.png);;JPEG Images (*.jpg)"
        )
        
        if not path:
            self.status_label.setText("저장 취소됨")
            return
            
        # 확장자 확인 및 보정
        ext = os.path.splitext(path)[1].lower()
        if not ext:
            if "png" in filter_selected.lower():
                ext = ".png"
            elif "jpg" in filter_selected.lower():
                ext = ".jpg"
            else:
                ext = ".pdf"
            path += ext
        
        files = self.get_ordered_files()
        total_steps = len(files) + 2
        progress = QProgressDialog("파일 생성 및 저장 중...", None, 0, total_steps, self)
        progress.setWindowTitle("저장 중")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        apply_window_theme(progress, self)
        progress.show()
        QApplication.processEvents()

        try:
            self.status_label.setText("파일 생성 중...")
            QApplication.processEvents()
            
            # 설정값 파싱
            try:
                margin = int(metadata.get('margin', DEFAULT_MARGIN))
                spacing = int(metadata.get('spacing', DEFAULT_SPACING))
            except ValueError:
                margin = int(DEFAULT_MARGIN)
                spacing = int(DEFAULT_SPACING)
            
            page_num_pos = metadata.get('page_num_pos', '하단 중앙')
            use_basic = metadata.get('enhance', False)
            use_high = metadata.get('high_quality', False)
            do_invert = metadata.get('invert', False)
            invert_mode = metadata.get('invert_mode', 'both')
            do_adaptive = metadata.get('adaptive', False)
            
            invert_bg = do_invert and (invert_mode in ["bg", "both"])
            invert_score = do_invert and (invert_mode in ["score", "both"])
            
            bg_color = "black" if invert_bg else "white"
            text_fill_color = "white" if invert_bg else "black"

            image_objects = []
            for i, f in enumerate(files):
                progress.setValue(i)
                progress.setLabelText(f"이미지 처리 중... ({i+1}/{len(files)})")
                QApplication.processEvents()

                if use_basic or use_high or do_adaptive:
                    cv_img = None
                    if use_high:
                        if f in self.editor_widget.hq_cache:
                            cv_img = imread_unicode(self.editor_widget.hq_cache[f])
                        else:
                            cv_img = imread_unicode(f)
                            if cv_img is not None:
                                cv_img = enhance_score_image(cv_img, use_basic=False, use_high=True)
                                cached_path = self.editor_widget._save_to_cache(cv_img, f, 'hq')
                                if cached_path:
                                    self.editor_widget.hq_cache[f] = cached_path
                    elif use_basic:
                        if f in self.editor_widget.basic_cache:
                            cv_img = imread_unicode(self.editor_widget.basic_cache[f])
                        else:
                            cv_img = imread_unicode(f)
                            if cv_img is not None:
                                cv_img = enhance_score_image(cv_img, use_basic=True, use_high=False)
                                cached_path = self.editor_widget._save_to_cache(cv_img, f, 'basic')
                                if cached_path:
                                    self.editor_widget.basic_cache[f] = cached_path
                    
                    if cv_img is None:
                        cv_img = imread_unicode(f)
                            
                    if cv_img is not None:
                        processed = cv_img
                        
                        if do_adaptive:
                            processed = apply_natural_grayscale(processed)

                        if invert_score:
                            processed = cv2.bitwise_not(processed)
                        image_objects.append(Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)))
                else:
                    img = Image.open(f).convert("RGB")
                    if invert_score:
                        img = ImageOps.invert(img)
                    image_objects.append(img)

            if not image_objects:
                self.status_label.setText("처리할 이미지가 없습니다.")
                progress.close()
                return

            # 원본 이미지 너비 확인 (비율 계산용)
            raw_width = 1000
            if files and os.path.exists(files[0]):
                try:
                    with Image.open(files[0]) as tmp:
                        raw_width = tmp.width
                except: pass

            # 기준 해상도 보정 (최소 A4 300DPI 수준 확보)
            current_width = image_objects[0].width
            
            # 1. 처리(업스케일링)에 따른 스케일 계산
            processing_scale = current_width / raw_width if raw_width > 0 else 1.0
            
            margin = int(margin * processing_scale)
            spacing = int(spacing * processing_scale)

            min_width = 2480  # A4 @ 300DPI width

            # 항상 A4 300DPI 너비로 고정 (일관된 출력 크기)
            base_width = min_width
            final_scale = min_width / current_width
            
            margin = int(margin * final_scale)
            spacing = int(spacing * final_scale)
            
            # 패딩/오프셋 계산용 통합 비율
            enhance_ratio = processing_scale * final_scale

            page_height = int(base_width * (297 / 210))
            
            # 여백을 고려한 콘텐츠 너비
            content_width = base_width - (margin * 2)
            if content_width < 100: content_width = base_width
            
            final_pages = []
            current_page = Image.new('RGB', (base_width, page_height), bg_color)
            
            current_y = margin

            qr_height_val = 0
            if url and qrcode:
                try:
                    qr_fill = "white" if invert_bg else "black"
                    qr_back = "black" if invert_bg else "white"
                    qr = qrcode.QRCode(box_size=10, border=0)
                    qr.add_data(url)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color=qr_fill, back_color=qr_back).convert("RGB")
                    
                    qr_size = int(base_width * 0.12)
                    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
                    
                    current_page.paste(qr_img, (margin, margin))
                    qr_height_val = qr_size
                except Exception as e:
                    print(f"PDF QR Error: {e}")

            # 제목/작곡가 추가 (첫 페이지)
            title = metadata.get('title', '').strip()
            composer = metadata.get('composer', '').strip()
            bpm = metadata.get('bpm', '').strip()
            
            header_offset = 0
            if title or composer or bpm:
                draw = ImageDraw.Draw(current_page)
                title_font = get_pil_font(FONT_BOLD_PATH, int(base_width/30))
                comp_font = get_pil_font(FONT_REGULAR_PATH, int(base_width/60))
                bpm_font = get_pil_font(FONT_BOLD_PATH, int(base_width/60))
                
                if title:
                    tw, th = get_text_size(draw, title, title_font)
                    draw.text(((base_width - tw) / 2, current_y), title, fill=text_fill_color, font=title_font)
                    header_offset += th + int(20 * enhance_ratio)
                
                if composer:
                    cw, ch = get_text_size(draw, composer, comp_font)
                    draw.text((base_width - margin - cw, current_y + header_offset), composer, fill=text_fill_color, font=comp_font)
                    header_offset += ch + int(20 * enhance_ratio)
                
                if bpm:
                    bpm_text = f"BPM: {bpm}"
                    bw, bh = get_text_size(draw, bpm_text, bpm_font)
                    
                    if qr_height_val > 0 and header_offset < qr_height_val:
                        header_offset = qr_height_val + int(10 * enhance_ratio)
                        
                    draw.text((margin, current_y + header_offset), bpm_text, fill=text_fill_color, font=bpm_font)
                    header_offset += bh + int(10 * enhance_ratio)

            final_header_height = max(header_offset, qr_height_val)
            if final_header_height > 0:
                current_y += final_header_height + int(50 * enhance_ratio)

            progress.setValue(len(files))
            progress.setLabelText("페이지 레이아웃 구성 중...")
            QApplication.processEvents()

            for img in image_objects:
                if img.width != content_width:
                    new_h = int(img.height * (content_width / img.width))
                    img = img.resize((content_width, new_h), Image.Resampling.LANCZOS)
                else:
                    new_h = img.height
                    
                if current_y + new_h + margin > page_height:
                    final_pages.append(current_page)
                    current_page = Image.new('RGB', (base_width, page_height), bg_color)
                    current_y = margin
                    
                current_page.paste(img, (margin, current_y))
                current_y += new_h + spacing
                
            final_pages.append(current_page)

            # 페이지 번호 및 워터마크 추가
            draw_font = get_pil_font(FONT_REGULAR_PATH, max(14, int(base_width/50)))
            
            # 워터마크 설정
            watermark_font = get_pil_font(FONT_BOLD_PATH, max(20, int(base_width/60)))
            watermark_text = "SCORE CAPTURE PRO"
            
            # 투명도를 위한 색상 설정 (RGBA)
            if invert_bg:
                wm_color = (255, 255, 255, 50)  # 다크모드: 흰색 투명
            else:
                wm_color = (0, 0, 0, 40)        # 라이트모드: 검은색 투명

            for i, page in enumerate(final_pages, 1):
                draw = ImageDraw.Draw(page)
                
                # 페이지 번호
                if page_num_pos != "없음":
                    text = f"{i} / {len(final_pages)}"
                    text_w, text_h = get_text_size(draw, text, draw_font)
                    if page_num_pos == "하단 중앙":
                        draw.text(((base_width - text_w) // 2, page_height - margin // 2 - text_h), text, fill=text_fill_color, font=draw_font)
                    elif page_num_pos == "하단 우측":
                        draw.text((base_width - margin - text_w, page_height - margin // 2 - text_h), text, fill=text_fill_color, font=draw_font)
                    elif page_num_pos == "상단 우측":
                        draw.text((base_width - margin - text_w, margin // 2), text, fill=text_fill_color, font=draw_font)

                # 워터마크
                wm_w, wm_h = get_text_size(draw, watermark_text, watermark_font)
                
                # 텍스트를 그릴 투명 레이어 생성
                txt_layer = Image.new('RGBA', (wm_w + 20, wm_h + 30), (0,0,0,0))
                d_txt = ImageDraw.Draw(txt_layer)
                d_txt.text((10, 10), watermark_text, font=watermark_font, fill=wm_color)
                
                # 밑줄 추가
                line_y = 10 + wm_h + 4
                line_width = max(2, int(base_width/800))
                d_txt.line((10, line_y, 10 + wm_w, line_y), fill=wm_color, width=line_width)
                
                # 위치 계산 (페이지 번호와 겹치지 않도록 배치)
                wm_padding = int(base_width * 0.025)
                x = wm_padding if page_num_pos == "하단 우측" else (base_width - wm_w - wm_padding)
                y = page_height - wm_h - wm_padding
                
                # 원본 페이지에 합성
                page.paste(txt_layer, (x - 10, y - 10), txt_layer)

            progress.setValue(len(files) + 1)
            progress.setLabelText("파일 저장 중...")
            QApplication.processEvents()

            if ext == ".pdf":
                final_pages[0].save(path, save_all=True, append_images=final_pages[1:])
                msg_title = "PDF 생성 완료"
                msg_text = f"PDF가 생성되었습니다.\n\n총 페이지: {len(final_pages)}페이지"
            else:
                # 이미지로 저장 (여러 페이지일 경우 번호 붙임)
                base_path, _ = os.path.splitext(path)
                saved_count = 0
                for i, page in enumerate(final_pages):
                    if len(final_pages) > 1:
                        save_path = f"{base_path}_{i+1:02d}{ext}"
                    else:
                        save_path = path
                    
                    if ext in ['.jpg', '.jpeg']:
                        page.save(save_path, quality=95)
                    else:
                        page.save(save_path)
                    saved_count += 1
                
                msg_title = "이미지 저장 완료"
                msg_text = f"이미지가 저장되었습니다.\n\n저장된 파일 수: {saved_count}개"

            self.is_saved = True
            self.status_label.setText(f"저장 완료")
            
            progress.setValue(total_steps)
            progress.close()
            
            show_message(self, msg_title, msg_text, QMessageBox.Icon.Information)
            
        except Exception as e:
            progress.close()
            self.status_label.setText(f"저장 실패")
            show_message(self, "오류", f"파일 저장 실패:\n{e}", QMessageBox.Icon.Critical)

    def show_about_dialog(self):
        dlg = AboutDialog(self, is_secret_active=self.is_easter_egg_active)
        dlg.easter_egg_activated.connect(self.apply_secret_theme)
        dlg.exec()

    def apply_secret_theme(self):
        self.is_easter_egg_active = True
        
        # 1. 아이콘 변경
        secret_path = EASTER_EGG_IMAGE_PATH
        if os.path.exists(secret_path):
            self.setWindowIcon(QIcon(secret_path))
            logo_lbl = self.findChild(QLabel, "logoLabel")
            if logo_lbl:
                pm = QPixmap(secret_path)
                logo_lbl.setPixmap(pm.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        # 2. 이스터 에그 스타일 적용
        self.btn_delete.setStyleSheet("")
        self.btn_reset.setStyleSheet("")
        self.btn_reslice.setStyleSheet("")
        self.btn_theme.hide()
        
        self.setStyleSheet(EASTER_EGG_STYLE)
        self.setWindowTitle(EASTER_EGG_TITLE)
        
        header_lbl = self.findChild(QLabel, "headerLabel")
        if header_lbl:
            header_lbl.setText(EASTER_EGG_TITLE)
            
        self.update_ui_state()
        self.update_mode_icon()
        self.update_title_bar_color()
        
        # 3. 효과음 및 윈도우 흔들기 효과
        QApplication.beep()
        self.shake_window()

    def shake_window(self):
        """윈도우 흔들기 애니메이션"""
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(500)
        anim.setLoopCount(1)
        start_pos = self.pos()
        for i in range(0, 11):
            step = i / 10.0
            offset = 15 if i % 2 == 1 else -15
            if i == 0 or i == 10: offset = 0
            anim.setKeyValueAt(step, start_pos + QPoint(offset, 0))
        self._shake_anim = anim
        anim.start()

    def show_update_notification(self, version, url):
        msg = QMessageBox(self)
        msg.setWindowTitle("업데이트 알림")
        msg.setText(f"새로운 버전 ({version})이 출시되었습니다.")
        msg.setInformativeText("업데이트 내용을 확인하고 다운로드하시겠습니까?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        apply_window_theme(msg, self)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            webbrowser.open(url)

    def closeEvent(self, event):
        if self.captured_files and not self.is_saved:
            reply = show_message(self, '종료 확인', 
                               '저장되지 않은 캡처 데이터가 있습니다.\n정말로 종료하시겠습니까?',
                               QMessageBox.Icon.Question,
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                               QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        if self.is_capturing:
            self.stop_capture() 
        if self.area_indicator:
            self.area_indicator.close()
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.close()
        if hasattr(self, 'worker_thread'):
            self.worker_thread.quit()
            self.worker_thread.wait()

        # 프로그램 종료 시 임시 폴더 및 파일 정리
        if os.path.exists(OUTPUT_FOLDER):
            try:
                shutil.rmtree(OUTPUT_FOLDER, ignore_errors=True)
            except Exception:
                pass

        super().closeEvent(event)
        QApplication.instance().quit()

def exception_hook(exctype, value, tb):
    """전역 예외 처리: 프로그램 충돌 시 메시지 박스 표시"""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    
    # GUI 애플리케이션이 실행 중이라면 메시지 박스 표시
    if QApplication.instance():
        show_message(None, "치명적 오류 발생", 
                    "예기치 않은 오류가 발생하여 프로그램이 종료됩니다.", 
                    QMessageBox.Icon.Critical,
                    QMessageBox.StandardButton.Ok,
                    detailed_text=error_msg)
    
    # 원래의 훅 호출 (콘솔 출력 등) 후 종료
    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

if __name__ == "__main__":
    sys.excepthook = exception_hook

    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    # 중복 실행 방지 로직
    lock_file_path = os.path.join(tempfile.gettempdir(), "ScoreCapturePro.lock")
    lock_file = QLockFile(lock_file_path)
    lock_file.setStaleLockTime(0)

    if not lock_file.tryLock(100):
        # 락 획득 실패 시, 스테일 락(비정상 종료 잔재)인지 확인 후 제거 시도
        if not lock_file.removeStaleLockFile() or not lock_file.tryLock(100):
            show_message(None, "알림", "프로그램이 이미 실행 중입니다.", QMessageBox.Icon.Warning)
            sys.exit(0)

    # 이전 실행 잔재 정리
    cleanup_old_temp_folders()

    # macOS 화면 녹화 권한 확인
    if not check_screen_recording_permission():
        sys.exit(0)

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())