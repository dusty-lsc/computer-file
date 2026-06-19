#!/usr/bin/env python3
"""Restore old photos with gentler processing to avoid artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片: {path}")
    return image


def save_jpeg(path: Path, image: np.ndarray, quality: int = 95) -> None:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError(f"无法保存图片: {path}")
    encoded.tofile(str(path))


def mild_halftone_suppress(gray: np.ndarray) -> np.ndarray:
    """Light frequency suppression for printed dot patterns."""
    f = np.fft.fft2(gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    rows, cols = gray.shape
    crow, ccol = rows // 2, cols // 2
    y, x = np.ogrid[:rows, :cols]
    radius = max(6, min(rows, cols) // 120)
    mask = np.ones((rows, cols), np.float32)

    for dy, dx in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        cy = int(crow + dy * rows * 0.09)
        cx = int(ccol + dx * cols * 0.09)
        dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
        mask[dist <= radius] = 0.55

    restored = np.fft.ifft2(np.fft.ifftshift(fshift * mask))
    out = np.real(restored)
    out = cv2.normalize(out, None, 0, 255, cv2.NORM_MINMAX)
    return out.astype(np.uint8)


def remove_spots_and_scratches(
    gray: np.ndarray, scratch_threshold: int = 215, spot_threshold: int = 22
) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (0, 0), 1.2)
    diff = cv2.absdiff(gray, blur)
    _, spot_mask = cv2.threshold(diff, spot_threshold, 255, cv2.THRESH_BINARY)
    spot_mask = cv2.morphologyEx(spot_mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    bright = cv2.threshold(gray, scratch_threshold, 255, cv2.THRESH_BINARY)[1]
    vert = cv2.morphologyEx(bright, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7)))
    horiz = cv2.morphologyEx(bright, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1)))
    scratch_mask = cv2.bitwise_or(vert, horiz)
    scratch_mask = cv2.dilate(scratch_mask, np.ones((2, 2), np.uint8), iterations=1)

    mask = cv2.bitwise_or(spot_mask, scratch_mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(mask) == 0:
        return gray
    return cv2.inpaint(gray, mask, 2, cv2.INPAINT_TELEA)


def unsharp_mask(image: np.ndarray, amount: float = 0.5, sigma: float = 1.0) -> np.ndarray:
    blurred = cv2.GaussianBlur(image, (0, 0), sigma)
    sharpened = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def apply_sepia(gray: np.ndarray) -> np.ndarray:
    color = np.zeros((gray.shape[0], gray.shape[1], 3), dtype=np.uint8)
    color[:, :, 2] = np.clip(gray.astype(np.int16) * 1.01 + 4, 0, 255).astype(np.uint8)
    color[:, :, 1] = np.clip(gray.astype(np.int16) * 0.97 + 2, 0, 255).astype(np.uint8)
    color[:, :, 0] = np.clip(gray.astype(np.int16) * 0.86, 0, 255).astype(np.uint8)
    return color


def restore_landscape(image: np.ndarray, scale: int = 2) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, h=4, templateWindowSize=7, searchWindowSize=21)
    gray = remove_spots_and_scratches(gray, scratch_threshold=212)
    gray = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8)).apply(gray)
    gray = unsharp_mask(gray, amount=0.45, sigma=1.0)
    if scale > 1:
        gray = cv2.resize(gray, (gray.shape[1] * scale, gray.shape[0] * scale), interpolation=cv2.INTER_LANCZOS4)
        gray = unsharp_mask(gray, amount=0.25, sigma=0.8)
    return apply_sepia(gray)


def restore_portrait(image: np.ndarray, scale: int = 2) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, h=6, templateWindowSize=7, searchWindowSize=21)
    gray = mild_halftone_suppress(gray)
    gray = cv2.bilateralFilter(gray, d=5, sigmaColor=28, sigmaSpace=28)
    gray = remove_spots_and_scratches(gray, scratch_threshold=228, spot_threshold=32)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gray = unsharp_mask(gray, amount=0.55, sigma=1.0)
    if scale > 1:
        gray = cv2.resize(gray, (gray.shape[1] * scale, gray.shape[0] * scale), interpolation=cv2.INTER_LANCZOS4)
        gray = unsharp_mask(gray, amount=0.3, sigma=0.8)
    return apply_sepia(gray)


def main() -> int:
    repo = Path(__file__).resolve().parent
    originals = repo / "originals"
    jobs = [
        ("107a10ee34dfcd943f0c8d1ed954c5cd.jpeg", restore_landscape),
        ("9a60b669b52725aaa1fca70ea928ad65.jpeg", restore_portrait),
    ]

    for name, fn in jobs:
        src = originals / name if (originals / name).exists() else repo / name
        dst = repo / name
        if not src.exists():
            print(f"跳过: {src}", file=sys.stderr)
            continue
        print(f"处理: {name}")
        image = load_image(src)
        print(f"  原始: {image.shape[1]}x{image.shape[0]}")
        restored = fn(image, scale=2)
        print(f"  输出: {restored.shape[1]}x{restored.shape[0]}")
        save_jpeg(dst, restored, quality=95)
        print(f"  已保存: {dst}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
