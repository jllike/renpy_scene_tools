init python:
    import json
    import os
    import datetime

    def _extract_displayable_filenames(d):
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

    def save_scene_info():
        sl = renpy.game.context().scene_lists
        skip_layers = {'screens', 'overlay', 'transient', 'over_screens'}
        layers_data = {}

        for layer_name in config.layers:
            if layer_name in skip_layers:
                continue

            entries = sl.layers.get(layer_name, [])
            if not entries:
                continue

            layer_entries = []
            for entry in entries:
                tag = entry.tag or ""
                zorder = entry.zorder
                name = entry.name

                filenames = []
                if entry.displayable:
                    filenames = _extract_displayable_filenames(entry.displayable)

                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    is_video = ext in ('.webm', '.mp4', '.mov', '.avi', '.ogv', '.mkv')
                    layer_entries.append({
                        "tag": tag,
                        "zorder": zorder,
                        "name": list(name) if name else [],
                        "file": fn,
                        "type": "video" if is_video else "image"
                    })

            layer_entries.sort(key=lambda x: x["zorder"])

            if layer_entries:
                layers_data[layer_name] = layer_entries

        try:
            current_node = renpy.current_node()
            label = current_node.name if current_node else ""
        except:
            label = ""

        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": label,
            "layers": layers_data
        }

        save_path = os.path.join(config.basedir, "快照.json")
        data = []
        if os.path.exists(save_path):
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = []

        data.append(entry)

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            renpy.notify("Scene saved!")
        except Exception as e:
            renpy.notify("Save failed: " + str(e))

    _save_path = os.path.join(config.basedir, "快照.json")
    with open(_save_path, "w", encoding="utf-8") as _f:
        _f.write("[]")

    config.overlay_screens.append("scene_saver_overlay")

screen scene_saver_overlay():
    key "K_F11" action Function(save_scene_info)
