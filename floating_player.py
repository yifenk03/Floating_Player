#!/usr/bin/env python3
"""
漂浮置顶无边框视频播放器
支持 MP4, MKV, GIF 等格式
支持拖放文件、自动播放列表、音频设备选择
"""

import sys
import os

# ===================== 核心配置 =====================
WINDOW_ROUND_RADIUS = 4
SUPPORT_FORMATS = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.gif', '.wmv', '.flv', '.ts', '.m2ts']
AUTO_HIDE_DELAY = 1500

os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'PassThrough'

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QSlider, QPushButton, QLabel, QFileDialog, QListWidget,
    QMenu, QAction, QStyle, QListWidgetItem, QAbstractItemView,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import QTimer, QUrl, QPoint, QRectF
from PyQt5.QtGui import QIcon, QDragEnterEvent, QDropEvent, QMouseEvent

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

try:
    from PyQt5.QtMultimedia import QAudioOutputSelectorControl
    HAS_AUDIO_SELECTOR = True
except ImportError:
    HAS_AUDIO_SELECTOR = False

from PyQt5.QtMultimediaWidgets import QVideoWidget


class PlaylistWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setFixedWidth(600)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("""
            QWidget {
                background: rgba(30, 30, 30, 0.98);
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet("background: rgba(40, 40, 40, 0.98);")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 5, 0)

        header_label = QLabel("播放列表")
        header_label.setStyleSheet("color: white; font-size: 12px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                color: white; font-size: 12px; border: none;
                border-radius: 3px; background: transparent;
            }
            QPushButton:hover { background-color: rgba(255, 0, 0, 0.6); }
        """)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        self.playlist_panel = QListWidget()
        self.playlist_panel.setDragDropMode(QAbstractItemView.InternalMove)
        self.playlist_panel.setSelectionMode(QAbstractItemView.SingleSelection)
        self.playlist_panel.setStyleSheet("""
            QListWidget {
                background: rgba(30, 30, 30, 0.98);
                color: white;
                border: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            QListWidget::item:selected {
                background: rgba(59, 130, 246, 0.5);
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        layout.addWidget(self.playlist_panel)

    def position_next_to(self, parent_widget):
        parent_geo = parent_widget.geometry()
        parent_right = parent_geo.right()
        screen = QApplication.screenAt(parent_geo.center())
        if screen:
            screen_geo = screen.availableGeometry()
            if parent_right + self.width() > screen_geo.right():
                self.move(parent_geo.left() - self.width(), parent_geo.top())
            else:
                self.move(parent_right, parent_geo.top())
        else:
            self.move(parent_right, parent_geo.top())
        # 确保播放列表在主窗口上方
        self.raise_()


class FloatingVideoPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.resize(960, 540)

        self.dragging = False
        self.resizing = False
        self.drag_pos = QPoint()
        self.resize_edge = None
        self.RESIZE_MARGIN = 8
        self.is_maximized = False

        self.playlist = []
        self.current_index = -1
        self.video_aspect_ratio = None

        self.player = QMediaPlayer()

        self.audio_output_control = None
        if HAS_AUDIO_SELECTOR:
            try:
                svc = self.player.service()
                if svc:
                    self.audio_output_control = svc.requestControl(
                        'org.qt-project.qt.audiooutputselectorcontrol/5.0'
                    )
            except Exception:
                self.audio_output_control = None

        self.hide_timer = QTimer()
        self.hide_timer.setInterval(AUTO_HIDE_DELAY)
        self.hide_timer.timeout.connect(self.hide_controls)

        self.init_ui()
        self.setAcceptDrops(True)
        self.set_rounded_window()

    def set_rounded_window(self):
        from PyQt5.QtGui import QPainterPath, QRegion
        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, WINDOW_ROUND_RADIUS, WINDOW_ROUND_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black; border-radius: 4px;")
        self.player.setVideoOutput(self.video_widget)
        main_layout.addWidget(self.video_widget)

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.mediaStatusChanged.connect(self.media_status_changed)

        self.control_panel = QWidget()
        self.control_panel.setFixedHeight(60)
        self.control_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 0.9);
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }
        """)
        control_layout = QHBoxLayout(self.control_panel)
        control_layout.setContentsMargins(5, 2, 5, 2)
        control_layout.setSpacing(2)

        self.open_btn = QPushButton("📂")
        self.open_btn.setFixedSize(28, 28)
        self.open_btn.setStyleSheet("""
            QPushButton {
                color: white; font-size: 14px; border: none;
                padding: 2px; border-radius: 3px; background: transparent;
            }
            QPushButton:hover { background-color: rgba(80, 80, 80, 0.8); }
        """)
        self.open_btn.clicked.connect(self.open_files)
        control_layout.addWidget(self.open_btn)

        self.prev_btn = QPushButton("⏮")
        self.play_btn = QPushButton("▶")
        self.next_btn = QPushButton("⏭")
        self.prev_btn.setFixedSize(28, 28)
        self.play_btn.setFixedSize(28, 28)
        self.next_btn.setFixedSize(28, 28)

        btn_style = """
            QPushButton {
                color: white; font-size: 12px; border: none;
                padding: 2px; border-radius: 3px; background: transparent;
            }
            QPushButton:hover { background-color: rgba(80, 80, 80, 0.8); }
        """
        self.prev_btn.setStyleSheet(btn_style)
        self.play_btn.setStyleSheet(btn_style)
        self.next_btn.setStyleSheet(btn_style)

        self.prev_btn.clicked.connect(self.prev_video)
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn.clicked.connect(self.next_video)

        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.next_btn)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #555; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: white; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }
            QSlider::sub-page:horizontal { background: #3b82f6; }
        """)
        self.progress_slider.sliderMoved.connect(self.set_position)
        control_layout.addWidget(self.progress_slider)

        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setFixedSize(28, 28)
        self.volume_btn.setStyleSheet(btn_style)
        self.volume_btn.clicked.connect(self.toggle_mute)
        control_layout.addWidget(self.volume_btn)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setFixedWidth(40)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #555; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: white; width: 8px; height: 8px; margin: -2px 0; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: white; }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        control_layout.addWidget(self.volume_slider)

        self.playlist_btn = QPushButton("📋")
        self.playlist_btn.setFixedSize(28, 28)
        self.playlist_btn.setStyleSheet(btn_style)
        self.playlist_btn.clicked.connect(self.toggle_playlist)
        control_layout.addWidget(self.playlist_btn)

        self.minimize_btn = QPushButton("─")
        self.minimize_btn.setFixedSize(28, 28)
        self.minimize_btn.setStyleSheet(btn_style)
        self.minimize_btn.clicked.connect(self.showMinimized)
        control_layout.addWidget(self.minimize_btn)

        main_layout.addWidget(self.control_panel)
        self.setLayout(main_layout)

        self.playlist_window = PlaylistWindow(self)
        self.playlist_window.playlist_panel.itemDoubleClicked.connect(self.playlist_item_clicked)

    # ===================== 播放列表 =====================
    def toggle_playlist(self):
        if self.playlist_window.isVisible():
            self.playlist_window.hide()
        else:
            self.update_playlist_panel()
            self.playlist_window.position_next_to(self)
            self.playlist_window.show()

    def update_playlist_panel(self):
        self.playlist_window.playlist_panel.clear()
        for i, item_data in enumerate(self.playlist):
            duration = item_data.get('duration', 0)
            duration_str = self.format_time(duration) if duration > 0 else ""
            display_text = f"{'▶ ' if i == self.current_index else '  '}{item_data['name']}"
            if duration_str:
                display_text += f"  [{duration_str}]"
            self.playlist_window.playlist_panel.addItem(display_text)
        if 0 <= self.current_index < self.playlist_window.playlist_panel.count():
            self.playlist_window.playlist_panel.setCurrentRow(self.current_index)

    def playlist_item_clicked(self, item):
        index = self.playlist_window.playlist_panel.row(item)
        self.play_index(index)

    # ===================== 播放控制 =====================
    def toggle_play(self):
        if not self.playlist:
            self.open_files()
            return

        if self.player.state() == QMediaPlayer.State.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            if self.current_index == -1:
                self.current_index = 0
                self.play_index(0)
            else:
                self.player.play()
            self.play_btn.setText("⏸")

    def prev_video(self):
        if not self.playlist:
            return
        self.current_index = max(0, self.current_index - 1)
        self.play_index(self.current_index)

    def next_video(self):
        if not self.playlist:
            return
        self.current_index += 1
        if self.current_index >= len(self.playlist):
            self.current_index = 0
        self.play_index(self.current_index)

    def play_index(self, index):
        if index < 0 or index >= len(self.playlist):
            return

        self.current_index = index
        file_path = self.playlist[index]['path']
        url = QUrl.fromLocalFile(file_path)
        self.player.setMedia(QMediaContent(url))
        self.player.play()
        self.play_btn.setText("⏸")
        self.update_playlist_panel()

    def position_changed(self, position):
        self.progress_slider.setValue(position)

    def duration_changed(self, duration):
        self.progress_slider.setRange(0, duration)

        if self.current_index >= 0 and self.current_index < len(self.playlist):
            self.playlist[self.current_index]['duration'] = duration
            self.update_playlist_item(self.current_index)

    def media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_video()

    def set_position(self, position):
        self.player.setPosition(position)

    def set_volume(self, value):
        self.player.setVolume(value)
        self.update_mute_icon()

    def toggle_mute(self):
        muted = self.player.isMuted()
        self.player.setMuted(not muted)
        self.update_mute_icon()

    def update_mute_icon(self):
        is_muted = self.player.isMuted()
        volume = self.volume_slider.value()

        if is_muted or volume == 0:
            self.volume_btn.setText("🔇")
        else:
            self.volume_btn.setText("🔊")

    def format_time(self, ms):
        if ms <= 0:
            return "0:00"
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    # ===================== 文件操作 =====================
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = []
        for url in e.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in SUPPORT_FORMATS:
                    files.append(file_path)

        if files:
            self.add_files_to_playlist(files)

    def add_files_to_playlist(self, files):
        for file_path in files:
            file_name = os.path.basename(file_path)
            item_data = {
                'path': file_path,
                'duration': 0,
                'name': file_name
            }
            self.playlist.append(item_data)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, len(self.playlist) - 1)
            self.update_playlist_item(len(self.playlist) - 1, item)
            self.playlist_window.playlist_panel.addItem(item)

        if self.current_index == -1 and len(files) > 0:
            self.play_index(0)

    def update_playlist_item(self, index, item=None):
        if index < 0 or index >= len(self.playlist):
            return

        item_data = self.playlist[index]
        duration = item_data.get('duration', 0)
        duration_str = self.format_time(duration) if duration > 0 else ""

        display_text = f"{item_data['name']}"
        if duration_str:
            display_text += f"  [{duration_str}]"

        if item is None:
            item = self.playlist_window.playlist_panel.item(index)
        if item:
            item.setText(display_text)

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm *.gif *.wmv *.flv *.ts *.m2ts);;所有文件 (*)"
        )
        if files:
            self.add_files_to_playlist(files)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            files = []
            for file in os.listdir(folder):
                file_path = os.path.join(folder, file)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in SUPPORT_FORMATS:
                        files.append(file_path)
            if files:
                self.add_files_to_playlist(files)

    # ===================== 右键菜单 =====================
    def contextMenuEvent(self, e):
        menu = QMenu(self)

        add_file_action = QAction("添加文件", self)
        add_file_action.triggered.connect(self.open_files)
        menu.addAction(add_file_action)

        add_folder_action = QAction("添加文件夹", self)
        add_folder_action.triggered.connect(self.open_folder)
        menu.addAction(add_folder_action)

        menu.addSeparator()

        ratio_menu = QMenu("视频比例", self)
        ratio_16_9_action = QAction("16:9 横向", self)
        ratio_16_9_action.triggered.connect(lambda: self.set_video_ratio(16, 9))
        ratio_menu.addAction(ratio_16_9_action)

        ratio_9_16_action = QAction("9:16 竖向", self)
        ratio_9_16_action.triggered.connect(lambda: self.set_video_ratio(9, 16))
        ratio_menu.addAction(ratio_9_16_action)

        ratio_4_3_action = QAction("4:3 经典", self)
        ratio_4_3_action.triggered.connect(lambda: self.set_video_ratio(4, 3))
        ratio_menu.addAction(ratio_4_3_action)

        ratio_original_action = QAction("原始比例", self)
        ratio_original_action.triggered.connect(self.set_original_ratio)
        ratio_menu.addAction(ratio_original_action)

        menu.addMenu(ratio_menu)

        menu.addSeparator()

        audio_menu = QMenu("音频输出设备", self)

        if self.audio_output_control:
            try:
                outputs = self.audio_output_control.availableOutputs()
                if outputs:
                    for output_name in outputs:
                        desc = self.audio_output_control.outputDescription(output_name)
                        action = QAction(desc, self)
                        action.setData(output_name)
                        action.triggered.connect(
                            lambda checked, name=output_name: self.change_audio_device(name)
                        )
                        audio_menu.addAction(action)
                    menu.addMenu(audio_menu)
                else:
                    no_device_action = QAction("（未检测到设备）", self)
                    no_device_action.setEnabled(False)
                    audio_menu.addAction(no_device_action)
                    menu.addMenu(audio_menu)
            except Exception:
                no_device_action = QAction("（音频设备不可用）", self)
                no_device_action.setEnabled(False)
                audio_menu.addAction(no_device_action)
                menu.addMenu(audio_menu)
        else:
            no_device_action = QAction("（不支持）", self)
            no_device_action.setEnabled(False)
            audio_menu.addAction(no_device_action)
            menu.addMenu(audio_menu)

        menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit_app)
        menu.addAction(exit_action)

        menu.exec(e.globalPos())

    def change_audio_device(self, device_name):
        if self.audio_output_control:
            try:
                self.audio_output_control.setActiveOutput(device_name)
            except Exception:
                pass

    def quit_app(self):
        """彻底退出应用程序"""
        self.player.stop()
        QApplication.quit()

    def set_video_ratio(self, width, height):
        current_width = self.width()
        new_height = int(current_width * height / width)
        self.resize(current_width, new_height)
        self.set_rounded_window()

    def set_original_ratio(self):
        if self.video_aspect_ratio:
            width, height = self.video_aspect_ratio
            self.set_video_ratio(width, height)

    # ===================== 控制栏显示/隐藏 =====================
    def enterEvent(self, e):
        self.control_panel.show()
        self.hide_timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self.playlist_window.isVisible():
            self.hide_timer.start()
        super().leaveEvent(e)

    def hide_controls(self):
        self.control_panel.hide()

    # ===================== 无边框窗口拖动和调整大小 =====================
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.pos()

            if pos.x() < self.RESIZE_MARGIN and pos.y() < self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'top-left'
            elif pos.x() > self.width() - self.RESIZE_MARGIN and pos.y() < self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'top-right'
            elif pos.x() < self.RESIZE_MARGIN and pos.y() > self.height() - self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'bottom-left'
            elif pos.x() > self.width() - self.RESIZE_MARGIN and pos.y() > self.height() - self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'bottom-right'
            elif pos.y() < self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'top'
            elif pos.y() > self.height() - self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'bottom'
            elif pos.x() < self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'left'
            elif pos.x() > self.width() - self.RESIZE_MARGIN:
                self.resizing = True
                self.resize_edge = 'right'
            else:
                self.dragging = True
                self.drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self.resizing:
            global_pos = e.globalPos()
            rect = self.frameGeometry()

            min_width = 320
            min_height = 180

            if self.resize_edge == 'top-left':
                new_width = rect.right() - global_pos.x()
                new_height = rect.bottom() - global_pos.y()
                if new_width > min_width and new_height > min_height:
                    self.setGeometry(global_pos.x(), global_pos.y(), new_width, new_height)
            elif self.resize_edge == 'top-right':
                new_width = global_pos.x() - rect.left()
                new_height = rect.bottom() - global_pos.y()
                if new_width > min_width and new_height > min_height:
                    self.setGeometry(rect.left(), global_pos.y(), new_width, new_height)
            elif self.resize_edge == 'bottom-left':
                new_width = rect.right() - global_pos.x()
                new_height = global_pos.y() - rect.top()
                if new_width > min_width and new_height > min_height:
                    self.setGeometry(global_pos.x(), rect.top(), new_width, new_height)
            elif self.resize_edge == 'bottom-right':
                new_width = global_pos.x() - rect.left()
                new_height = global_pos.y() - rect.top()
                if new_width > min_width and new_height > min_height:
                    self.setGeometry(rect.left(), rect.top(), new_width, new_height)
            elif self.resize_edge == 'top':
                new_height = rect.bottom() - global_pos.y()
                if new_height > min_height:
                    self.setGeometry(rect.left(), global_pos.y(), rect.width(), new_height)
            elif self.resize_edge == 'bottom':
                new_height = global_pos.y() - rect.top()
                if new_height > min_height:
                    self.setGeometry(rect.left(), rect.top(), rect.width(), new_height)
            elif self.resize_edge == 'left':
                new_width = rect.right() - global_pos.x()
                if new_width > min_width:
                    self.setGeometry(global_pos.x(), rect.top(), new_width, rect.height())
            elif self.resize_edge == 'right':
                new_width = global_pos.x() - rect.left()
                if new_width > min_width:
                    self.setGeometry(rect.left(), rect.top(), new_width, rect.height())
            e.accept()
        elif self.dragging:
            self.move(e.globalPos() - self.drag_pos)
            e.accept()
        else:
            pos = e.pos()
            if (pos.x() < self.RESIZE_MARGIN or pos.x() > self.width() - self.RESIZE_MARGIN or
                pos.y() < self.RESIZE_MARGIN or pos.y() > self.height() - self.RESIZE_MARGIN):
                if pos.x() < self.RESIZE_MARGIN and pos.y() < self.RESIZE_MARGIN:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif pos.x() > self.width() - self.RESIZE_MARGIN and pos.y() < self.RESIZE_MARGIN:
                    self.setCursor(Qt.SizeBDiagCursor)
                elif pos.x() < self.RESIZE_MARGIN and pos.y() > self.height() - self.RESIZE_MARGIN:
                    self.setCursor(Qt.SizeBDiagCursor)
                elif pos.x() > self.width() - self.RESIZE_MARGIN and pos.y() > self.height() - self.RESIZE_MARGIN:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif pos.y() < self.RESIZE_MARGIN or pos.y() > self.height() - self.RESIZE_MARGIN:
                    self.setCursor(Qt.SizeVerCursor)
                elif pos.x() < self.RESIZE_MARGIN or pos.x() > self.width() - self.RESIZE_MARGIN:
                    self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
        self.setCursor(Qt.ArrowCursor)

    def resizeEvent(self, e):
        self.set_rounded_window()
        super().resizeEvent(e)

    def moveEvent(self, e):
        if hasattr(self, 'playlist_window') and self.playlist_window.isVisible():
            self.playlist_window.position_next_to(self)
        super().moveEvent(e)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Space:
            self.toggle_play()
        elif key == Qt.Key_Left:
            pos = self.player.position()
            self.player.setPosition(max(0, pos - 10000))
        elif key == Qt.Key_Right:
            pos = self.player.position()
            self.player.setPosition(min(self.player.duration(), pos + 10000))
        elif key == Qt.Key_Up:
            vol = self.volume_slider.value()
            self.volume_slider.setValue(min(100, vol + 5))
            self.set_volume(min(100, vol + 5))
        elif key == Qt.Key_Down:
            vol = self.volume_slider.value()
            self.volume_slider.setValue(max(0, vol - 5))
            self.set_volume(max(0, vol - 5))
        elif key == Qt.Key_M:
            self.toggle_mute()
        elif key == Qt.Key_O:
            self.open_files()
        elif key == Qt.Key_Escape:
            if self.playlist_window.isVisible():
                self.playlist_window.hide()
            else:
                self.close()
        else:
            super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("漂浮视频播放器")

    player = FloatingVideoPlayer()
    player.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
