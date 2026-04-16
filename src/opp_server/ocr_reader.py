"""
ocr_reader.py — captures screen text using Apple Vision framework (macOS native OCR).

No external API. Works on any visible window content including browser pages.
Requires: System Settings → Privacy & Security → Screen Recording → enable Terminal/IDE.
"""
from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

if sys.platform != "darwin":
    raise RuntimeError("ocr_reader requires macOS")

import Quartz
import Vision  # type: ignore[import]
import Cocoa   # type: ignore[import]


def _screenshot_window_region(pid: int) -> Path | None:
    """
    Screenshot the main window of *pid*, cropping the browser chrome (toolbar/tabs)
    so OCR focuses on page content only. Falls back to full screen.
    """
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    target_wid = None
    win_height = 0
    for w in wins:
        if w.get("kCGWindowOwnerPID") == pid:
            bounds = w.get("kCGWindowBounds", {})
            alpha = w.get("kCGWindowAlpha", 0)
            width = bounds.get("Width", 0)
            height = bounds.get("Height", 0)
            if width > 200 and height > 200 and alpha > 0:
                target_wid = w.get("kCGWindowNumber")
                win_height = height
                break

    if target_wid is not None:
        image_ref = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            target_wid,
            Quartz.kCGWindowImageBoundsIgnoreFraming,
        )
        if image_ref and Quartz.CGImageGetWidth(image_ref) > 0:
            # Crop top ~140px (browser toolbar + tabs) — scaled for Retina (×2)
            full_w = Quartz.CGImageGetWidth(image_ref)
            full_h = Quartz.CGImageGetHeight(image_ref)
            scale = full_h / win_height if win_height > 0 else 2.0
            crop_top = int(140 * scale)
            if crop_top < full_h:
                image_ref = Quartz.CGImageCreateWithImageInRect(
                    image_ref,
                    Quartz.CGRectMake(0, crop_top, full_w, full_h - crop_top),
                )
            return _save_image(image_ref)

    # Fallback: full screen
    image_ref = Quartz.CGWindowListCreateImage(
        Quartz.CGRectInfinite,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if not image_ref:
        return None
    return _save_image(image_ref)


def _save_image(image_ref) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    dest = Quartz.CFURLCreateWithFileSystemPath(None, tmp.name, Quartz.kCFURLPOSIXPathStyle, False)
    dst = Quartz.CGImageDestinationCreateWithURL(dest, "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(dst, image_ref, None)
    Quartz.CGImageDestinationFinalize(dst)
    return Path(tmp.name)


def _run_vision_ocr(image_path: Path) -> list[str]:
    """Run Apple Vision text recognition on an image file."""
    url = Cocoa.NSURL.fileURLWithPath_(str(image_path))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})

    results: list[str] = []

    def completion(request, error):
        if error:
            return
        for obs in request.results():
            text = obs.topCandidates_(1)[0].string()
            if text and text.strip():
                results.append(text.strip())

    req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completion)
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)

    handler.performRequests_error_([req], None)
    return results


def ocr_snapshot(pid: int) -> list[str]:
    """Return OCR-recognized text from the frontmost window of the given PID."""
    img_path = _screenshot_window_region(pid)
    if img_path is None:
        return []
    try:
        return _run_vision_ocr(img_path)
    finally:
        try:
            os.unlink(img_path)
        except OSError:
            pass


def ocr_snapshot_text(pid: int) -> str:
    """Return OCR text as a single joined string."""
    return "\n".join(ocr_snapshot(pid))

