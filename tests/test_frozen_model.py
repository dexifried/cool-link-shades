"""Compare the actual frozen model with the extracted stock model."""
import struct
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import probe_mesh as common


class FrozenModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stock = Path(common.nxfmt.ROMFS) / 'Model/Player_Adult.Player_Adult.bfres.zs'
        frozen = root / 'mod/romfs/Model/Player_Adult.Player_Adult.bfres.zs'
        cls.original, _ = common.read_source(stock)
        cls.modified, _ = common.read_source(frozen)
        cls.old = common.bfres.Fres(cls.original)
        cls.new = common.bfres.Fres(cls.modified)
        cls.old_model, cls.new_model = cls.old.model(), cls.new.model()

    def test_stock_vertex_and_index_data_are_unchanged(self):
        old, new = self.old, self.new
        for shape in self.old_model.shapes:
            other = next(s for s in self.new_model.shapes if s.name == shape.name)
            old_vertex, new_vertex = old.u64(shape.off + 0x10), new.u64(other.off + 0x10)
            size = old.u32(old.u64(old_vertex + 0x30))
            a = old.sections[1]['pos'] + old.u32(old_vertex + 0x48)
            b = new.sections[1]['pos'] + new.u32(new_vertex + 0x48)
            self.assertEqual(self.original[a:a + size], self.modified[b:b + size], shape.name)
            for i in range(shape.meshes):
                om = old.u64(shape.off + 0x18) + i * 0x38
                nm = new.u64(other.off + 0x18) + i * 0x38
                oi, _, _, oc, of = struct.unpack_from('<5I', self.original, om + 0x20)
                ni, _, _, nc, nf = struct.unpack_from('<5I', self.modified, nm + 0x20)
                self.assertEqual((oc, of), (nc, nf), shape.name)
                oi += old.sections[1]['pos']
                ni += new.sections[1]['pos']
                self.assertEqual(self.original[oi:oi + oc * 2], self.modified[ni:ni + nc * 2], shape.name)

    def test_glasses_are_head_bound_and_indices_are_in_range(self):
        f, m = self.new, self.new_model
        shape = next(s for s in m.shapes if s.name == 'CoolLink_Probe')
        vertex = f.u64(shape.off + 0x10)
        start = f.sections[1]['pos'] + f.u32(vertex + 0x48) + 3080 * 36
        self.assertEqual(f.u32(vertex + 0x50), 3136)
        for i in range(56):
            self.assertEqual(self.modified[start + i * 36 + 28:start + i * 36 + 36],
                             bytes((87, 0, 0, 0, 255, 0, 0, 0)))
        self.assertEqual(shape.meshes, 3)
        for i in range(shape.meshes):
            mesh = f.u64(shape.off + 0x18) + i * 0x38
            offset = f.sections[1]['pos'] + f.u32(mesh + 0x20)
            count = f.u32(mesh + 0x2c)
            self.assertEqual(count, 396)
            indices = struct.unpack_from(f'<{count}H', self.modified, offset)
            self.assertTrue(all(3080 <= value < 3136 for value in indices))
        self.assertGreater(f.check(), 0)


if __name__ == '__main__':
    unittest.main()
