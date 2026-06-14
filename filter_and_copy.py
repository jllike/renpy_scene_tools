import datetime
import json
import os
import shutil
from pathlib import Path

from PIL import Image

SCRIPT_DIR = Path(__file__).parent
GAME_ROOT = SCRIPT_DIR.parent
JSON_PATH = GAME_ROOT / "保存的一幕.json"
CLEAN_JSON_PATH = SCRIPT_DIR / "保存的一幕_clean.json"
IMAGES_DIR = GAME_ROOT / "game" / "images"

VIDEO_EXTS = {".webm", ".mp4", ".mov", ".avi", ".ogv", ".mkv"}


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
    ext = os.path.splitext(filepath)[1].lower()
    if ext in VIDEO_EXTS:
        return True
    try:
        img = Image.open(filepath)
        if img.mode in ("RGBA", "LA", "PA"):
            alpha = img.getchannel("A")
            extrema = alpha.getextrema()
            return extrema[0] == 255
        return True
    except Exception:
        return True


def filter_layer(entries):
    last_opaque_idx = -1
    for i, entry in enumerate(entries):
        fp = resolve_filepath(entry["file"])
        if fp and is_opaque(fp):
            last_opaque_idx = i
    if last_opaque_idx >= 0:
        return entries[last_opaque_idx:]
    return entries


def step1_filter():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    clean_data = []
    for entry in data:
        clean_entry = {
            "timestamp": entry["timestamp"],
            "label": entry["label"],
            "layers": {},
        }
        for layer_name, layer_entries in entry.get("layers", {}).items():
            visible = filter_layer(layer_entries)
            if visible:
                clean_entry["layers"][layer_name] = visible
        clean_data.append(clean_entry)

    CLEAN_JSON_PATH.write_text(
        json.dumps(clean_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Step 1 done. Clean JSON saved to:\n  {CLEAN_JSON_PATH}")
    print("Please review the clean JSON before proceeding.")


def step2_copy():
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_dir = SCRIPT_DIR / ("素材_" + now)
    clean_data = json.loads(CLEAN_JSON_PATH.read_text(encoding="utf-8"))
    for entry in clean_data:
        ts = entry["timestamp"].replace(":", "-").replace(" ", "_")
        dest_dir = batch_dir / ts
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied = set()
        for layer_entries in entry.get("layers", {}).values():
            for asset in layer_entries:
                fn = asset["file"]
                if fn in copied:
                    continue
                src = resolve_filepath(fn)
                if src:
                    shutil.copy2(src, dest_dir / src.name)
                    print(f"  Copied: {src.name}")
                    copied.add(fn)
                else:
                    print(f"  NOT FOUND: {fn}")
    print(f"\nDone! All visible assets have been copied to:\n  {batch_dir}")


if __name__ == "__main__":
    step1_filter()
    input("\nPress Enter to continue to Step 2 (copy assets)...")
    step2_copy()
