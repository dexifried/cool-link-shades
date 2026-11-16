"""Try the game's existing boot material on the isolated shades mesh.

This is a diagnostic build only. It writes exclusively to the workspace and
does not modify the installed mod, game data, or emulator configuration.
"""
import argparse
from pathlib import Path
import struct

import probe_mesh as common
import build_shades_experiment as shades


def build(original):
    out = bytearray(shades.build(original))
    f = common.bfres.Fres(bytes(out))
    model = f.model()
    shape = next(s for s in model.shapes if s.name == 'CoolLink_Probe')
    struct.pack_into('<H', out, shape.off + 0x52,
                     model.material_names.index('Mt_Boots_Metal'))
    vertex = f.u64(shape.off + 0x10)
    start = f.sections[1]['pos'] + f.u32(vertex + 0x48)
    count = f.u32(vertex + 0x50)
    points, _ = shades.mesh()
    face = next(s for s in model.shapes if s.name == 'Face_low__Mt_Face')
    face_vertex = f.u64(face.off+0x10)
    face_start = f.sections[1]['pos'] + f.u32(face_vertex+0x48)
    # Use an unmodified, front-facing surface basis from Link's cheek as a
    # control for the shader, independent of our tangent generation.
    basis = bytes(out[face_start+12:face_start+20])
    for i in range(count - len(points), count):
        off = start + i * 36
        out[off + 20:off + 24] = bytes((255, 255, 255, 255))
        # Stock character normals always carry W=+1; stock tangents carry
        # W=+1 or -1 as handedness. A zero tangent W collapses the bitangent
        # used by normal-mapped material shaders.
        out[off+12:off+20] = basis
        # Bright gold test pixel with near-flat normal and low roughness. A
        # clearly colored result proves that the material is actually bound;
        # this is diagnostic and is not intended as the finished appearance.
        struct.pack_into('<2e', out, off + 24, 491.5/768, 742.5/768)
    # The eyebrow buffer calls its color channel _c0, while the solid-material
    # shader expects _c1. Add an alias at the same byte offset, preserving _c0
    # for the original eyebrows and keeping all existing vertex data intact.
    f = common.bfres.Fres(bytes(out))
    model = f.model()
    shape = next(s for s in model.shapes if s.name == 'CoolLink_Probe')
    boots = next(s for s in model.shapes if s.name == 'Boots_Metal_A_low__Mt_Boots_Metal')
    # Give the added draw its own full solid-material record and runtime
    # arrays. Sharing a runtime FMAT with an unrelated draw may result in
    # shader state being overwritten during game initialization.
    material_array = f.u64(model.off + 0x38)
    target_index = model.material_names.index('Mt_CoolLink_Probe')
    source_index = model.material_names.index('Mt_Boots_Metal')
    target = material_array + target_index*0xb0
    source = material_array + source_index*0xb0
    target_name = f.u64(target+8)
    f.data[target:target+0xb0] = f.data[source:source+0xb0]
    struct.pack_into('<Q',f.data,target+8,target_name)
    struct.pack_into('<H',f.data,target+0xa0,target_index)
    struct.pack_into('<H',f.data,shape.off+0x52,target_index)
    refl = f.u64(f.u64(source+0x10))
    nparam = struct.unpack_from('<H',f.data,refl+0x4a)[0]
    nsamplers, ntextures = f.data[source+0xa2:source+0xa4]
    relocations = list(f.pointers())
    for field, size in ((0x18,ntextures*8),(0x28,nsamplers*0x78),
                        (0x60,nparam*4),(0x80,((nparam+31)//32)*4),
                        (0x90,nsamplers*8),(0x98,ntextures*8)):
        ptr=f.u64(source+field)
        if ptr:
            clone=f.alloc(f.data[ptr:ptr+size])
            for section,loc in relocations:
                if ptr <= loc < ptr+size:
                    f.sections[section]['entries'].append([clone+loc-ptr,1,1,0])
            struct.pack_into('<Q',f.data,target+field,clone)
    vertex = f.u64(shape.off + 0x10)
    boot_vertex = f.u64(boots.off + 0x10)
    boot_arr = f.u64(boot_vertex + 8)
    boot_count = f.data[boot_vertex + 0x4c]
    color_ptr = next(f.u64(boot_arr + i*16) for i in range(boot_count)
                     if f.string(f.u64(boot_arr + i*16)) == '_c1')
    old_arr = f.u64(vertex + 8)
    count = f.data[vertex + 0x4c]
    records = bytearray(f.data[old_arr:old_arr+16*count])
    color = next(i for i in range(count) if f.string(f.u64(old_arr+i*16)) == '_c0')
    record = bytearray(records[color*16:(color+1)*16])
    struct.pack_into('<Q', record, 0, color_ptr)
    records.extend(record)
    new_arr = f.alloc(records)
    for i in range(count+1):
        f.sections[0]['entries'].append([new_arr+i*16, 1, 1, 0])
    old_dict = f.u64(vertex+0x10)
    names, _ = f.read_dict(old_dict)
    pointers = [f.u64(old_dict+8+(i+1)*16+8) for i in range(len(names))] + [color_ptr]
    names.append('_c1')
    nodes = common.bfres.resdic_build([n.encode() for n in names])
    blob = bytearray(struct.pack('<Ii', 0, len(names)))
    for i, (ref, left, right) in enumerate(nodes):
        blob += struct.pack('<iHHQ', ref, left, right, 0 if i == 0 else pointers[i-1])
    new_dict = f.alloc(blob)
    for i in range(1,len(nodes)):
        f.sections[0]['entries'].append([new_dict+8+i*16+8, 1, 1, 0])
    struct.pack_into('<QQ', f.data, vertex+8, new_arr, new_dict)
    f.data[vertex+0x4c] = count+1
    result = f.build()
    common.bfres.Fres(result).model()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(common.ROOT) or output.exists():
        parser.error('output must be a new file in the workspace')
    source = Path(common.nxfmt.ROMFS) / 'Model/Player_Adult.Player_Adult.bfres.zs'
    original, dictionary = common.read_source(source)
    modified = build(original)
    packed = common.compress(modified, dictionary)
    assert common.decompress(packed, dictionary) == modified
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packed)
    print(f'Wrote isolated physically lit material probe: {output}')
