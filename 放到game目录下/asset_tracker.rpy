init python:
    import json
    import os
    import datetime

    _at_active = False
    _at_interaction_count = 0
    _at_new_since_write = 0
    _at_assets = []
    _at_on_screen = set()
    _at_start_time = None
    _at_dirty = False
    _at_json_path = os.path.join(config.basedir, "素材记录.json")
    _AT_WRITE_INTERVAL = 100
    _AT_NEW_ASSET_THRESHOLD = 50

    def _at_extract_filenames(d):
        from renpy.display.im import Image as ImImage
        from renpy.display.video import Movie

        filenames = []

        def callback(obj):
            try:
                if isinstance(obj, ImImage):
                    if obj.filename:
                        filenames.append(obj.filename)
                elif isinstance(obj, Movie):
                    play = getattr(obj, '_play', None)
                    if play:
                        if isinstance(play, list):
                            filenames.extend(play)
                        else:
                            filenames.append(play)
                    mask = getattr(obj, 'mask', None)
                    if mask:
                        filenames.append(mask)
            except:
                pass

        try:
            d.visit_all(callback)
        except:
            pass

        return filenames

    def _at_on_interact():
        global _at_interaction_count, _at_on_screen, _at_dirty, _at_new_since_write

        if not _at_active:
            return

        _at_interaction_count += 1
        idx = _at_interaction_count

        try:
            current_node = renpy.current_node()
            label = current_node.name if current_node else ""
        except:
            label = ""

        sl = renpy.game.context().scene_lists
        skip_layers = {'screens', 'overlay', 'transient', 'over_screens'}

        current_on_screen = set()

        for layer_name in config.layers:
            if layer_name in skip_layers:
                continue

            entries = sl.layers.get(layer_name, [])
            if not entries:
                continue

            for entry in entries:
                tag = entry.tag or ""

                filenames = []
                if entry.displayable:
                    filenames = _at_extract_filenames(entry.displayable)

                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    is_video = ext in ('.webm', '.mp4', '.mov', '.avi', '.ogv', '.mkv')

                    key = (layer_name, tag, fn)
                    current_on_screen.add(key)

                    if key not in _at_on_screen:
                        _at_assets.append({
                            "idx": idx,
                            "file": fn,
                            "type": "video" if is_video else "image",
                            "layer": layer_name,
                            "tag": tag,
                            "label": label
                        })
                        _at_dirty = True
                        _at_new_since_write += 1

        _at_on_screen = current_on_screen

        if _at_dirty and (_at_interaction_count % _AT_WRITE_INTERVAL == 0 or _at_new_since_write >= _AT_NEW_ASSET_THRESHOLD):
            _at_write_json()
            _at_dirty = False
            _at_new_since_write = 0

    def _at_write_json():
        data = {
            "start_time": _at_start_time or "",
            "total_interactions": _at_interaction_count,
            "assets": _at_assets
        }
        try:
            with open(_at_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _at_toggle():
        global _at_active, _at_start_time, _at_interaction_count, _at_assets, _at_on_screen, _at_dirty, _at_new_since_write

        _at_active = not _at_active

        if _at_active:
            _at_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _at_interaction_count = 0
            _at_assets = []
            _at_on_screen = set()
            _at_dirty = False
            _at_new_since_write = 0
            renpy.notify("Asset Tracker: ON")
        else:
            _at_write_json()
            renpy.notify("Asset Tracker: OFF (saved)")

    def _at_on_quit():
        if _at_active or _at_dirty:
            _at_write_json()

    config.interact_callbacks.append(_at_on_interact)
    config.quit_callbacks.append(_at_on_quit)
    config.overlay_screens.append("asset_tracker_overlay")

screen asset_tracker_overlay():
    key "K_F10" action Function(_at_toggle)
