"""이미지 편집 상태와 PIL 기반 처리 로직."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont, ImageOps

RGB = Tuple[int, int, int]


def _clamp_byte(value: int) -> int:
    return max(0, min(255, value))


def korean_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
    fonts_dir = os.path.join(windir, "Fonts")
    bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    candidates = [
        os.path.join(bundled, "malgun.ttf"),
        os.path.join(fonts_dir, "malgun.ttf"),
        os.path.join(fonts_dir, "malgunbd.ttf"),
        os.path.join(fonts_dir, "gulim.ttc"),
        os.path.join(fonts_dir, "arial.ttf"),
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


@dataclass
class MosaicRect:
    x: float
    y: float
    w: float
    h: float


@dataclass
class TextOverlay:
    x: float
    y: float
    text: str
    font_ratio: float
    color: RGB = (255, 255, 255)


@dataclass
class EditState:
    r: float = 1.0
    g: float = 1.0
    b: float = 1.0
    grayscale: bool = False
    target_width: Optional[int] = None
    mosaics: List[MosaicRect] = field(default_factory=list)
    texts: List[TextOverlay] = field(default_factory=list)

    def copy(self) -> "EditState":
        return EditState(
            r=self.r,
            g=self.g,
            b=self.b,
            grayscale=self.grayscale,
            target_width=self.target_width,
            mosaics=[MosaicRect(m.x, m.y, m.w, m.h) for m in self.mosaics],
            texts=[
                TextOverlay(t.x, t.y, t.text, t.font_ratio, t.color) for t in self.texts
            ],
        )


def open_image(path: str) -> Image.Image:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def output_size(original_size: Tuple[int, int], target_width: Optional[int]) -> Tuple[int, int]:
    width, height = original_size
    if not target_width:
        return width, height
    new_height = max(1, round(target_width * height / max(width, 1)))
    return target_width, new_height


def adjust_rgb(image: Image.Image, r_gain: float, g_gain: float, b_gain: float) -> Image.Image:
    if r_gain == 1.0 and g_gain == 1.0 and b_gain == 1.0:
        return image
    red, green, blue = image.split()
    red = red.point([_clamp_byte(int(i * r_gain)) for i in range(256)])
    green = green.point([_clamp_byte(int(i * g_gain)) for i in range(256)])
    blue = blue.point([_clamp_byte(int(i * b_gain)) for i in range(256)])
    return Image.merge("RGB", (red, green, blue))


def apply_mosaic(image: Image.Image, rect: MosaicRect, block: int = 16) -> Image.Image:
    width, height = image.size
    block = max(8, min(width, height) // 40)
    x1 = int(max(0, min(width, round(rect.x * width))))
    y1 = int(max(0, min(height, round(rect.y * height))))
    x2 = int(max(0, min(width, round((rect.x + rect.w) * width))))
    y2 = int(max(0, min(height, round((rect.y + rect.h) * height))))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return image

    region = image.crop((x1, y1, x2, y2))
    rw, rh = region.size
    small_w = max(1, rw // block)
    small_h = max(1, rh // block)
    mosaic = region.resize((small_w, small_h), Image.BILINEAR).resize((rw, rh), Image.NEAREST)
    image.paste(mosaic, (x1, y1))
    return image


def apply_text(image: Image.Image, overlay: TextOverlay) -> Image.Image:
    width, height = image.size
    size = max(10, int(overlay.font_ratio * width))
    font = korean_font(size)
    x = int(overlay.x * width)
    y = int(overlay.y * height)
    draw = ImageDraw.Draw(image)

    outline = (0, 0, 0)
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            if dx or dy:
                draw.text((x + dx, y + dy), overlay.text, font=font, fill=outline)
    draw.text((x, y), overlay.text, font=font, fill=overlay.color)
    return image


def apply_edits(
    image: Image.Image,
    state: EditState,
    *,
    for_preview: bool = False,
    preview_max: int = 1400,
) -> Image.Image:
    result = image.convert("RGB")

    if for_preview:
        width, height = result.size
        longest = max(width, height, 1)
        if longest > preview_max:
            scale = preview_max / longest
            result = result.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.BILINEAR,
            )
    elif state.target_width:
        result = result.resize(output_size(result.size, state.target_width), Image.LANCZOS)

    result = adjust_rgb(result, state.r, state.g, state.b)
    if state.grayscale:
        result = ImageOps.grayscale(result).convert("RGB")

    for mosaic in state.mosaics:
        result = apply_mosaic(result, mosaic)
    for overlay in state.texts:
        result = apply_text(result, overlay)
    return result


def unique_edited_path(
    folder: str,
    stem: str,
    ext: str,
    taken: Optional[set] = None,
) -> str:
    """기존 파일과 이번 저장에서 이미 쓴 이름을 피해 *_edited, *_edited_1 ... 경로를 만든다."""
    reserved = taken if taken is not None else set()
    if not ext.startswith("."):
        ext = f".{ext}"

    def is_taken(path: str) -> bool:
        abs_path = os.path.normcase(os.path.abspath(path))
        return os.path.exists(path) or abs_path in reserved

    candidate = os.path.join(folder, f"{stem}_edited{ext}")
    if not is_taken(candidate):
        return candidate
    index = 1
    while True:
        candidate = os.path.join(folder, f"{stem}_edited_{index}{ext}")
        if not is_taken(candidate):
            return candidate
        index += 1


def save_image(image: Image.Image, path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".jpg", ".jpeg"}:
        image.convert("RGB").save(path, format="JPEG", quality=95, optimize=True)
        return
    if ext == ".gif":
        image.convert("P", palette=Image.ADAPTIVE).save(path, format="GIF")
        return
    image.save(path)
