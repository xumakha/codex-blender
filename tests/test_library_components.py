import json
from pathlib import Path
import tempfile
import unittest

from codex_blender.library import catalog


class LibraryComponentTests(unittest.TestCase):
    def test_components_stay_available_but_only_assembly_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,meta in [('assembly',{'preview':'preview.png'}),
                              ('arm',{'component_of':'assembly.glb','preview':'preview.png'}),
                              ('hand',{'component_of':'assembly.glb','preview':'preview.png'}),
                              ('orphan',{'component_of':'missing.glb'})]:
                (root/(name+'.glb')).write_bytes(b'fixture')
                (root/(name+'.asset.json')).write_text(json.dumps(meta),encoding='utf-8')
            (root/'preview.png').write_bytes(b'preview')
            (root/'reference.png').write_bytes(b'user image')
            items={item['path']:item for item in catalog(root)}
            self.assertEqual(len(items),6)
            self.assertTrue(items['arm.glb']['internal'])
            self.assertTrue(items['hand.glb']['internal'])
            self.assertTrue(items['preview.png']['internal'])
            self.assertFalse(items['assembly.glb']['internal'])
            self.assertFalse(items['reference.png']['internal'])
            self.assertFalse(items['orphan.glb']['internal'])


if __name__=='__main__':
    unittest.main()
