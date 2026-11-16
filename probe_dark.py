"""Experimental triangle using Adult Link's existing eyebrow material.

Only use in the isolated test profile; this does not produce sunglasses.
"""
import argparse
from pathlib import Path
import struct

import probe_mesh as common


def add_dark_probe(data, leather=False, constant_uv=False):
    f = common.bfres.Fres(data)
    model = f.model()
    shape_name = 'Belt_Pattrn_low__Mt_Leater_Upper' if leather else 'Eyebrow_A_low__Mt_Eyebrow'
    material = 'Mt_Leater_Upper' if leather else 'Mt_Eyebrow'
    shape = next(s for s in model.shapes if s.name == shape_name)
    head = next(b.smooth for b in model.bones if b.name == 'Head_2')
    if model.material_names[shape.material] != material or 104 not in shape.skin_bones or head != 87:
        raise ValueError('Unexpected eyebrow material or skeleton')
    vtx = f.u64(shape.off + 0x10)
    rel, _, nbuf, _, count = struct.unpack_from('<IBBHI', data, vtx + 0x48)
    size_ptr, stride_ptr = f.u64(vtx + 0x30), f.u64(vtx + 0x38)
    if nbuf != 1 or f.u32(stride_ptr) != 36 or f.u32(size_ptr) != count * 36:
        raise ValueError('Unexpected eyebrow vertex layout')
    start = f.sections[1]['pos'] + rel
    end = start + count * 36
    if data[end:end + 108] != bytes(108):
        raise ValueError('Insufficient eyebrow vertex padding')
    out = bytearray(data)
    points = [(-0.065, 1.60, 0.20), (0.065, 1.60, 0.20), (0.0, 1.76, 0.20)]
    # Try a different stock UV and a white vertex color; the first template
    # did not render, and the reason is not yet known.
    for i, point in enumerate(points):
        # Preserve the UVs of an existing triangle across the new triangle.
        template_index = i
        row = bytearray(data[start + template_index * 36:start + (template_index + 1) * 36])
        struct.pack_into('<3f', row, 0, *point)
        if constant_uv:
            if leather:
                raise ValueError('constant-UV experiment is for eyebrows only')
            struct.pack_into('<2e', row, 24, 65.5 / 512, 65.5 / 512)
            row[20:24] = bytes([0, 0, 0, 255])
        row[28:36] = bytes([head, 0, 0, 0, 255, 0, 0, 0])
        out[end + i * 36:end + (i + 1) * 36] = row
    struct.pack_into('<I', out, vtx + 0x50, count + 3)
    struct.pack_into('<I', out, size_ptr, (count + 3) * 36)
    mesh_array = f.u64(shape.off + 0x18)
    for i in range(shape.meshes):
        mesh = mesh_array + i * 0x38
        index_offset, primitive, fmt, n, first = struct.unpack_from('<5I', data, mesh + 0x20)
        size_offset, submesh = f.u64(mesh + 0x18), f.u64(mesh)
        index_end = f.sections[1]['pos'] + index_offset + n * 2
        extra = 3 if leather else 6
        if (primitive, fmt) != (3, 1) or f.u32(size_offset) != n * 2 or f.u32(mesh + 0x34) != 1 or struct.unpack_from('<II', data, submesh) != (0, n) or data[index_end:index_end + extra * 2] != bytes(extra * 2):
            raise ValueError('Unexpected eyebrow index layout or padding')
        a, b, c = (count - first + j for j in range(3))
        indices = (a, b, c) if leather else (a, b, c, a, c, b)
        struct.pack_into(f'<{extra}H', out, index_end, *indices)
        struct.pack_into('<I', out, mesh + 0x2c, n + extra)
        struct.pack_into('<I', out, size_offset, (n + extra) * 2)
        struct.pack_into('<I', out, submesh + 4, n + extra)
    return bytes(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--leather', action='store_true')
    ap.add_argument('--constant-uv', action='store_true')
    args = ap.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(common.ROOT) or output.exists():
        ap.error('output must be a new file in the workspace')
    source = Path(common.nxfmt.ROMFS) / 'Model/Player_Adult.Player_Adult.bfres.zs'
    original, dictionary = common.read_source(source)
    modified = add_dark_probe(original, leather=args.leather, constant_uv=args.constant_uv)
    if not common.reopen(modified):
        raise ValueError('BFRES reparse failed')
    packed = common.compress(modified, dictionary)
    if common.decompress(packed, dictionary) != modified:
        raise ValueError('Compression round trip failed')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packed)
    print(f'Wrote experimental material probe: {output}')
