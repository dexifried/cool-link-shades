"""Check that the boot fix only reassigns the intended material records and shapes."""
from pathlib import Path
import struct
import subprocess
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import probe_mesh as common


class BootVisibilityFixTests(unittest.TestCase):
    def test_material_swap_preserves_every_other_byte(self):
        current, dictionary = common.read_source(root / 'mod/romfs/Model/Player_Adult.Player_Adult.bfres.zs')
        packed = subprocess.check_output(
            ['git', 'show', 'frozen-shared-lit:mod/romfs/Model/Player_Adult.Player_Adult.bfres.zs'], cwd=root)
        original = common.decompress(packed, dictionary)
        f = common.bfres.Fres(original)
        m = f.model()
        teeth, custom = m.material_names.index('Mt_Teeth'), m.material_names.index('Mt_CoolLink_Probe')
        base = f.u64(m.off + 0x38)
        a, b = base + teeth * 0xb0, base + custom * 0xb0
        expected = bytearray(original)
        expected[a:a+0xb0], expected[b:b+0xb0] = original[b:b+0xb0], original[a:a+0xb0]
        struct.pack_into('<Q', expected, a + 8, f.u64(a + 8))
        struct.pack_into('<Q', expected, b + 8, f.u64(b + 8))
        struct.pack_into('<H', expected, a + 0xa0, teeth)
        struct.pack_into('<H', expected, b + 0xa0, custom)
        shapes = {s.name: s for s in m.shapes}
        struct.pack_into('<H', expected, shapes['CoolLink_Probe'].off + 0x52, teeth)
        struct.pack_into('<H', expected, shapes['Teeth_Under_low__Mt_Teeth'].off + 0x52, custom)
        self.assertEqual(current, expected)


if __name__ == '__main__':
    unittest.main()
