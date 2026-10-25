"""Real Blender geometry, lifecycle and persistence checks for soma display."""
import subprocess
import unittest


class TestSomaDisplay(unittest.TestCase):
    def test_display_geometry(self):
        subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                        '--python', 'tests/soma_display_worker.py'], check=True, timeout=90)

    def test_animation_render(self):
        subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                        '--python', 'tests/soma_animation_worker.py'], check=True, timeout=60)
        subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                        '--python', 'tests/soma_reopen_worker.py'], check=True, timeout=30)

    def test_incremental_geometry(self):
        subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                        '--python', 'tests/soma_incremental_worker.py'], check=True, timeout=60)


if __name__ == '__main__':
    unittest.main()
