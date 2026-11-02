import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "tools" / "touch_keyboard.py"
spec = importlib.util.spec_from_file_location("touch_keyboard", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TouchKeyboardTests(unittest.TestCase):
    def test_complete_registry(self):
        text = "\n".join("interface: '%s', version: 1, name: 2" % x for x in m.REQUIRED)
        self.assertEqual(m.missing_protocols(text), [])

    def test_partial_registry(self):
        self.assertIn("zwp_input_method_manager_v2", m.missing_protocols("interface: 'wl_seat'"))

    def test_mentions_are_not_advertisements(self):
        self.assertEqual(len(m.missing_protocols(" ".join(m.REQUIRED))), 4)

    def test_command_has_no_key_output(self):
        command = m.keyboard_command("wvkbd-deskintl", 300)
        self.assertIn("--auto", command)
        self.assertIn("--hidden", command)
        for flag in ("-o", "-O", "-D"):
            self.assertNotIn(flag, command)

    def test_height_bounds(self):
        for height in (0, 119, 801):
            with self.assertRaises(ValueError):
                m.keyboard_command("wvkbd-deskintl", height)

    def test_environment_disables_tracing(self):
        source = {"WAYLAND_DEBUG": "1", "WVKBD_DEBUG": "1", "WAYLAND_DISPLAY": "wayland-0"}
        result = m.safe_environment(source)
        self.assertNotIn("WAYLAND_DEBUG", result)
        self.assertNotIn("WVKBD_DEBUG", result)
        self.assertEqual(result["WAYLAND_DISPLAY"], "wayland-0")
        self.assertIn("WAYLAND_DEBUG", source)

    def test_no_wayland_fails(self):
        with self.assertRaisesRegex(RuntimeError, "active Wayland"):
            m.check("wvkbd-deskintl", {})

    def test_old_keyboard_rejected(self):
        registry = "\n".join("interface: '%s'" % x for x in m.REQUIRED)
        from subprocess import CompletedProcess
        with patch.object(m.shutil, "which", return_value="/fake/bin"), patch.object(
            m.subprocess, "run", side_effect=[
                CompletedProcess([], 0, registry, ""),
                CompletedProcess([], 1, "", "usage: old keyboard")]):
            with self.assertRaisesRegex(RuntimeError, "too old"):
                m.check("wvkbd-deskintl", {"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/tmp"})


if __name__ == "__main__":
    unittest.main()
