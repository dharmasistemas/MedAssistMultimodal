import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_secrets import read_sensitive_values, scan_repository


class SecretSafetyTests(unittest.TestCase):
    def test_scanner_detects_secret_without_returning_its_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            secret = b'super-secret-value'
            (root / 'unsafe.txt').write_bytes(b'credential=' + secret)

            findings, scanned_files = scan_repository(
                root,
                {'GEMINI_API_KEY': secret},
            )

        self.assertEqual(scanned_files, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, 'GEMINI_API_KEY')
        self.assertNotIn(secret.decode(), repr(findings[0]))

    def test_scanner_ignores_source_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            secret = 'super-secret-value'
            (root / '.env').write_text(
                f'GEMINI_API_KEY={secret}\n',
                encoding='utf-8',
            )
            values = read_sensitive_values(root / '.env')

            findings, scanned_files = scan_repository(root, values)

        self.assertEqual(scanned_files, 0)
        self.assertEqual(findings, [])

    def test_scanner_prunes_directories_before_descending(self) -> None:
        # Simula entradas sem criar ou acessar qualquer diretório privado.
        from scripts.check_secrets import candidate_files
        directories = ['_backup', '.git', 'src']
        with patch('scripts.check_secrets.os.walk', return_value=iter([
            ('fixture-root', directories, ['safe.py']),
        ])):
            files = candidate_files(Path('fixture-root'))
        self.assertEqual(directories, ['src'])
        self.assertEqual(files, [Path('fixture-root/safe.py')])


if __name__ == '__main__':
    unittest.main()
