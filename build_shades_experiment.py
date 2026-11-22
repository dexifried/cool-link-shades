"""Build an experimental black sunglasses mesh for the isolated Lichii profile.

This is a fit test, not a release. It never writes into a game or emulator folder.
"""
import argparse
from pathlib import Path
import struct

import probe_mesh as common
import probe_separate_material as separate


def mesh():
    vertices, faces = [], []

    def polygon(points):
        start = len(vertices)
        vertices.extend(points)
        for i in range(1, len(points) - 1):
            a, b, c = start, start + i, start + i + 1
            faces.extend((a, b, c, a, c, b))

    # Rest-pose face samples put the nose at z~0.128 and the eye/cheek
    # surfaces around z~0.075-0.115. Follow that curvature instead of
    # positioning the lenses out at z~0.17 as in the first fit test.
    right = [(0.009,1.509,0.132),(0.020,1.516,0.130),
             (0.041,1.518,0.122),(0.071,1.512,0.110),
             (0.086,1.502,0.097),(0.083,1.479,0.099),
             (0.075,1.463,0.108),(0.048,1.457,0.118),
             (0.026,1.460,0.129),(0.010,1.467,0.134)]
    for outline in (right, [(-x,y,z) for x,y,z in reversed(right)]):
        cx = sum(p[0] for p in outline)/len(outline)
        cy = sum(p[1] for p in outline)/len(outline)
        start = len(vertices)
        # Outer lip is slightly raised; the inset lens shares its edge.
        vertices.extend((x,y,z+0.0025) for x,y,z in outline)
        vertices.extend((cx+(x-cx)*0.86, cy+(y-cy)*0.83, z+0.001)
                        for x,y,z in outline)
        n = len(outline)
        def tri(a,b,c):
            faces.extend((a,b,c,a,c,b))
        for i in range(n):
            j=(i+1)%n
            tri(start+i,start+j,start+n+j)
            tri(start+i,start+n+j,start+n+i)
        for i in range(1,n-1):
            tri(start+n,start+n+i,start+n+i+1)
    polygon([(-0.015, 1.505, 0.135), (0.015, 1.505, 0.135),
             (0.015, 1.475, 0.137), (-0.015, 1.475, 0.137)])
    # Short, narrow temples overlap the outer rims and disappear under the
    # hair. The previous long, deep polygon emerged beyond the hair as an
    # isolated triangular patch.
    for sign in (-1, 1):
        polygon([(sign * 0.077, 1.507, 0.110), (sign * 0.095, 1.503, 0.079),
                 (sign * 0.100, 1.499, 0.060), (sign * 0.098, 1.493, 0.060),
                 (sign * 0.091, 1.496, 0.080), (sign * 0.078, 1.500, 0.108)])
    return vertices, faces


def build(original):
    base_data = separate.build_separate(original)
    f = common.bfres.Fres(base_data)
    m = f.model()
    shape = next(s for s in m.shapes if s.name == 'CoolLink_Probe')
    stock = next(s for s in m.shapes if s.name == 'Eyebrow_A_low__Mt_Eyebrow')
    vtx = f.u64(stock.off + 0x10)
    relative, _, nbuf, _, count = struct.unpack_from('<IBBHI', f.data, vtx + 0x48)
    stride = f.u32(f.u64(vtx + 0x38))
    if nbuf != 1 or stride != 36 or count != 3083:
        raise ValueError('Unexpected shared eyebrow buffer')
    base = f.sections[1]['pos']
    start = base + relative
    stock_count = count - 3
    vertices, indices = mesh()
    out = bytearray(base_data)

    # Open space in the existing GPU vertex pool, without changing its size.
    # The pool has 2924 unused trailing zero bytes in the verified 2.0.0 model.
    shift, move_start = 2048, 0x2c2800
    pool_end = f.sections[2]['pos'] + f.sections[2]['size']
    if pool_end != 0x86a000 or any(out[pool_end - shift:pool_end]):
        raise ValueError('Vertex pool has insufficient unused tail padding')
    if start + stock_count * stride != 0x2c2720:
        raise ValueError('Unexpected eyebrow vertex position')
    out[move_start + shift:pool_end] = out[move_start:pool_end - shift]
    out[move_start:move_start + shift] = bytes(shift)
    seen = set()
    for s in m.shapes:
        ptr = f.u64(s.off + 0x10)
        if ptr in seen:
            continue
        seen.add(ptr)
        r = f.u32(ptr + 0x48)
        if base + r >= move_start:
            struct.pack_into('<I', out, ptr + 0x48, r + shift)
    if stock_count * stride + len(vertices) * stride > move_start + shift - start:
        raise ValueError('New vertices exceed the available buffer gap')
    template = bytes(out[start + stock_count * stride:start + (stock_count + 1) * stride])
    for i, point in enumerate(vertices):
        row = bytearray(template)
        struct.pack_into('<3f', row, 0, *point)
        # The eyebrow template's arbitrary normals make flat, unlit lenses.
        # Orient the lenses toward the face's front; angle the outer lip
        # slightly so the game's lighting can pick up the beveled frame.
        if i < 40 and i % 20 < 10:
            x, y, _ = point
            nx = max(-0.5, min(0.5, (abs(x)-0.048)*8)) * (1 if x > 0 else -1)
            ny = max(-0.5, min(0.5, (y-1.487)*12))
            nz = (max(0.0, 1.0-nx*nx-ny*ny))**0.5
        else:
            nx,ny,nz=0.0,0.0,1.0
        normal = sum((round(v*511) & 0x3ff) << (10*k) for k,v in enumerate((nx,ny,nz)))
        struct.pack_into('<I', row, 12, normal)
        struct.pack_into('<I', row, 16, 511)
        out[start + (stock_count + i) * stride:start + (stock_count + i + 1) * stride] = row
    new_count = stock_count + len(vertices)
    struct.pack_into('<I', out, vtx + 0x50, new_count)
    struct.pack_into('<I', out, f.u64(vtx + 0x30), new_count * stride)

    # Find a single verified, zero-filled gap between existing index buffers;
    # all three detail levels may share these head-bound glasses indices.
    spans = []
    for s in m.shapes:
        ma = f.u64(s.off + 0x18)
        for i in range(s.meshes):
            ptr = ma + i * 0x38
            off, _, fmt, n, _ = struct.unpack_from('<5I', f.data, ptr + 0x20)
            if fmt != 1:
                raise ValueError('Unexpected index format')
            spans.append((base + off, base + off + n * 2))
    spans.sort()
    need = len(indices) * 2
    slot = None
    for left, right in zip(spans, spans[1:]):
        candidate = (left[1] + 3) & ~3
        if right[0] - candidate >= need and not any(out[candidate:candidate + need]):
            slot = candidate
            break
    if slot is None:
        # Both index and vertex buffers use offsets from the same GPU pool.
        # Use only proven-unused zero padding after the shifted vertex data.
        candidate = (pool_end - need) & ~3
        if candidate < pool_end - (2924-shift) or any(out[candidate:candidate+need]):
            raise ValueError('No suitable GPU buffer padding for glasses indices')
        slot = candidate
    struct.pack_into(f'<{len(indices)}H', out, slot, *(stock_count + i for i in indices))
    array = f.u64(shape.off + 0x18)
    for i in range(shape.meshes):
        ptr = array + i * 0x38
        struct.pack_into('<I', out, ptr + 0x20, slot - base)
        struct.pack_into('<I', out, ptr + 0x2c, len(indices))
        struct.pack_into('<I', out, ptr + 0x30, 0)
        struct.pack_into('<I', out, f.u64(ptr + 0x18), need)
        struct.pack_into('<II', out, f.u64(ptr), 0, len(indices))
    result = bytes(out)
    common.bfres.Fres(result).model()
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
    modified = build(original)
    packed = common.compress(modified, dictionary)
    assert common.decompress(packed, dictionary) == modified
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packed)
    print(f'Wrote experimental glasses fit test: {output}')
