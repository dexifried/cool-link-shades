# Cool Link Shades

Adult Link wears chunky, dark sunglasses inspired by the classic meme. This experimental cosmetic mod is for the Ocarina of Time remake, update 2.0.0, title ID `0400486024DEC000`, on Lichii for Windows. The head-bound mesh uses the game's lighting and does not change game logic or saves.

## Hover Boots update

The original release used a normal-boot material, which the game hides when Hover Boots or Iron Boots are equipped. This update moves the glasses out of that visibility group while retaining the same mesh, textures, head binding, and shader. The original teeth material is moved to an existing extra material slot. In a diagnostic build, moving the teeth made it possible to confirm they rendered in that slot; the released model keeps them in their normal position.

In an isolated Lichii build-177 profile, this revision was visible with Hover Boots and the green and blue tunics in the equipment view, and with Iron Boots and the green tunic in the equipment view. The owner reported that the previous release worked outdoors and in cutscenes; those scenarios have not yet been rechecked for this revision. Full gameplay animation, rolling, other equipment, and distant rendering remain unverified. Hair overlap is expected; the bridge or sides may appear too bright in some lighting. Only the two largest texture mip levels were edited in the original release.

## Install or uninstall

Download the latest release ZIP and extract it. With Lichii closed, replace the previous `Cool Link Shades (experimental)` folder under `%APPDATA%\eden\load\0400486024DEC000\` with the folder from the ZIP, then enable it in the game's add-ons. The mod folder must contain `romfs/` directly inside it. Portable profiles may use their own `user/load/0400486024DEC000/` folder. To uninstall, close Lichii and disable or remove only that mod folder.

The mod replaces `romfs/Model/Player_Adult.Player_Adult.bfres.zs` and three `Mt_Boots_Player_Adult` albedo, normal, and roughness textures under `romfs/Tex/`. It conflicts with other mods replacing those same files. Other game updates have not been tested. `SHA256SUMS` lists the release files; run `python verify_snapshot.py` to check them.

The original revision remains available in the `experimental-1.0` release and the `frozen-shared-lit` tag.

## Rebuilding

From a full Git clone containing the `frozen-shared-lit` tag, use Python with `zstandard` installed. Supply the original game's `Pack/ZsDic.pack.zs` via `OOT_ROMFS` pointing to an extracted romfs; it defaults to `~/Games/Hookshot/romfs`. Run `python experimental/build_boot_visibility_fix.py`. The script checks the frozen 1.0 model's hash, uses it as the input, and writes the rebuilt model under ignored `build/`. It does not independently recreate the mesh or textures.

The model and textures are modified game-derived assets; original game assets belong to their respective rights holders. The included reference tools derive from [OoT-Character-Select](https://github.com/snaildev99/OoT-Character-Select); its MIT license is preserved under `reference/`.
