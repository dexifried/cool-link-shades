"""Rebuild the 1.1 model from the verified frozen 1.0 Git tag.

Requires the original game's Zstandard dictionary via OOT_ROMFS. Writes only to build/.
"""
import hashlib
from pathlib import Path
import struct
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import probe_mesh as common

source_hash = '2054b54c87af5a2801695ba3e9298b5746ffdba27670d52bee70456c54ca2113'
source = subprocess.check_output(
    ['git', 'show', 'frozen-shared-lit:mod/romfs/Model/Player_Adult.Player_Adult.bfres.zs'], cwd=root)
if hashlib.sha256(source).hexdigest() != source_hash:
    raise ValueError('The frozen 1.0 model did not match the verified source')
input_path = root / 'build' / 'frozen-1' / 'Player_Adult.Player_Adult.bfres.zs'
input_path.parent.mkdir(parents=True, exist_ok=True)
if input_path.exists() and input_path.read_bytes() != source:
    raise ValueError('Existing build input differs from the frozen Git tag')
input_path.write_bytes(source)
raw, dictionary = common.read_source(input_path)
data = bytearray(raw)
f = common.bfres.Fres(raw)
m = f.model()
base = f.u64(m.off + 0x38)
teeth = m.material_names.index('Mt_Teeth')
custom = m.material_names.index('Mt_CoolLink_Probe')
a, b = base + teeth * 0xb0, base + custom * 0xb0
orig_a, orig_b = raw[a:a+0xb0], raw[b:b+0xb0]
data[a:a+0xb0], data[b:b+0xb0] = orig_b, orig_a
# Keep material names and indices tied to their original slots; exchange everything else.
struct.pack_into('<Q', data, a + 8, f.u64(a + 8))
struct.pack_into('<Q', data, b + 8, f.u64(b + 8))
struct.pack_into('<H', data, a + 0xa0, teeth)
struct.pack_into('<H', data, b + 0xa0, custom)
shade = next(s for s in m.shapes if s.name == 'CoolLink_Probe')
tooth = next(s for s in m.shapes if s.name == 'Teeth_Under_low__Mt_Teeth')
struct.pack_into('<H', data, shade.off + 0x52, teeth)
struct.pack_into('<H', data, tooth.off + 0x52, custom)
model = common.bfres.Fres(data).model()
assert model.material_names[teeth] == 'Mt_Teeth'
assert model.material_names[custom] == 'Mt_CoolLink_Probe'
packed = common.compress(data, dictionary)
assert common.decompress(packed, dictionary) == data
output = root / 'build' / 'hover-fix' / 'Player_Adult.Player_Adult.bfres.zs'
if output.exists():
    raise FileExistsError(output)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(packed)
print('Wrote', output)
