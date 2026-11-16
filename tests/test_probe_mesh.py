import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probe_mesh
import probe_dark
import build_shades_experiment
import build_gloss_experiment


class ProbeMeshTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(os.environ["USERPROFILE"]) / "Games/Hookshot/romfs/Model/Player_Adult.Player_Adult.bfres.zs"
        self.original, self.dictionary = probe_mesh.read_source(self.source)

    def test_adds_head_bound_triangle_without_changing_existing_vertices(self):
        modified, report = probe_mesh.add_probe(self.original)
        before, after = probe_mesh.describe(self.original), probe_mesh.describe(modified)
        self.assertEqual(len(modified), len(self.original))
        self.assertEqual(after["vertex_count"], before["vertex_count"] + 3)
        self.assertEqual(len(before["meshes"]), 3)
        for old_mesh, new_mesh in zip(before["meshes"], after["meshes"]):
            self.assertEqual(new_mesh["index_count"], old_mesh["index_count"] + 3)
            self.assertEqual(struct.unpack_from("<I", modified, old_mesh["submesh_count_ptr"])[0], old_mesh["index_count"] + 3)
            expected = tuple(range(before["vertex_count"] - old_mesh["first"], before["vertex_count"] - old_mesh["first"] + 3))
            self.assertEqual(struct.unpack_from("<3H", modified, old_mesh["index_end"]), expected)
        self.assertEqual(modified[before["vertex_start"]:before["vertex_end"]], self.original[before["vertex_start"]:before["vertex_end"]])
        for i in range(3):
            row = modified[before["vertex_end"] + i * 40:before["vertex_end"] + (i + 1) * 40]
            self.assertEqual(row[32:40], bytes([report["bone_matrix"], 0, 0, 0, 255, 0, 0, 0]))
        self.assertTrue(probe_mesh.reopen(modified))

    def test_refuses_to_overwrite_nonzero_padding(self):
        original = bytearray(self.original)
        layout = probe_mesh.describe(original)
        original[layout["vertex_end"]] = 1
        with self.assertRaisesRegex(ValueError, "padding"):
            probe_mesh.add_probe(original)

    def test_compressed_output_round_trips(self):
        modified, _ = probe_mesh.add_probe(self.original)
        self.assertEqual(probe_mesh.decompress(probe_mesh.compress(modified, self.dictionary), self.dictionary), modified)

    def test_existing_eyebrow_material_probe_preserves_existing_vertices(self):
        f = probe_mesh.bfres.Fres(self.original)
        shape = next(s for s in f.model().shapes if s.name == 'Eyebrow_A_low__Mt_Eyebrow')
        vtx = f.u64(shape.off + 0x10)
        start = f.sections[1]['pos'] + f.u32(vtx + 0x48)
        count = f.u32(vtx + 0x50)
        modified = probe_dark.add_dark_probe(self.original)
        self.assertEqual(modified[start:start + count * 36], self.original[start:start + count * 36])
        self.assertEqual(struct.unpack_from('<I', modified, vtx + 0x50)[0], count + 3)
        self.assertEqual(modified[start + count * 36 + 28:start + count * 36 + 36], bytes([87, 0, 0, 0, 255, 0, 0, 0]))
        self.assertTrue(probe_mesh.reopen(modified))

    def test_glasses_preserve_stock_geometry_and_bind_every_vertex_to_head(self):
        modified = build_shades_experiment.build(self.original)
        before = probe_mesh.bfres.Fres(self.original)
        after = probe_mesh.bfres.Fres(modified)
        original_model, new_model = before.model(), after.model()
        self.assertEqual(new_model.shape_count, original_model.shape_count + 1)
        self.assertEqual(new_model.material_count, original_model.material_count + 1)
        for old in original_model.shapes:
            new = next(s for s in new_model.shapes if s.name == old.name)
            old_vtx, new_vtx = before.u64(old.off + 0x10), after.u64(new.off + 0x10)
            length = before.u32(before.u64(old_vtx + 0x30))
            old_start = before.sections[1]['pos'] + before.u32(old_vtx + 0x48)
            new_start = after.sections[1]['pos'] + after.u32(new_vtx + 0x48)
            self.assertEqual(self.original[old_start:old_start+length], modified[new_start:new_start+length], old.name)
            old_mesh, new_mesh = before.u64(old.off+0x18), after.u64(new.off+0x18)
            for i in range(old.meshes):
                op, np = old_mesh+i*0x38, new_mesh+i*0x38
                oi, _, _, oc, of = struct.unpack_from('<5I', self.original, op+0x20)
                ni, _, _, nc, nf = struct.unpack_from('<5I', modified, np+0x20)
                self.assertEqual((oc, of), (nc, nf), old.name)
                oi += before.sections[1]['pos']
                ni += after.sections[1]['pos']
                self.assertEqual(self.original[oi:oi+oc*2], modified[ni:ni+nc*2], old.name)
        shape = next(s for s in new_model.shapes if s.name == 'CoolLink_Probe')
        old_shape = next(s for s in original_model.shapes if s.name == 'Eyebrow_A_low__Mt_Eyebrow')
        old_count = before.u32(before.u64(old_shape.off+0x10)+0x50)
        vtx = after.u64(shape.off+0x10)
        start = after.sections[1]['pos'] + after.u32(vtx+0x48)
        points, indices = build_shades_experiment.mesh()
        for i in range(len(points)):
            offset = start + (old_count+i)*36
            self.assertEqual(modified[offset+28:offset+36], bytes([87,0,0,0,255,0,0,0]))
        meshes = after.u64(shape.off+0x18)
        for i in range(3):
            offset, _, _, count, first = struct.unpack_from('<5I', modified, meshes+i*0x38+0x20)
            self.assertEqual((count, first), (len(indices), 0))
            self.assertEqual(struct.unpack_from(f'<{count}H', modified, after.sections[1]['pos']+offset),
                             tuple(old_count+j for j in indices))
        self.assertEqual(new_model.shader_param('Mt_Eyebrow', 0x68E131E72BCD91AD, '<4f'),
                         original_model.shader_param('Mt_Eyebrow', 0x68E131E72BCD91AD, '<4f'))
        self.assertEqual(probe_mesh.decompress(probe_mesh.compress(modified, self.dictionary), self.dictionary), modified)

    def test_glasses_have_independent_runtime_index_buffers_and_complete_info(self):
        modified = build_shades_experiment.build(self.original)
        f = probe_mesh.bfres.Fres(modified)
        m = f.model()
        eyebrow = next(s for s in m.shapes if s.name == 'Eyebrow_A_low__Mt_Eyebrow')
        glasses = next(s for s in m.shapes if s.name == 'CoolLink_Probe')
        original_buffers = set()
        for shape in m.shapes:
            if shape.name == glasses.name:
                continue
            array = f.u64(shape.off + 0x18)
            original_buffers.update(f.u64(array + i * 0x38 + 0x10) for i in range(shape.meshes))
        array = f.u64(glasses.off + 0x18)
        eyebrow_array = f.u64(eyebrow.off + 0x18)
        new_buffers = set()
        for i in range(glasses.meshes):
            ptr = array + i * 0x38
            buffer = f.u64(ptr + 0x10)
            self.assertNotIn(buffer, original_buffers)
            self.assertNotIn(buffer, new_buffers)
            self.assertEqual(modified[buffer:buffer + 0x48], bytes(0x48))
            new_buffers.add(buffer)
            info = f.u64(ptr + 0x18)
            old_info = f.u64(eyebrow_array + i * 0x38 + 0x18)
            self.assertEqual(modified[info + 4:info + 16], modified[old_info + 4:old_info + 16])

    def test_glasses_material_owns_its_runtime_arrays(self):
        modified = build_shades_experiment.build(self.original)
        f = probe_mesh.bfres.Fres(modified)
        m = f.model()
        array = f.u64(m.off + 0x38)
        stock = array + m.material_names.index('Mt_Eyebrow') * 0xB0
        clone = array + m.material_names.index('Mt_CoolLink_Probe') * 0xB0
        for offset in (0x18, 0x28, 0x60, 0x80, 0x90, 0x98):
            self.assertNotEqual(f.u64(stock + offset), f.u64(clone + offset), hex(offset))

    def test_gloss_changes_only_new_material_texture_reference(self):
        original = probe_mesh.bfres.Fres(self.original)
        modified = build_gloss_experiment.build(self.original)
        f = probe_mesh.bfres.Fres(modified)
        m = f.model()
        oldm = original.model()
        def texture_names(fres, model, name):
            material = fres.u64(model.off + 0x38) + model.material_names.index(name)*0xB0
            keys = fres.read_dict(fres.u64(material+0x38))[0]
            arr = fres.u64(material+0x20)
            return {key:fres.string(fres.u64(arr+i*8)) for i,key in enumerate(keys)}
        self.assertEqual(texture_names(original, oldm, 'Mt_Eyebrow'),
                         texture_names(f, m, 'Mt_Eyebrow'))
        self.assertEqual(texture_names(f, m, 'Mt_CoolLink_Probe')['_rgh0'],
                         texture_names(f, m, 'Mt_Boots_Metal')['_rgh0'])
        self.assertGreater(f.check(), 0)
        self.assertEqual(probe_mesh.decompress(probe_mesh.compress(modified, self.dictionary), self.dictionary), modified)


if __name__ == "__main__":
    unittest.main()
