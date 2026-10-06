"""좌측 이미지 미리보기와 우측 편집 메뉴로 구성된 메인 창."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon
from PyQt5.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from PIL import Image

from canvas import ImageCanvas, pil_to_qpixmap
from image_ops import (
    EditState,
    MosaicRect,
    TextOverlay,
    apply_edits,
    open_image,
    output_size,
    save_image,
    unique_edited_path,
)

IMAGE_FILTER = "이미지 파일 (*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff)"


class TextInputDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("텍스트 입력")
        self.setModal(True)
        self.color = QColor(255, 255, 255)

        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("이미지에 넣을 문구")
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 400)
        self.font_size.setValue(48)

        self.color_btn = QPushButton("색상 선택")
        self.color_btn.clicked.connect(self._pick_color)
        self._refresh_color_btn()

        form = QFormLayout()
        form.addRow("문구", self.text_edit)
        form.addRow("글자 크기", self.font_size)
        form.addRow("색상", self.color_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(360, 160)

    def _refresh_color_btn(self) -> None:
        self.color_btn.setStyleSheet(
            f"background:{self.color.name()}; color:{'#000' if self.color.lightness() > 150 else '#fff'};"
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self.color, self, "텍스트 색상")
        if color.isValid():
            self.color = color
            self._refresh_color_btn()

    def values(self) -> Tuple[str, int, Tuple[int, int, int]]:
        rgb = (self.color.red(), self.color.green(), self.color.blue())
        return self.text_edit.text().strip(), self.font_size.value(), rgb


class SaveWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished_ok = pyqtSignal(int, str)
    failed = pyqtSignal(str)

    def __init__(self, paths: List[str], state: EditState, folder: str, ext: str) -> None:
        super().__init__()
        self.paths = paths
        self.state = state.copy()
        self.folder = folder
        self.ext = ext

    def run(self) -> None:
        saved = 0
        taken: set = set()
        try:
            for index, path in enumerate(self.paths, start=1):
                name = os.path.splitext(os.path.basename(path))[0]
                out_path = unique_edited_path(self.folder, name, self.ext, taken)
                taken.add(os.path.normcase(os.path.abspath(out_path)))
                image = open_image(path)
                result = apply_edits(image, self.state, for_preview=False)
                save_image(result, out_path)
                saved += 1
                self.progress.emit(index, len(self.paths), out_path)
            self.finished_ok.emit(saved, self.folder)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("이미지 크기 · 컬러 조정")
        self.resize(1400, 860)
        self.image_paths: List[str] = []
        self.current_index = 0
        self.state = EditState()
        self._updating_width = False
        self._worker: Optional[SaveWorker] = None
        self._preview_cache: Optional[Image.Image] = None
        self._preview_path: Optional[str] = None
        self._splitter_ready = False

        self.canvas = ImageCanvas()
        self.canvas.mosaicSelected.connect(self._on_mosaic)
        self.canvas.textClicked.connect(self._on_text_click)

        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListWidget.IconMode)
        self.thumbs.setFlow(QListWidget.LeftToRight)
        self.thumbs.setWrapping(False)
        self.thumbs.setMovement(QListWidget.Static)
        self.thumbs.setIconSize(QSize(88, 66))
        self.thumbs.setFixedHeight(102)
        self.thumbs.setSpacing(6)
        self.thumbs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.thumbs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbs.setResizeMode(QListWidget.Adjust)
        self.thumbs.currentRowChanged.connect(self._on_thumb_changed)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.canvas, 1)
        left_layout.addWidget(self.thumbs)

        right = self._build_side_panel()

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 8)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setChildrenCollapsible(False)
        right.setMinimumWidth(280)
        right.setMaximumWidth(420)

        container = QWidget()
        root = QHBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 6)
        root.addWidget(self.splitter)
        self.setCentralWidget(container)

        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("여러 장을 올린 뒤 한 장만 수정하면 같은 설정이 모든 이미지에 적용됩니다.")

        self._apply_style()
        self._set_controls_enabled(False)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._splitter_ready:
            return
        total = max(self.width(), 1)
        self.splitter.setSizes([int(total * 0.8), int(total * 0.2)])
        self._splitter_ready = True

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("편집 메뉴")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.btn_upload = QPushButton("다중 이미지 업로드")
        self.btn_upload.clicked.connect(self._upload_images)
        layout.addWidget(self.btn_upload)

        self.info_label = QLabel("업로드된 이미지 없음")
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("infoLabel")
        layout.addWidget(self.info_label)

        layout.addWidget(self._hline())

        layout.addWidget(QLabel("RGB 컬러 조절"))
        self.slider_r, self.label_r, row_r = self._make_slider("빨강")
        self.slider_g, self.label_g, row_g = self._make_slider("초록")
        self.slider_b, self.label_b, row_b = self._make_slider("파랑")
        for slider, row in (
            (self.slider_r, row_r),
            (self.slider_g, row_g),
            (self.slider_b, row_b),
        ):
            layout.addWidget(row)
            slider.valueChanged.connect(self._on_rgb_changed)

        layout.addWidget(self._hline())

        size_title = QLabel("크기 조정")
        layout.addWidget(size_title)

        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("가로 픽셀"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20000)
        self.width_spin.setValue(800)
        self.width_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        width_row.addWidget(self.width_spin)
        layout.addLayout(width_row)

        self.height_label = QLabel("세로 사이즈: - (자동)")
        self.height_label.setObjectName("autoSize")
        layout.addWidget(self.height_label)

        layout.addWidget(self._hline())

        self.btn_gray = QPushButton("흑백 변환")
        self.btn_gray.setCheckable(True)
        self.btn_gray.toggled.connect(self._on_gray_toggled)
        layout.addWidget(self.btn_gray)

        self.btn_mosaic = QPushButton("모자이크 처리")
        self.btn_mosaic.setCheckable(True)
        self.btn_mosaic.toggled.connect(self._on_mosaic_mode)
        layout.addWidget(self.btn_mosaic)

        self.btn_text = QPushButton("텍스트 입력")
        self.btn_text.setCheckable(True)
        self.btn_text.toggled.connect(self._on_text_mode)
        layout.addWidget(self.btn_text)

        layout.addStretch(1)

        self.btn_save = QPushButton("결과 파일 저장")
        self.btn_save.setObjectName("saveButton")
        self.btn_save.clicked.connect(self._save_results)
        layout.addWidget(self.btn_save)

        hint = QLabel(
            "모자이크: 드래그로 영역 지정\n텍스트: 위치를 클릭 후 문구 입력\n편집은 모든 이미지에 일괄 적용"
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return panel

    def _make_slider(self, name: str) -> Tuple[QSlider, QLabel, QWidget]:
        row = QWidget()
        box = QVBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        header = QHBoxLayout()
        title = QLabel(name)
        value = QLabel("100%")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(title)
        header.addWidget(value)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 200)
        slider.setValue(100)
        box.addLayout(header)
        box.addWidget(slider)
        return slider, value, row

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("line")
        return line

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.slider_r,
            self.slider_g,
            self.slider_b,
            self.width_spin,
            self.btn_gray,
            self.btn_mosaic,
            self.btn_text,
            self.btn_save,
        ):
            widget.setEnabled(enabled)

    def _upload_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "이미지 여러 장 선택", "", IMAGE_FILTER)
        if not paths:
            return
        self.image_paths = paths
        self.current_index = 0
        self.state = EditState()
        self.btn_gray.blockSignals(True)
        self.btn_gray.setChecked(False)
        self.btn_gray.blockSignals(False)
        self.btn_mosaic.setChecked(False)
        self.btn_text.setChecked(False)
        for slider in (self.slider_r, self.slider_g, self.slider_b):
            slider.blockSignals(True)
            slider.setValue(100)
            slider.blockSignals(False)
        self.label_r.setText("100%")
        self.label_g.setText("100%")
        self.label_b.setText("100%")
        self._preview_cache = None
        self._preview_path = None
        self._fill_thumbs()
        self._set_controls_enabled(True)
        self._load_current(reset_width=True)
        self.statusBar().showMessage(f"{len(paths)}장 업로드됨. 한 장의 수정이 모든 이미지에 동일하게 적용됩니다.")

    def _fill_thumbs(self) -> None:
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for path in self.image_paths:
            item = QListWidgetItem(os.path.basename(path))
            try:
                with Image.open(path) as raw:
                    thumb = raw.convert("RGB")
                    thumb.thumbnail((176, 132))
                    pix = pil_to_qpixmap(thumb)
                    item.setIcon(QIcon(pix))
            except Exception:
                item.setIcon(QIcon())
            item.setToolTip(path)
            self.thumbs.addItem(item)
        if self.image_paths:
            self.thumbs.setCurrentRow(0)
        self.thumbs.blockSignals(False)

    def _on_thumb_changed(self, row: int) -> None:
        if 0 <= row < len(self.image_paths):
            self.current_index = row
            self._load_current(reset_width=False)

    def _current_path(self) -> Optional[str]:
        if 0 <= self.current_index < len(self.image_paths):
            return self.image_paths[self.current_index]
        return None

    def _original(self) -> Optional[Image.Image]:
        path = self._current_path()
        if not path:
            return None
        if self._preview_path != path or self._preview_cache is None:
            self._preview_cache = open_image(path)
            self._preview_path = path
        return self._preview_cache

    def _load_current(self, reset_width: bool) -> None:
        image = self._original()
        if image is None:
            self.canvas.set_image(None)
            return
        if reset_width:
            self._updating_width = True
            self.width_spin.setValue(image.size[0])
            self.state.target_width = None
            self._updating_width = False
        self._update_height_label()
        self._refresh_preview()
        name = os.path.basename(self._current_path() or "")
        self.info_label.setText(f"{self.current_index + 1} / {len(self.image_paths)}\n{name}")

    def _update_height_label(self) -> None:
        image = self._original()
        if image is None:
            self.height_label.setText("세로 사이즈: - (자동)")
            return
        width = self.width_spin.value()
        _, height = output_size(image.size, width)
        self.height_label.setText(f"세로 사이즈: {height} px (자동)")

    def _refresh_preview(self) -> None:
        image = self._original()
        if image is None:
            self.canvas.set_image(None)
            return
        preview = apply_edits(image, self.state, for_preview=True)
        self.canvas.set_image(preview)

    def _on_rgb_changed(self) -> None:
        self.state.r = self.slider_r.value() / 100.0
        self.state.g = self.slider_g.value() / 100.0
        self.state.b = self.slider_b.value() / 100.0
        self.label_r.setText(f"{self.slider_r.value()}%")
        self.label_g.setText(f"{self.slider_g.value()}%")
        self.label_b.setText(f"{self.slider_b.value()}%")
        self._refresh_preview()

    def _on_width_changed(self, value: int) -> None:
        if self._updating_width:
            self._update_height_label()
            return
        self.state.target_width = value
        self._update_height_label()
        self.statusBar().showMessage(f"가로 {value}px로 모든 이미지를 리사이즈합니다. 세로는 각 이미지 비율로 자동 계산됩니다.")

    def _on_gray_toggled(self, checked: bool) -> None:
        self.state.grayscale = checked
        self.btn_gray.setText("흑백 변환 해제" if checked else "흑백 변환")
        self._refresh_preview()

    def _on_mosaic_mode(self, checked: bool) -> None:
        if checked:
            self.btn_text.blockSignals(True)
            self.btn_text.setChecked(False)
            self.btn_text.blockSignals(False)
            self.canvas.set_mode("mosaic")
            self.statusBar().showMessage("모자이크할 영역을 드래그하세요. 상대 위치가 다른 이미지에도 동일하게 적용됩니다.")
        else:
            if not self.btn_text.isChecked():
                self.canvas.set_mode("view")

    def _on_text_mode(self, checked: bool) -> None:
        if checked:
            self.btn_mosaic.blockSignals(True)
            self.btn_mosaic.setChecked(False)
            self.btn_mosaic.blockSignals(False)
            self.canvas.set_mode("text")
            self.statusBar().showMessage("텍스트를 넣을 위치를 클릭하세요.")
        else:
            if not self.btn_mosaic.isChecked():
                self.canvas.set_mode("view")

    def _on_mosaic(self, x: float, y: float, w: float, h: float) -> None:
        self.state.mosaics.append(MosaicRect(x, y, w, h))
        self._refresh_preview()

    def _on_text_click(self, x: float, y: float) -> None:
        dialog = TextInputDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        text, font_px, color = dialog.values()
        if not text:
            return
        image = self._original()
        width = image.size[0] if image else 1000
        ratio = font_px / max(width, 1)
        self.state.texts.append(TextOverlay(x, y, text, ratio, color))
        self._refresh_preview()

    def _save_results(self) -> None:
        if not self.image_paths:
            return
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if not folder:
            return

        picker = QDialog(self)
        picker.setWindowTitle("저장 형식")
        combo = QComboBox()
        combo.addItem("JPEG (*.jpg)", ".jpg")
        combo.addItem("PNG (*.png)", ".png")
        combo.addItem("GIF (*.gif)", ".gif")
        combo.addItem("BMP (*.bmp)", ".bmp")
        form = QFormLayout(picker)
        form.addRow("파일 형식", combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(picker.accept)
        buttons.rejected.connect(picker.reject)
        form.addRow(buttons)
        if picker.exec_() != QDialog.Accepted:
            return

        ext = combo.currentData()
        self.btn_save.setEnabled(False)
        self._worker = SaveWorker(self.image_paths, self.state, folder, ext)
        self._worker.progress.connect(
            lambda i, n, p: self.statusBar().showMessage(f"저장 중 {i}/{n}: {os.path.basename(p)}")
        )
        self._worker.finished_ok.connect(self._on_saved)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_saved(self, count: int, folder: str) -> None:
        self.btn_save.setEnabled(True)
        self.statusBar().showMessage(f"{count}장 저장 완료: {folder}")
        QMessageBox.information(self, "저장 완료", f"{count}장의 결과를 저장했습니다.\n{folder}")

    def _on_save_failed(self, message: str) -> None:
        self.btn_save.setEnabled(True)
        QMessageBox.critical(self, "저장 실패", message)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #111111; }
            QWidget#sidePanel {
                background: #1c1c1c;
                border: 1px solid #2c2c2c;
                border-radius: 8px;
            }
            QLabel { color: #e8e8e8; }
            QLabel#panelTitle { font-size: 16px; font-weight: 700; padding-bottom: 4px; }
            QLabel#infoLabel { color: #b5b5b5; }
            QLabel#autoSize { color: #8fd3ff; }
            QLabel#hintLabel { color: #8a8a8a; font-size: 11px; }
            QFrame#line { color: #333; }
            QPushButton {
                background: #2b2b2b;
                color: #f2f2f2;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 9px 10px;
                text-align: center;
            }
            QPushButton:hover { background: #3a3a3a; }
            QPushButton:checked { background: #0d5cad; border-color: #4da3ff; }
            QPushButton#saveButton { background: #0f6d3f; border-color: #1d8a54; font-weight: 700; }
            QPushButton#saveButton:hover { background: #148553; }
            QPushButton:disabled { color: #777; background: #222; }
            QSlider::groove:horizontal { height: 6px; background: #333; border-radius: 3px; }
            QSlider::handle:horizontal {
                width: 14px; height: 14px; margin: -5px 0;
                background: #4da3ff; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #4da3ff; border-radius: 3px; }
            QSpinBox, QLineEdit, QComboBox {
                background: #111; color: #fff; border: 1px solid #444;
                border-radius: 4px; padding: 4px 6px;
            }
            QListWidget {
                background: #151515; border: 1px solid #2a2a2a; color: #ddd;
            }
            QStatusBar { color: #bbb; background: #0d0d0d; }
            """
        )
        font = QFont("Malgun Gothic", 10)
        self.setFont(font)
