import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_export', SCRIPTS / 'export_repository.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class PublicExportTests(unittest.TestCase):
    def test_export_has_runtime_assets_public_docs_and_no_nested_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = exporter.export(Path(temporary) / 'source')
            for name in ['README.md', 'LICENSE', 'pyproject.toml', '.github/workflows/test.yml',
                         'skills/audience/SKILL.md', 'skills/audience/scripts/audience.py',
                         'skills/audience/scripts/audience_core/report_assets/report.css']:
                self.assertTrue((result / name).is_file(), name)
            self.assertFalse((result / 'skills/audience/assets/repository').exists())
            self.assertFalse(any('__pycache__' in path.parts for path in result.rglob('*')))
            self.assertIn('audience_core.__version__', (result / 'pyproject.toml').read_text())

    def test_export_refuses_nonempty_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'keep.txt').write_text('keep')
            with self.assertRaises(ValueError):
                exporter.export(root)
            self.assertEqual((root / 'keep.txt').read_text(), 'keep')

    def test_copy_does_not_follow_links_or_include_private_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'input'
            source.mkdir()
            for name in ['.env', 'private.key', 'cached.pyc']:
                (source / name).write_text('private')
            (source / 'runs').mkdir()
            (source / 'runs/run.json').write_text('private')
            (source / 'script.py').write_text('print(1)')
            exporter.copy_entry(source, root / 'output')
            self.assertEqual([p.name for p in (root / 'output').iterdir()], ['script.py'])
            (source / 'link').symlink_to(source / 'script.py')
            with self.assertRaises(ValueError):
                exporter.copy_entry(source, root / 'other')

    def test_public_checkout_can_be_exported_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = exporter.export(Path(temporary) / 'first')
            spec = importlib.util.spec_from_file_location('exported_export', first / 'skills/audience/scripts/export_repository.py')
            exported = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(exported)
            second = exported.export(Path(temporary) / 'second')
            a = {str(p.relative_to(first)): p.read_bytes() for p in first.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            b = {str(p.relative_to(second)): p.read_bytes() for p in second.rglob('*') if p.is_file()}
            self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
