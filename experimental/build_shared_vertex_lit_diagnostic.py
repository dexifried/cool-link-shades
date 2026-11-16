"""Rebuild the frozen model using its checked-in glasses as a geometry template.

Reads the matching extracted stock model and dictionary; writes only to build/.
"""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import probe_mesh as common
import build_pbr_probe as pbr

root = Path(__file__).resolve().parent
stock_path = Path(common.nxfmt.ROMFS) / 'Model/Player_Adult.Player_Adult.bfres.zs'
lit_path = root.parent / 'mod/romfs/Model/Player_Adult.Player_Adult.bfres.zs'
dest = root.parent / 'build/Player_Adult.Player_Adult.bfres.zs'
if dest.exists():
    raise FileExistsError(dest)
original, dictionary = common.read_source(stock_path)
lit, _ = common.read_source(lit_path)
data = bytearray(pbr.build(original))
f, g = common.bfres.Fres(data), common.bfres.Fres(lit)
m, lm = f.model(), g.model()
shape = next(s for s in m.shapes if s.name == 'CoolLink_Probe')
lshape = next(s for s in lm.shapes if s.name == 'CoolLink_Probe')
v, lv = f.u64(shape.off + 0x10), g.u64(lshape.off + 0x10)
assert f.u32(v + 0x50) == 3136 and g.u32(lv + 0x50) == 3136
target = f.sections[1]['pos'] + f.u32(v + 0x48) + 3080 * 36
source = g.sections[1]['pos'] + g.u32(lv + 0x48) + 3080 * 36
data[target:target+56*36] = lit[source:source+56*36]
struct.pack_into('<I', data, shape.off + 4, g.u32(lshape.off + 4))
struct.pack_into('<H', data, shape.off + 0x52, m.material_names.index('Mt_Boots_Metal'))
data[shape.off + 0x5a] = lit[lshape.off + 0x5a]
common.bfres.Fres(data).model()
packed = common.compress(data, dictionary)
assert common.decompress(packed, dictionary) == data
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_bytes(packed)
print('Wrote rebuilt model:', dest)
