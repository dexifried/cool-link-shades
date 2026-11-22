"""Build an experimental head-bound triangle; never writes to the game installation.

Run with HookshotBuilder's bundled Python, which supplies the zstandard package.
The reference project's BFRES parser is used for inspection and consistency checks.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import types

import zstandard

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "reference" / "OoT-Character-Select" / "tools"))
shim = types.ModuleType("pyzstd")
shim.ZstdDict = zstandard.ZstdCompressionDict
shim.decompress = lambda data, zstd_dict=None: zstandard.ZstdDecompressor(dict_data=zstd_dict).decompress(data)
sys.modules["pyzstd"] = shim
import bfres
import nxfmt


def read_source(path):
    packed = Path(path).read_bytes()
    dict_id = zstandard.get_frame_parameters(packed).dict_id
    dictionary = None
    if dict_id:
        for candidate in nxfmt.load_dicts().values():
            if candidate.dict_id() == dict_id:
                dictionary = candidate
                break
        if dictionary is None:
            raise ValueError("Source compression dictionary not found")
    return decompress(packed, dictionary), dictionary


def decompress(data, dictionary):
    return zstandard.ZstdDecompressor(dict_data=dictionary).decompress(data)


def compress(data, dictionary):
    return zstandard.ZstdCompressor(level=16, dict_data=dictionary).compress(data)


def describe(data):
    f = bfres.Fres(bytes(data))
    m = f.model()
    shape = next(s for s in m.shapes if s.name == "Face_low__Mt_Face")
    vtx = f.u64(shape.off + 0x10)
    count = f.u32(vtx + 0x50)
    relative, nattr, nbuf, _, _ = struct.unpack_from("<IBBHI", data, vtx + 0x48)
    if nbuf != 1:
        raise ValueError("Expected one face vertex buffer")
    size_ptr = f.u64(vtx + 0x30)
    stride = f.u32(f.u64(vtx + 0x38))
    if stride != 40 or f.u32(size_ptr) != stride * count:
        raise ValueError("Unexpected face vertex layout")
    attrs = {}
    arr = f.u64(vtx + 8)
    for i in range(nattr):
        name = f.string(f.u64(arr + 16 * i))
        attrs[name] = struct.unpack_from("<HHHH", data, arr + 16 * i + 8)
    expected = {"_p0": (0x1805, 0, 0, 0), "_i0": (0x0b03, 0, 32, 0), "_w0": (0x0b01, 0, 36, 0)}
    if any(attrs.get(k) != value for k, value in expected.items()):
        raise ValueError("Unexpected face attribute layout")
    head_index = next(i for i, bone in enumerate(m.bones) if bone.name == "Head_2")
    head_matrix = m.bones[head_index].smooth
    if head_index not in shape.skin_bones or not 0 <= head_matrix < 256:
        raise ValueError("Face shape cannot use the Head_2 matrix")
    base = f.sections[1]["pos"]
    vertex_start = base + relative
    meshes = []
    mesh_array = f.u64(shape.off + 0x18)
    for i in range(shape.meshes):
        mesh = mesh_array + i * 0x38
        index_off, primitive, fmt, index_count, first = struct.unpack_from("<5I", data, mesh + 0x20)
        if (primitive, fmt) != (3, 1) or first > count:
            raise ValueError("Unexpected face index format")
        index_size_ptr = f.u64(mesh + 0x18)
        if f.u32(index_size_ptr) != index_count * 2:
            raise ValueError("Unexpected face index buffer size")
        submesh = f.u64(mesh)
        if f.u32(mesh + 0x34) != 1 or struct.unpack_from("<II", data, submesh) != (0, index_count):
            raise ValueError("Unexpected face submesh layout")
        meshes.append(dict(index_count=index_count, index_end=base + index_off + index_count * 2,
                           index_count_ptr=mesh + 0x2c, index_size_ptr=index_size_ptr,
                           submesh_count_ptr=submesh + 4, first=first))
    return dict(vertex_start=vertex_start, vertex_end=vertex_start + stride * count,
                vertex_count=count, vertex_count_ptr=vtx + 0x50, vertex_size_ptr=size_ptr,
                meshes=meshes, bone_matrix=head_matrix)


def add_probe(data):
    layout = describe(data)
    original = bytes(data)
    vertex_end = layout["vertex_end"]
    if original[vertex_end:vertex_end + 120] != bytes(120) or any(
        original[mesh["index_end"]:mesh["index_end"] + 6] != bytes(6) for mesh in layout["meshes"]
    ):
        raise ValueError("Insufficient zero padding for probe geometry")
    if layout["vertex_count"] + 2 > 65535:
        raise ValueError("Probe indices do not fit")
    row = None
    for offset in range(layout["vertex_start"], vertex_end, 40):
        if original[offset + 32] == layout["bone_matrix"] and original[offset + 36] == 255:
            row = original[offset:offset + 40]
            break
    if row is None:
        raise ValueError("No suitable face vertex template")
    out = bytearray(original)
    points = [(-0.065, 1.60, 0.20), (0.065, 1.60, 0.20), (0.0, 1.76, 0.20)]
    for i, point in enumerate(points):
        new = bytearray(row)
        struct.pack_into("<3f", new, 0, *point)
        new[32:40] = bytes([layout["bone_matrix"], 0, 0, 0, 255, 0, 0, 0])
        out[vertex_end + i * 40:vertex_end + (i + 1) * 40] = new
    for mesh in layout["meshes"]:
        struct.pack_into("<3H", out, mesh["index_end"], *(layout["vertex_count"] - mesh["first"] + i for i in range(3)))
        struct.pack_into("<I", out, mesh["index_count_ptr"], mesh["index_count"] + 3)
        struct.pack_into("<I", out, mesh["index_size_ptr"], (mesh["index_count"] + 3) * 2)
        struct.pack_into("<I", out, mesh["submesh_count_ptr"], mesh["index_count"] + 3)
    struct.pack_into("<I", out, layout["vertex_count_ptr"], layout["vertex_count"] + 3)
    struct.pack_into("<I", out, layout["vertex_size_ptr"], (layout["vertex_count"] + 3) * 40)
    return bytes(out), layout


def reopen(data):
    f = bfres.Fres(data)
    f.model()
    return f.build() == data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(nxfmt.ROMFS) / "Model/Player_Adult.Player_Adult.bfres.zs")
    parser.add_argument("--output", type=Path, required=True, help="experimental output inside the workspace")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("output must be a new file within this workspace")
    data, dictionary = read_source(args.source)
    modified, report = add_probe(data)
    if not reopen(modified):
        raise ValueError("Modified BFRES did not reopen unchanged")
    packed = compress(modified, dictionary)
    if decompress(packed, dictionary) != modified:
        raise ValueError("Compression verification failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packed)
    print(json.dumps({"output": str(output), "bytes": len(packed), "head_matrix": report["bone_matrix"], "status": "experimental; not tested in game"}, indent=2))


if __name__ == "__main__":
    main()
