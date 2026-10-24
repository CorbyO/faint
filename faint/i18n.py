"""English/Korean UI text and persistent language selection.

Translation keys use dotted UPPER_CASE namespaces, independent of display text. Do not translate user data,
filenames or saved layer names. Static widgets retain their source text as Qt
properties so switching languages never rebuilds the document or canvas.
"""

import os
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QLibraryInfo,
    QLocale,
    QObject,
    QSettings,
    QTranslator,
    Signal,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractButton, QLabel

SUPPORTED_LANGUAGES = {"en": "English", "ko": "한국어"}
MESSAGES = {
    "MENU.FILE": {"en": "File", "ko": "파일"},
    "COMMON.NEW_IMAGE": {"en": "New image", "ko": "새 그림"},
    "MENU.OPEN": {"en": "Open…", "ko": "불러오기…"},
    "COMMON.SAVE": {"en": "Save", "ko": "저장"},
    "MENU.SAVE_AS": {"en": "Save as…", "ko": "다른 이름으로 저장…"},
    "MENU.EDIT": {"en": "Edit", "ko": "편집"},
    "COMMON.UNDO": {"en": "Undo", "ko": "실행 취소"},
    "COMMON.REDO": {"en": "Redo", "ko": "다시 실행"},
    "COMMON.COPY": {"en": "Copy", "ko": "복사"},
    "EDIT.COPY_MERGED": {"en": "Copy merged", "ko": "모든 레이어에서 복사"},
    "COMMON.CUT": {"en": "Cut", "ko": "잘라내기"},
    "EDIT.PASTE_AS_LAYER": {"en": "Paste as new layer", "ko": "새 레이어로 붙여넣기"},
    "EDIT.DELETE_SELECTION": {"en": "Delete selection", "ko": "선택 영역 지우기"},
    "MENU.CANVAS_SIZE": {"en": "Canvas size…", "ko": "캔버스 크기 조절…"},
    "EDIT.SELECT_ALL": {"en": "Select all", "ko": "전체 선택"},
    "EDIT.DESELECT": {"en": "Deselect", "ko": "선택 해제"},
    "TOOLBAR.TITLE": {"en": "Drawing tools", "ko": "그리기 도구"},
    "TOOLBAR.LABEL": {"en": "Tools:", "ko": "도구:"},
    "TOOLBAR.SIZE": {"en": "Size ", "ko": "굵기 "},
    "LAYER.TITLE": {"en": "Layers", "ko": "레이어"},
    "LAYER.MERGE": {"en": "Merge", "ko": "합치기"},
    "LAYER.MERGE_HINT": {
        "en": "Merge selected layers · Shift+click to select multiple layers",
        "ko": "선택한 레이어 합치기 · Shift+클릭으로 여러 레이어 선택",
    },
    "PALETTE.TITLE": {"en": "Palette", "ko": "팔레트"},
    "PALETTE.ADD_COLOR": {"en": "Add current color", "ko": "현재 색 추가"},
    "PALETTE.REMOVE_COLOR": {"en": "Remove selected color", "ko": "선택 색 삭제"},
    "MENU.LOAD_PALETTE": {"en": "Load palette…", "ko": "팔레트 불러오기…"},
    "MENU.SAVE_PALETTE": {"en": "Save palette…", "ko": "팔레트 저장…"},
    "ZOOM.INPUT_HINT": {"en": "Enter zoom (10–1600%)", "ko": "배율 직접 입력 (10–1600%)"},
    "ZOOM.INPUT_ACCESSIBLE_NAME": {"en": "Enter zoom", "ko": "확대 배율 입력"},
    "TOOLBAR.PIXEL": {"en": "Pixel", "ko": "픽셀"},
    "TOOLBAR.BRUSH": {"en": "Brush", "ko": "브러시"},
    "TOOLBAR.ERASER": {"en": "Eraser", "ko": "지우개"},
    "TOOLBAR.SELECT": {"en": "Select", "ko": "사각 선택"},
    "TOOLBAR.LINE": {"en": "Line", "ko": "직선"},
    "TOOLBAR.RECTANGLE": {"en": "Rectangle", "ko": "사각형"},
    "TOOLBAR.ELLIPSE": {"en": "Ellipse", "ko": "타원"},
    "TOOLBAR.ROUNDED_RECTANGLE": {"en": "Rounded rectangle", "ko": "둥근 사각형"},
    "TOOLBAR.COLOR_PICKER": {"en": "Color picker", "ko": "컬러 피커"},
    "TOOLBAR.FILL": {"en": "Fill", "ko": "채우기"},
    "TOOL_HINT.PIXEL": {
        "en": "Drag to draw pixels · No antialiasing · Shift: horizontal/vertical",
        "ko": "드래그하여 픽셀 그리기 · 안티앨리어싱 없음 · Shift: 수평/수직",
    },
    "TOOL_HINT.BRUSH": {
        "en": "Drag to draw · Shift: horizontal/vertical",
        "ko": "드래그하여 그리기 · Shift: 수평/수직",
    },
    "TOOL_HINT.ERASER": {"en": "Drag to erase to transparency", "ko": "드래그하여 투명하게 지우기"},
    "TOOL_HINT.SELECT": {
        "en": "Drag to select · Inside: move · Edges: resize · Shift: keep proportions",
        "ko": "드래그로 선택 · 내부: 이동 · 변/모서리: 크기 · Shift: 비율 유지",
    },
    "TOOL_HINT.LINE": {"en": "Drag to draw a line", "ko": "드래그하여 직선 그리기"},
    "TOOL_HINT.RECTANGLE": {
        "en": "Drag to draw a rectangle · Shift: square",
        "ko": "드래그하여 사각형 그리기 · Shift: 정사각형",
    },
    "TOOL_HINT.ELLIPSE": {
        "en": "Drag to draw an ellipse · Shift: circle",
        "ko": "드래그하여 타원 그리기 · Shift: 원",
    },
    "TOOL_HINT.ROUNDED_RECTANGLE": {
        "en": "Drag to draw a rounded rectangle · Shift: equal sides",
        "ko": "드래그하여 둥근 사각형 그리기 · Shift: 가로세로 동일",
    },
    "TOOL_HINT.COLOR_PICKER": {"en": "Click to pick a color", "ko": "클릭하여 색상 추출"},
    "TOOL_HINT.FILL": {"en": "Click to fill a connected area", "ko": "클릭하여 연결 영역 채우기"},
    "DIALOG.CANVAS_SIZE": {"en": "Canvas size", "ko": "캔버스 크기 조절"},
    "DIALOG.LOCK_ASPECT_RATIO": {"en": "Lock aspect ratio", "ko": "비율 잠금"},
    "COMMON.WIDTH": {"en": "Width", "ko": "너비"},
    "COMMON.HEIGHT": {"en": "Height", "ko": "높이"},
    "DIALOG.CANVAS_SIZE_DESCRIPTION": {
        "en": "Resize the canvas from the top left. The image is not scaled.",
        "ko": "왼쪽 위를 기준으로 캔버스 영역을 변경합니다. 그림의 배율은 바뀌지 않습니다.",
    },
    "LAYER.DELETE": {"en": "Delete layer", "ko": "레이어 삭제"},
    "LAYER.HIDE": {"en": "Hide layer", "ko": "레이어 숨기기"},
    "LAYER.SHOW": {"en": "Show layer", "ko": "레이어 보이기"},
    "BACKGROUND.WHITE": {"en": "White", "ko": "흰색"},
    "BACKGROUND.TRANSPARENT": {"en": "Transparent", "ko": "투명"},
    "BACKGROUND.TOGGLE_HINT": {
        "en": "Toggle transparent / white background",
        "ko": "배경을 투명 / 흰색으로 전환",
    },
    "COLOR.CHANGE": {"en": "Change current color", "ko": "현재 색상 변경"},
    "ERROR.IMPORT_IMAGE": {"en": "Could not import image", "ko": "이미지 불러오기 실패"},
    "COLOR.CURRENT_HINT": {
        "en": "Current color {color} · Click to change",
        "ko": "현재 색상 {color} · 클릭하여 변경",
    },
    "DIALOG.CHOOSE_COLOR": {"en": "Choose color", "ko": "색상 선택"},
    "STATUS.PICK_COLOR_HINT": {"en": "Alt+click: pick color", "ko": "Alt+클릭: 색상 추출"},
    "STATUS.NO_LAYERS": {
        "en": "No layers · Add one with + or paste an image",
        "ko": "레이어가 없습니다 · +로 추가하거나 이미지를 붙여넣으세요",
    },
    "STATUS.HIDDEN_LAYER_LOCKED": {
        "en": "🔒 Hidden layer is locked · Click its eye icon to edit",
        "ko": "🔒 숨긴 레이어는 편집할 수 없습니다 · 눈 아이콘으로 표시하면 편집할 수 있습니다",
    },
    "DIALOG.ZOOM": {"en": "Zoom", "ko": "확대 배율"},
    "DIALOG.ZOOM_PERCENT": {"en": "Zoom (%)", "ko": "배율 (%)"},
    "DIALOG.SAVE_ASK_TITLE": {"en": "Unsaved changes", "ko": "변경 사항"},
    "DIALOG.SAVE_ASK_DESCRIPTION": {"en": "Save your changes?", "ko": "변경 내용을 저장할까요?"},
    "COMMON.OPEN": {"en": "Open", "ko": "불러오기"},
    "FILE_FILTER.IMAGES": {
        "en": "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.faint)",
        "ko": "그림 (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.faint)",
    },
    "ERROR.OPEN_FILE": {"en": "Could not open file", "ko": "불러오기 실패"},
    "FILE.UNTITLED": {"en": "Untitled.faint", "ko": "그림.faint"},
    "FILE_FILTER.SAVE": {
        "en": "Faint project (*.faint);;PNG image (*.png);;JPEG image (*.jpg *.jpeg);;WebP image (*.webp);;BMP image (*.bmp);;GIF image (*.gif)",
        "ko": "Faint 프로젝트 (*.faint);;PNG 이미지 (*.png);;JPEG 이미지 (*.jpg *.jpeg);;WebP 이미지 (*.webp);;BMP 이미지 (*.bmp);;GIF 이미지 (*.gif)",
    },
    "ERROR.SAVE_FILE": {"en": "Could not save file", "ko": "저장 실패"},
    "PALETTE.SAVE": {"en": "Save palette", "ko": "팔레트 저장"},
    "FILE_FILTER.PALETTE": {"en": "Palette (*.json)", "ko": "팔레트 (*.json)"},
    "PALETTE.LOAD": {"en": "Load palette", "ko": "팔레트 불러오기"},
    "ERROR.INVALID_PALETTE": {"en": "Invalid color list", "ko": "올바른 색상 배열이 아닙니다"},
    "ERROR.INVALID_LAYER_IMAGE": {"en": "Invalid layer image", "ko": "잘못된 레이어 이미지"},
    "ERROR.READ_IMAGE": {"en": "Could not read image", "ko": "이미지를 읽을 수 없습니다"},
    "ERROR.SAVE_LAYER": {"en": "Could not save layer", "ko": "레이어 저장 실패"},
    "ERROR.SAVE_IMAGE": {"en": "Could not save image", "ko": "이미지 저장 실패"},
    "ERROR.SUPPORTED_FORMATS": {
        "en": "Supported formats: .faint, .png, .jpg, .jpeg, .webp, .bmp, .gif",
        "ko": "지원 형식: .faint, .png, .jpg, .jpeg, .webp, .bmp, .gif",
    },
    "MENU.LANGUAGE": {"en": "Language", "ko": "언어"},
}

# Qt owns these standard button labels. Keep their translation in the same
# translator lifecycle so newly opened dialogs follow the application language.
QT_KOREAN = {
    "OK": "확인",
    "&OK": "확인",
    "Cancel": "취소",
    "&Cancel": "취소",
    "Save": "저장",
    "&Save": "저장",
    "Discard": "저장 안 함",
    "&Discard": "저장 안 함",
    "Open": "열기",
    "&Open": "열기",
    "Close": "닫기",
    "&Close": "닫기",
    "Yes": "예",
    "&Yes": "예",
    "No": "아니요",
    "&No": "아니요",
    "Help": "도움말",
    "&Help": "도움말",
    "Apply": "적용",
    "&Apply": "적용",
    "Reset": "초기화",
    "Restore Defaults": "기본값 복원",
}


def initial_language(settings):
    override = os.environ.get("FAINT_LANGUAGE")
    saved = settings.value("ui/language", "")
    if override in SUPPORTED_LANGUAGES:
        return override
    if saved in SUPPORTED_LANGUAGES:
        return saved
    return "ko" if QLocale.system().language() == QLocale.Language.Korean else "en"


class StandardTranslator(QTranslator):
    def __init__(self, parent):
        super().__init__(parent)
        self.language = "en"

    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        # None becomes a null QString (no translation). An empty string is a
        # successful blank translation and would erase standard button labels.
        if self.language == "ko":
            return QT_KOREAN.get(sourceText)
        return sourceText


class LanguageManager(QObject):
    languageChanged = Signal()

    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings if settings is not None else QSettings("Faint", "Faint")
        self.language = initial_language(self.settings)
        self.qt_base = QTranslator(self)
        # Keep bundled data separate from the standalone executable named "faint".
        bundled = Path(__file__).parent.parent / "faint_translations" / "qtbase_ko.qm"
        system = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / "qtbase_ko.qm"
        self._has_qt_base = self.qt_base.load(str(bundled if bundled.is_file() else system))
        self.qt_translator = StandardTranslator(self)
        self._application = None
        self.ensure_installed()

    def ensure_installed(self):
        application = QCoreApplication.instance()
        if application is not None and application is not self._application:
            self.qt_translator.language = self.language
            if self.language == "ko" and self._has_qt_base:
                application.installTranslator(self.qt_base)
            application.installTranslator(self.qt_translator)
            self._application = application

    def set_language(self, language, persist=True):
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        if persist:
            self.settings.setValue("ui/language", language)
            self.settings.sync()
        if language == self.language:
            return
        self.language = language
        self.ensure_installed()
        application = QCoreApplication.instance()
        if application is not None:
            application.removeTranslator(self.qt_translator)
            application.removeTranslator(self.qt_base)
            if language == "ko" and self._has_qt_base:
                application.installTranslator(self.qt_base)
            self.qt_translator.language = language
            application.installTranslator(self.qt_translator)
        self.languageChanged.emit()


_manager = None


def manager():
    global _manager
    if _manager is None:
        _manager = LanguageManager()
    _manager.ensure_installed()
    return _manager


def tr(key, **values):
    """Resolve a stable message key and substitute named placeholders."""
    # Tooltips append a shortcut to the key; shortcuts are language independent.
    message_key, separator, shortcut = key.rpartition(" (")
    if separator and key.endswith(")") and message_key in MESSAGES:
        return tr(message_key, **values) + separator + shortcut
    text = MESSAGES[key][manager().language]
    return text.format(**values) if values else text


def localize_tree(root):
    """Resolve widget message keys in place, never editable text or layer data."""
    for widget in [root, *root.findChildren(QObject)]:
        pairs = [
            ("windowTitle", "setWindowTitle"),
            ("toolTip", "setToolTip"),
            ("accessibleName", "setAccessibleName"),
            ("title", "setTitle"),
        ]
        if isinstance(widget, (QLabel, QAbstractButton, QAction)):
            pairs.append(("text", "setText"))
        for getter, setter in pairs:
            if not hasattr(widget, getter) or not hasattr(widget, setter):
                continue
            property_name = "faint_translation_" + getter
            source = widget.property(property_name)
            if source is None:
                source = getattr(widget, getter)()
                if source not in MESSAGES and not (
                    " (" in source and source.rpartition(" (")[0] in MESSAGES
                ):
                    continue
                widget.setProperty(property_name, source)
            getattr(widget, setter)(tr(source))
