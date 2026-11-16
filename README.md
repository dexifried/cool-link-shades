# Cool Link Shades — frozen experimental snapshot

This repository freezes the newer-looking Adult Link sunglasses revision tested in an isolated Lichii build-177 profile with Ocarina of Time remake update 2.0.0 (title ID `0400486024DEC000`). The `mod/` folder contains the exact files installed in the two previously configured Lichii/Eden profiles. The glasses are a head-bound mesh using the game's lighting; they do not alter gameplay logic or saves.

The green outfit displayed without the previous black patches in the tested equipment view. The glasses were also visible in a dark dungeon gameplay view after brief movement and in a sword-drawn stance. This is still experimental: rolling, the full range of combat animations, outdoor lighting, cutscenes, other equipment, and distant rendering have not been conclusively verified. The bridge or sides may appear too bright in other lighting, and some hair overlap is expected.

## Install or uninstall

Download the release ZIP and extract it. With Lichii closed, copy the enclosed `Cool Link Shades (experimental)` folder to `%APPDATA%\eden\load\0400486024DEC000\`, then enable it in the game's add-ons. The mod folder must contain `romfs/` directly inside it. Alternatively, copy the repository's `mod/` folder to the same location and rename it. To uninstall, close Lichii and disable or remove only that mod folder. Other profiles may use their own `user/load/0400486024DEC000/` folder.

The four game assets changed by this snapshot are listed with SHA-256 hashes in `SHA256SUMS`. Run `python verify_snapshot.py` to check them. The screenshot files under `screenshots/` show this exact model in the isolated test.

The model conflicts with other Adult Link model replacements. The three boot-texture overrides conflict with other mods replacing those same textures. Only the two largest texture mip levels were edited, so distant rendering remains unverified. Other game updates have not been tested.

## Model build and source

The Python scripts and the reference parser used for the model build are included. Rebuilding requires Python with `zstandard`, the matching extracted 2.0.0 `Model/Player_Adult.Player_Adult.bfres.zs`, and `Pack/ZsDic.pack.zs`. Set `OOT_ROMFS` to the extracted romfs directory; it defaults to `~/Games/Hookshot/romfs`. Confirm that the source model matches the installed game/update before rebuilding.

Run `python experimental/build_shared_vertex_lit_diagnostic.py`. It reads the glasses geometry from the checked-in frozen model as a template and writes a new file under ignored `build/`; it does not regenerate the glasses mesh independently. For the original source assets and environment, the rebuilt compressed model was byte-identical to the frozen model. The texture authoring experiments remain in the original workspace; the final texture files themselves are frozen in `mod/`.

The included `bfres.py` and `nxfmt.py` derive from [OoT-Character-Select](https://github.com/snaildev99/OoT-Character-Select); its MIT license is preserved in `reference/OoT-Character-Select/LICENSE`. The model and textures are modified game-derived assets; the original game assets belong to their respective rights holders.

