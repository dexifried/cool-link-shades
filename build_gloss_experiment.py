"""Try a game-lit, lower-roughness lens using an already loaded texture."""
import argparse
from pathlib import Path
import struct

import probe_mesh as common
import build_shades_experiment as shades


def build(original):
    f = common.bfres.Fres(shades.build(original))
    m = f.model()
    materials = f.u64(m.off+0x38)
    target = materials + m.material_names.index('Mt_CoolLink_Probe')*0xB0
    boots = materials + m.material_names.index('Mt_Boots_Metal')*0xB0
    target_keys = f.read_dict(f.u64(target+0x38))[0]
    boots_keys = f.read_dict(f.u64(boots+0x38))[0]
    assert target_keys.index('_rgh0') < f.data[target+0xA3]
    count = f.data[target+0xA3]
    old_names = f.u64(target+0x20)
    names = f.alloc(f.data[old_names:old_names+count*8])
    for i in range(count):
        f.sections[0]['entries'].append([names+i*8, 1, 1, 0])
    boots_names = f.u64(boots+0x20)
    roughness = f.u64(boots_names + boots_keys.index('_rgh0')*8)
    struct.pack_into('<Q', f.new, names-f.rlt_off+target_keys.index('_rgh0')*8, roughness)
    struct.pack_into('<Q', f.data, target+0x20, names)
    shape = next(s for s in m.shapes if s.name == 'CoolLink_Probe')
    vtx = f.u64(shape.off+0x10)
    start = f.sections[1]['pos']+f.u32(vtx+0x48)
    count = f.u32(vtx+0x50)
    points, _ = shades.mesh()
    for i in range(count-len(points),count):
        struct.pack_into('<2e',f.data,start+i*36+24,32.5/512,392.5/512)
    result = f.build()
    common.bfres.Fres(result).model()
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(common.ROOT) or output.exists():
        ap.error('output must be a new file in the workspace')
    source=Path(common.nxfmt.ROMFS)/'Model/Player_Adult.Player_Adult.bfres.zs'
    original,dictionary=common.read_source(source)
    modified=build(original)
    packed=common.compress(modified,dictionary)
    assert common.decompress(packed,dictionary)==modified
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(packed)
    print(f'Wrote roughness experiment: {output}')
