import argparse
import datetime
import gc
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def check_opaque(filepath):
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
    except Exception as e:
        raise RuntimeError(f"Failed to check opacity of {filepath}: {e}")


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


def load_image(filepath):
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
    return img


def process_scene(args):
    out_num, scene, batch_dir_str = args
    batch_dir = Path(batch_dir_str)

    base_asset = scene[0]
    base_fp = resolve_filepath(base_asset["file"])
    if base_fp is None:
        raise FileNotFoundError(f"Base asset not found: {base_asset['file']}")
    base_img = load_image(base_fp)

    psd = PSDImage.new(mode="RGBA", size=base_img.size)
    base_layer = psd.create_pixel_layer(base_img, name=os.path.basename(base_asset["file"]))
    psd.append(base_layer)

    for asset in scene[1:]:
        fp = resolve_filepath(asset["file"])
        if fp is None:
            raise FileNotFoundError(f"Asset file not found: {asset['file']}")
        img = load_image(fp)
        layer = psd.create_pixel_layer(img, name=os.path.basename(asset["file"]))
        psd.append(layer)
        del img

    out_path = batch_dir / f"scene_{out_num:04d}.psd"
    psd.save(str(out_path))
    del psd, base_img
    gc.collect()
    return out_num, len(scene), os.path.basename(base_asset["file"]), out_path.name


def main():
    parser = argparse.ArgumentParser(description="Generate PSD files from asset tracking JSON")
    parser.add_argument("--start", type=int, default=1, help="First scene number to process (1-based, original scene index)")
    parser.add_argument("--count", type=int, default=0, help="Number of scenes to process (0 = all remaining)")
    parser.add_argument("--workers", type=int, default=0, help="Number of parallel workers (0 = auto)")
    parser.add_argument("--include-single", action="store_true", help="Include single-layer scenes (skipped by default)")
    args = parser.parse_args()

    if not JSON_PATH.exists():
        raise FileNotFoundError(f"JSON file not found: {JSON_PATH}")

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assets = data.get("assets", [])
    if not assets:
        log("No assets found in JSON.")
        return

    log(f"Total assets: {len(assets)}")

    log("Phase 1: Resolving filepaths and checking opacity in parallel...")
    resolved = []
    for asset in assets:
        fp = resolve_filepath(asset["file"])
        if fp is None:
            raise FileNotFoundError(f"Asset file not found: {asset['file']}")
        resolved.append((asset, fp))

    workers = args.workers if args.workers > 0 else None
    opaque_map = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_opaque, fp): i for i, (_, fp) in enumerate(resolved)}
        done_count = 0
        for future in as_completed(futures):
            idx = futures[future]
            opaque_map[idx] = future.result()
            done_count += 1
            if done_count % 500 == 0:
                log(f"  Opacity check: {done_count}/{len(resolved)}")

    log("Phase 2: Grouping assets into scenes...")
    all_scenes = []
    current_scene = None
    for i, (asset, fp) in enumerate(resolved):
        if opaque_map[i]:
            if current_scene is not None:
                all_scenes.append(current_scene)
            current_scene = [(i + 1, asset)]
        else:
            if current_scene is None:
                raise RuntimeError(
                    f"First asset in list is transparent: {asset['file']} (idx={asset['idx']}). "
                    "Expected an opaque base image to start the first scene."
                )
            current_scene.append((i + 1, asset))
    if current_scene is not None:
        all_scenes.append(current_scene)

    total_scenes = len(all_scenes)
    single_count = sum(1 for s in all_scenes if len(s) == 1)
    log(f"Total scenes: {total_scenes} (single-layer: {single_count}, multi-layer: {total_scenes - single_count})")

    if not args.include_single:
        multi_scenes = [(i + 1, s) for i, s in enumerate(all_scenes) if len(s) > 1]
        log(f"Skipping {single_count} single-layer scenes. Processing {len(multi_scenes)} multi-layer scenes.")
    else:
        multi_scenes = [(i + 1, s) for i, s in enumerate(all_scenes)]
        log(f"Processing all {len(multi_scenes)} scenes (including single-layer).")

    start = args.start
    count = args.count if args.count > 0 else total_scenes - start + 1
    end = min(start + count - 1, total_scenes)

    filtered = [(orig, s) for orig, s in multi_scenes if start <= orig <= end]
    if not filtered:
        log("No scenes to process in the specified range.")
        return

    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_dir = OUTPUT_DIR / now
    batch_dir.mkdir(parents=True, exist_ok=True)

    psd_workers = args.workers if args.workers > 0 else None
    log(f"Phase 3: Generating {len(filtered)} PSD files with {psd_workers} workers...")

    tasks = []
    for out_num, (orig_num, scene) in enumerate(filtered, 1):
        scene_data = [asset for _, asset in scene]
        tasks.append((out_num, scene_data, str(batch_dir)))

    completed = 0
    total = len(tasks)
    with ProcessPoolExecutor(max_workers=psd_workers) as executor:
        futures = {executor.submit(process_scene, task): task[0] for task in tasks}
        for future in as_completed(futures):
            out_num, num_layers, base_name, saved_name = future.result()
            completed += 1
            log(f"  [{completed}/{total}] Scene {out_num}: {num_layers} layers, {saved_name}")

    log(f"\nDone! {len(filtered)} PSD files saved to:\n  {batch_dir}")


if __name__ == "__main__":
    main()
