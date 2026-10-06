"""이미지를 표시하고 모자이크 드래그 / 텍스트 클릭을 받는 캔버스."""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget
from PIL import Image


def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    rgb = image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimage = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())


class ImageCanvas(QWidget):
    mosaicSelected = pyqtSignal(float, float, float, float)
    textClicked = pyqtSignal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)
        self._pixmap: Optional[QPixmap] = None
        self._mode = "view"
        self._drag_start: Optional[QPoint] = None
        self._drag_end: Optional[QPoint] = None
        self._image_rect = QRect()
        self.setCursor(Qt.ArrowCursor)

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._drag_start = None
        self._drag_end = None
        if mode == "mosaic":
            self.setCursor(Qt.CrossCursor)
        elif mode == "text":
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def mode(self) -> str:
        return self._mode

    def set_image(self, image: Optional[Image.Image]) -> None:
        self._pixmap = pil_to_qpixmap(image) if image is not None else None
        self._drag_start = None
        self._drag_end = None
        self.update()

    def _fit_rect(self) -> QRect:
        if self._pixmap is None or self._pixmap.isNull():
            return QRect()
        area = self.rect().adjusted(16, 16, -16, -16)
        scaled = self._pixmap.size().scaled(area.size(), Qt.KeepAspectRatio)
        x = area.x() + (area.width() - scaled.width()) // 2
        y = area.y() + (area.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _rel_pos(self, pos: QPoint) -> Optional[Tuple[float, float]]:
        if self._image_rect.isNull() or not self._image_rect.contains(pos):
            return None
        x = (pos.x() - self._image_rect.x()) / max(self._image_rect.width(), 1)
        y = (pos.y() - self._image_rect.y()) / max(self._image_rect.height(), 1)
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141414"))
        self._image_rect = self._fit_rect()

        if self._pixmap is None:
            painter.setPen(QColor("#888888"))
            painter.drawText(self.rect(), Qt.AlignCenter, "이미지를 업로드하세요")
            return

        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(self._image_rect, self._pixmap)

        if self._mode in {"mosaic", "text"}:
            painter.setPen(QPen(QColor("#4da3ff"), 1, Qt.DashLine))
            painter.drawRect(self._image_rect.adjusted(0, 0, -1, -1))

        if self._mode == "mosaic" and self._drag_start and self._drag_end:
            select = QRect(self._drag_start, self._drag_end).normalized()
            select = select.intersected(self._image_rect)
            painter.fillRect(select, QColor(255, 220, 0, 60))
            painter.setPen(QPen(QColor("#ffd400"), 2))
            painter.drawRect(select)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or self._pixmap is None:
            return
        if self._mode == "mosaic":
            if self._image_rect.contains(event.pos()):
                self._drag_start = event.pos()
                self._drag_end = event.pos()
                self.update()
        elif self._mode == "text":
            rel = self._rel_pos(event.pos())
            if rel:
                self.textClicked.emit(*rel)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._mode == "mosaic" and self._drag_start is not None:
            self._drag_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or self._mode != "mosaic":
            return
        if self._drag_start is None or self._drag_end is None:
            return
        select = QRect(self._drag_start, self._drag_end).normalized().intersected(self._image_rect)
        self._drag_start = None
        self._drag_end = None
        self.update()
        if select.width() < 6 or select.height() < 6:
            return
        x = (select.x() - self._image_rect.x()) / max(self._image_rect.width(), 1)
        y = (select.y() - self._image_rect.y()) / max(self._image_rect.height(), 1)
        w = select.width() / max(self._image_rect.width(), 1)
        h = select.height() / max(self._image_rect.height(), 1)
        self.mosaicSelected.emit(x, y, w, h)
