import datetime
import json
import os
import sys
from pathlib import Path

import cv2
from PIL import Image
from psd_tools import PSDImage

SCRIPT_DIR = Path(__file__).parent
GAME_ROOT = SCRIPT_DIR.parent
JSON_PATH = GAME_ROOT / "素材记录.json"
IMAGES_DIR = GAME_ROOT / "game" / "images"
OUTPUT_DIR = SCRIPT_DIR / "psd"

VIDEO_EXTS = {".webm", ".mp4", ".mov", ".avi", ".ogv", ".mkv"}

_opaque_cache = {}
_image_cache = {}


def log(msg):
    print(msg, flush=True)


def resolve_filepath(filename):
    basename = os.path.basename(filename)
    candidates = [
        IMAGES_DIR / basename,
        IMAGES_DIR / filename,
    ]
    if filename.startswith("images/") or filename.startswith("images\\"):
        stripped = filename[7:]
        candidates.append(IMAGES_DIR / stripped)
        candidates.append(IMAGES_DIR / os.path.basename(stripped))
    for c in candidates:
        if c.exists():
            return c
    return None


def is_opaque(filepath):
    key = str(filepath)
    if key in _opaque_cache:
        return _opaque_cache[key]

    ext = os.path.splitext(filepath)[1].lower()
    if ext in VIDEO_EXTS:
        _opaque_cache[key] = True
        return True
    try:
        img = Image.open(filepath)
        if img.mode in ("RGBA", "LA", "PA"):
            alpha = img.getchannel("A")
            extrema = alpha.getextrema()
            result = extrema[0] == 255
        else:
            result = True
        _opaque_cache[key] = result
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to check opacity of {filepath}: {e}")


def load_image(filepath):
    key = str(filepath)
    if key in _image_cache:
        return _image_cache[key].copy()

    ext = os.path.splitext(filepath)[1].lower()
    if ext in VIDEO_EXTS:
        img = extract_video_frame(filepath)
    else:
        try:
            img = Image.open(filepath)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
        except Exception as e:
            raise RuntimeError(f"Failed to load image {filepath}: {e}")

    _image_cache[key] = img.copy()
    return img


def extract_video_frame(filepath):
    try:
        cap = cv2.VideoCapture(str(filepath))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {filepath}")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        mid_frame = frame_count // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            raise RuntimeError(f"Cannot read frame from video: {filepath}")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        return Image.fromarray(frame, "RGBA")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to extract frame from video {filepath}: {e}")


def group_scenes(assets):
    scenes = []
    current_scene = None

    for i, asset in enumerate(assets):
        if i % 500 == 0:
            log(f"  Grouping... {i}/{len(assets)}")

        fp = resolve_filepath(asset["file"])
        if fp is None:
            raise FileNotFoundError(f"Asset file not found: {asset['file']}")

        if is_opaque(fp):
            if current_scene is not None:
                scenes.append(current_scene)
            current_scene = [asset]
        else:
            if current_scene is None:
                raise RuntimeError(
                    f"First asset in list is transparent: {asset['file']} (idx={asset['idx']}). "
                    "Expected an opaque base image to start the first scene."
                )
            current_scene.append(asset)

    if current_scene is not None:
        scenes.append(current_scene)

    return scenes


def make_psd(scene_assets):
    base_asset = scene_assets[0]
    base_fp = resolve_filepath(base_asset["file"])
    if base_fp is None:
        raise FileNotFoundError(f"Base asset not found: {base_asset['file']}")
    base_img = load_image(base_fp)

    psd = PSDImage.new(mode="RGBA", size=base_img.size)
    base_layer = psd.create_pixel_layer(base_img, name=os.path.basename(base_asset["file"]))
    psd.append(base_layer)

    for asset in scene_assets[1:]:
        fp = resolve_filepath(asset["file"])
        if fp is None:
            raise FileNotFoundError(f"Asset file not found: {asset['file']}")
        img = load_image(fp)
        layer = psd.create_pixel_layer(img, name=os.path.basename(asset["file"]))
        psd.append(layer)

    return psd


def main():
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"JSON file not found: {JSON_PATH}")

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assets = data.get("assets", [])
    if not assets:
        log("No assets found in JSON.")
        return

    log(f"Total assets: {len(assets)}")
    log("Grouping assets into scenes...")

    scenes = group_scenes(assets)
    log(f"Total scenes: {len(scenes)}")

    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_dir = OUTPUT_DIR / now
    batch_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes, 1):
        log(f"Scene {i}/{len(scenes)}: {len(scene)} layers, base={scene[0]['file']}")
        psd = make_psd(scene)
        out_path = batch_dir / f"scene_{i:04d}.psd"
        psd.save(str(out_path))
        log(f"  Saved: {out_path.name}")

    log(f"\nDone! {len(scenes)} PSD files saved to:\n  {batch_dir}")


if __name__ == "__main__":
    main()
