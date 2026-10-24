"""Window composition only. Keep creation order, labels, geometry and signal wiring stable."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .i18n import SUPPORTED_LANGUAGES
from .tools import TOOLS
from .widgets.layers import LayerDock, LayerList
from .widgets.palette import CurrentColorButton, SwatchDelegate


def build_window_ui(self):
    """Construct the existing layout and connections in their original order."""
    menu = self.menuBar().addMenu("MENU.FILE")
    self.action(menu, "COMMON.NEW_IMAGE", self.new, QKeySequence.StandardKey.New)
    self.action(menu, "MENU.OPEN", self.open, QKeySequence.StandardKey.Open)
    self.action(menu, "COMMON.SAVE", self.save, QKeySequence.StandardKey.Save)
    self.action(menu, "MENU.SAVE_AS", lambda: self.save(True), QKeySequence.StandardKey.SaveAs)
    edit = self.menuBar().addMenu("MENU.EDIT")
    self.undo_action = self.action(edit, "COMMON.UNDO", self.undo, QKeySequence.StandardKey.Undo)
    self.redo_action = self.action(edit, "COMMON.REDO", self.redo)
    self.undo_action.setShortcut(QKeySequence("Ctrl+Z"))
    self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
    self.action(edit, "COMMON.COPY", self.copy, QKeySequence.StandardKey.Copy)
    self.action(edit, "EDIT.COPY_MERGED", self.copy_merged, "Ctrl+Shift+C")
    self.action(edit, "COMMON.CUT", self.cut, QKeySequence.StandardKey.Cut)
    self.action(edit, "EDIT.PASTE_AS_LAYER", self.paste, QKeySequence.StandardKey.Paste)
    self.action(edit, "EDIT.DELETE_SELECTION", self.clear_selection, "Delete")
    self.action(edit, "MENU.CANVAS_SIZE", self.resize_canvas_dialog, "Ctrl+E")
    self.action(edit, "EDIT.SELECT_ALL", self.select_all, QKeySequence.StandardKey.SelectAll)
    self.action(edit, "EDIT.DESELECT", self.deselect, "Escape")
    toolbar = QToolBar("TOOLBAR.TITLE")
    self.addToolBar(toolbar)
    tools_label = QLabel("TOOLBAR.LABEL")
    tools_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tools_label.setContentsMargins(6, 0, 6, 0)
    toolbar.addWidget(tools_label)
    toolbar.addSeparator()
    self.tool_actions = {}
    for definition in TOOLS:
        key, title = definition.key, definition.label
        action = QAction(title, self)
        action.setCheckable(True)
        shortcut = definition.shortcut
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(f"{title} ({shortcut})" if shortcut else title)
        action.triggered.connect(lambda checked=False, k=key: self.set_tool(k))
        toolbar.addAction(action)
        self.tool_actions[key] = action
    toolbar.setMovable(False)
    self.tools_toolbar = toolbar
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    toolbar.addWidget(spacer)
    toolbar.addSeparator()
    toolbar.addWidget(QLabel("TOOLBAR.SIZE"))
    self.width = QSpinBox()
    self.width.setRange(1, 200)
    self.width.setSuffix(" px")
    self.width.setFixedWidth(88)
    self.width.setValue(4)
    self.width.valueChanged.connect(self.width_changed)
    toolbar.addWidget(self.width)
    self.color_button = CurrentColorButton()
    self.color_button.clicked.connect(self.choose_color)
    self.set_color(self.color)
    dock = LayerDock("LAYER.TITLE", self)
    dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
    self.layer_dock = dock
    dock.toggleViewAction().setEnabled(False)
    titlebar = QWidget()
    title_layout = QHBoxLayout(titlebar)
    title_layout.setContentsMargins(6, 3, 6, 3)
    title_layout.addWidget(QLabel("LAYER.TITLE"))
    title_layout.addStretch()
    self.merge_button = QPushButton("LAYER.MERGE")
    self.merge_button.setEnabled(False)
    self.merge_button.setToolTip("LAYER.MERGE_HINT")
    self.merge_button.clicked.connect(self.merge_layers)
    title_layout.addWidget(self.merge_button)
    dock.setTitleBarWidget(titlebar)
    panel = QWidget()
    layout = QVBoxLayout(panel)
    self.layer_list = LayerList(self)
    self.layer_list.currentRowChanged.connect(self.layer_selected)
    self.layer_list.itemSelectionChanged.connect(self.update_merge_button)
    layout.addWidget(self.layer_list)
    row = QHBoxLayout()
    for text, callback in [("+", self.add_layer), ("−", self.remove_layer)]:
        button = QPushButton(text)
        button.clicked.connect(callback)
        row.addWidget(button)
    layout.addLayout(row)
    palette_toolbar = QToolBar("PALETTE.TITLE")
    palette_toolbar.setMovable(False)
    self.palette_toolbar = palette_toolbar
    palette_toolbar.addWidget(self.color_button)
    palette_toolbar.addSeparator()
    self.addToolBarBreak()
    self.addToolBar(palette_toolbar)
    self.palette_list = QListWidget()
    self.palette_list.setItemDelegate(SwatchDelegate(self.palette_list))
    self.palette_list.setViewMode(QListView.ViewMode.IconMode)
    self.palette_list.setFlow(QListView.Flow.LeftToRight)
    self.palette_list.setWrapping(False)
    self.palette_list.setGridSize(QSize(34, 44))
    self.palette_list.setFixedHeight(48)
    self.palette_list.setSpacing(0)
    self.palette_list.setFrameShape(QListWidget.Shape.NoFrame)
    self.palette_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.palette_list.setCursor(Qt.CursorShape.PointingHandCursor)
    self.palette_list.setStyleSheet(
        "QListWidget { background: transparent; border: none; padding: 2px; }"
        "QScrollBar:horizontal { height: 7px; background: transparent; }"
        "QScrollBar::handle:horizontal { background: palette(mid); border-radius: 3px; min-width: 24px; }"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
    )
    self.palette_list.setMinimumWidth(160)
    self.palette_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.palette_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.palette_list.itemClicked.connect(
        lambda item: self.set_color(QColor(item.data(Qt.ItemDataRole.UserRole)))
    )
    palette_toolbar.addWidget(self.palette_list)
    palette_menu = self.menuBar().addMenu("PALETTE.TITLE")
    for text, callback in [
        ("PALETTE.ADD_COLOR", self.add_swatch),
        ("PALETTE.REMOVE_COLOR", self.remove_swatch),
        ("MENU.LOAD_PALETTE", self.load_palette),
        ("MENU.SAVE_PALETTE", self.save_palette),
    ]:
        self.action(palette_menu, text, callback)
    language_menu = self.menuBar().addMenu("MENU.LANGUAGE")
    language_group = QActionGroup(self)
    language_group.setExclusive(True)
    self.language_actions = {}
    for code, label in SUPPORTED_LANGUAGES.items():
        action = QAction(label, self)
        action.setCheckable(True)
        action.setChecked(code == self._i18n.language)
        action.triggered.connect(lambda checked=False, code=code: self._i18n.set_language(code))
        language_group.addAction(action)
        language_menu.addAction(action)
        self.language_actions[code] = action
    dock.setWidget(panel)
    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    self.tool_status = QLabel()
    self.size_status = QLabel()
    self.zoom_button = QPushButton("100%")
    self.zoom_button.setFlat(True)
    self.zoom_button.setCursor(Qt.CursorShape.PointingHandCursor)
    self.zoom_button.setToolTip("ZOOM.INPUT_HINT")
    self.zoom_button.setAccessibleName("ZOOM.INPUT_ACCESSIBLE_NAME")
    self.zoom_button.clicked.connect(self.edit_zoom)
    self.statusBar().addWidget(self.tool_status, 1)
    self.statusBar().addPermanentWidget(self.size_status)
    self.statusBar().addPermanentWidget(self.zoom_button)
    self.refresh_palette()
    self.set_tool("brush")
