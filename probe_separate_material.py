"""Build a standalone black head-bound triangle for isolated Lichii tests.

Clones existing BFRES records and uses only existing GPU buffer padding. This is
an experiment, not a finished mod. The original eyebrow draw remains unchanged.
"""
import argparse
from pathlib import Path
import struct

import probe_mesh as common
import probe_dark

COLORS = (0x68E131E72BCD91AD, 0xE647277D46E8C1D8,
          0x0187464EC6541F6E, 0x961383B79667F911)


def build_separate(original):
    modified = probe_dark.add_dark_probe(original, constant_uv=True)
    f = common.bfres.Fres(modified)
    m = f.model()
    source = common.bfres.Fres(original)
    orig = source.model()
    eyebrow = next(s for s in m.shapes if s.name == 'Eyebrow_A_low__Mt_Eyebrow')
    oldshape = next(s for s in orig.shapes if s.name == eyebrow.name)
    matidx = m.material_names.index('Mt_Eyebrow')
    old_shape_array = f.u64(m.off + 0x28)
    old_mat_array = f.u64(m.off + 0x38)
    old_material = old_mat_array + matidx * 0xB0
    relocations = list(f.pointers())

    def alloc_copy(offset, size):
        new = f.alloc(bytes(f.data[offset:offset + size]))
        for section, loc in relocations:
            if offset <= loc < offset + size:
                f.sections[section]['entries'].append([new + loc - offset, 1, 1, 0])
        return new

    def put(offset, fmt, *values):
        if offset >= f.rlt_off:
            struct.pack_into(fmt, f.new, offset - f.rlt_off, *values)
        else:
            struct.pack_into(fmt, f.data, offset, *values)

    def new_dict(old_ptr, new_name, name_ptr):
        names, _ = f.read_dict(old_ptr)
        names.append(new_name)
        keys = [f.u64(old_ptr + 8 + (i + 1) * 16 + 8) for i in range(len(names) - 1)] + [name_ptr]
        nodes = common.bfres.resdic_build([n.encode() for n in names])
        blob = bytearray(struct.pack('<Ii', 0, len(names)))
        for i, (ref, left, right) in enumerate(nodes):
            blob += struct.pack('<iHHQ', ref, left, right, 0 if i == 0 else keys[i - 1])
        ptr = f.alloc(blob)
        for i in range(1, len(nodes)):
            f.sections[0]['entries'].append([ptr + 8 + i * 16 + 8, 1, 1, 0])
        return ptr

    shape_name = f.add_string('CoolLink_Probe')
    mat_name = f.add_string('Mt_CoolLink_Probe')
    # Clone material records, then clone just the eyebrow parameter block so the
    # new tint does not affect any stock material.
    materials = alloc_copy(old_mat_array, m.material_count * 0xB0)
    mat = alloc_copy(old_material, 0xB0)
    # Material records have to be contiguous; append the cloned record directly.
    assert mat == materials + m.material_count * 0xB0
    params = f.u64(old_material + 0x58)
    refl = f.u64(f.u64(old_material + 0x10))
    nparam, param_size = struct.unpack_from('<HH', original, refl + 0x4A)
    new_params = f.alloc(original[params:params + param_size])
    put(mat + 8, '<Q', mat_name)
    put(mat + 0x58, '<Q', new_params)
    put(mat + 0xA0, '<H', m.material_count)
    # FMAT includes mutable runtime arrays in addition to shader parameters.
    # Cloning just the record aliases those arrays with the stock eyebrow.
    nsamplers, ntextures = original[old_material+0xA2:old_material+0xA4]
    for field, size in ((0x18, ntextures*8), (0x28, nsamplers*0x78),
                        (0x60, nparam*4), (0x80, ((nparam+31)//32)*4),
                        (0x90, nsamplers*8), (0x98, ntextures*8)):
        old = source.u64(old_material+field)
        if old:
            put(mat+field, '<Q', alloc_copy(old, size))
    arr = f.u64(refl + 0x20)
    found = set()
    for i in range(nparam):
        key = f.u64(arr + i * 0x18 + 8)
        if key in COLORS:
            poff = struct.unpack_from('<H', original, arr + i * 0x18 + 0x10)[0]
            put(new_params + poff, '<4f', 0.04, 0.04, 0.04, 1.0)
            found.add(key)
    if found != set(COLORS):
        raise ValueError('Expected tint parameters are missing')
    mat_dict = new_dict(f.u64(m.off + 0x40), 'Mt_CoolLink_Probe', mat_name)

    # Clone the stock array and append one shape. Both shapes share the eyebrow
    # vertex buffer, but the new one draws only the newly inserted indices.
    shapes = alloc_copy(old_shape_array, m.shape_count * 0x60)
    new_shape = alloc_copy(eyebrow.off, 0x60)
    assert new_shape == shapes + m.shape_count * 0x60
    put(new_shape + 8, '<Q', shape_name)
    put(new_shape + 0x50, '<HH', m.shape_count, m.material_count)
    old_meshes = f.u64(eyebrow.off + 0x18)
    meshes = alloc_copy(old_meshes, eyebrow.meshes * 0x38)
    put(new_shape + 0x18, '<Q', meshes)
    for i in range(eyebrow.meshes):
        old_mesh = old_meshes + i * 0x38
        mesh = meshes + i * 0x38
        size_ptr = source.u64(old_mesh + 0x18)
        original_size = source.u32(size_ptr)
        original_n = source.u32(old_mesh + 0x2c)
        sub_ptr = source.u64(old_mesh)
        new_sub = f.alloc(struct.pack('<II', 0, 6))
        # A BufferInfo is 16 bytes, not just its first (size) word. Copy the
        # stock flags/reserved fields and give each draw its own runtime
        # nn::gfx::Buffer storage so it cannot overwrite the eyebrow object.
        info = bytearray(original[size_ptr:size_ptr + 16])
        struct.pack_into('<I', info, 0, 12)
        new_size = f.alloc(info)
        new_buffer = f.alloc(bytes(0x48), align=16)
        old_offset = source.u32(old_mesh + 0x20)
        put(mesh, '<Q', new_sub)
        put(mesh + 0x10, '<Q', new_buffer)
        put(mesh + 0x18, '<Q', new_size)
        put(mesh + 0x20, '<I', old_offset + original_size)
        put(mesh + 0x2c, '<I', 6)
        # Restore stock draw counts, retaining inserted vertex/index bytes.
        put(old_mesh + 0x2c, '<I', original_n)
        put(size_ptr, '<I', original_size)
        put(sub_ptr + 4, '<I', original_n)
    shape_dict = new_dict(f.u64(m.off + 0x30), 'CoolLink_Probe', shape_name)
    put(m.off + 0x28, '<Q', shapes)
    put(m.off + 0x30, '<Q', shape_dict)
    put(m.off + 0x38, '<Q', materials)
    put(m.off + 0x40, '<Q', mat_dict)
    put(m.off + 0x6A, '<HH', m.shape_count + 1, m.material_count + 1)
    result = f.build()
    rebuilt = common.bfres.Fres(result).model()
    assert rebuilt.shapes[-1].name == 'CoolLink_Probe'
    assert rebuilt.material_names[-1] == 'Mt_CoolLink_Probe'
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(common.ROOT) or output.exists():
        ap.error('output must be a new file in the workspace')
    source = Path(common.nxfmt.ROMFS) / 'Model/Player_Adult.Player_Adult.bfres.zs'
    original, dictionary = common.read_source(source)
    modified = build_separate(original)
    packed = common.compress(modified, dictionary)
    assert common.decompress(packed, dictionary) == modified
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packed)
    print(f'Wrote isolated material probe: {output}')
