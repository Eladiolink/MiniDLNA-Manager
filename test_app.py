#!/usr/bin/env python3
"""
Test suite for MiniDLNA Web UI backend.
"""

import os
import json
import unittest
import tempfile
from app import app, read_config, write_config, is_port_in_use, check_port_conflict

class MiniDLNATestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

        # Temporary test config
        self.temp_conf = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".conf")
        self.temp_conf.write("""# Test MiniDLNA config
port=8200
friendly_name=Test Server
media_dir=V,/tmp/videos
media_dir=A,/tmp/music
inotify=yes
""")
        self.temp_conf.flush()
        self.temp_conf.close()

        # Point environment to temporary config
        os.environ["MINIDLNA_CONF"] = self.temp_conf.name
        # Re-import or point app.CONFIG_PATH
        import app as app_module
        app_module.CONFIG_PATH = self.temp_conf.name

    def tearDown(self):
        if os.path.exists(self.temp_conf.name):
            os.remove(self.temp_conf.name)
        bak = f"{self.temp_conf.name}.bak"
        if os.path.exists(bak):
            os.remove(bak)

    def test_index_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"MiniDLNA", res.data)
        self.assertIn(b"Vis\xc3\xa3o Geral", res.data)

    def test_api_status(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("service", data)
        self.assertIn("metrics", data)
        self.assertIn("config", data)

    def test_api_get_config(self):
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        cfg = data["config"]
        self.assertEqual(cfg["port"], "8200")
        self.assertEqual(cfg["friendly_name"], "Test Server")
        self.assertEqual(len(cfg["media_dirs"]), 2)
        self.assertEqual(cfg["media_dirs"][0]["type"], "V")
        self.assertEqual(cfg["media_dirs"][0]["path"], "/tmp/videos")

    def test_api_post_config_valid(self):
        payload = {
            "port": 18200,
            "friendly_name": "Updated Server",
            "media_dirs": [
                {"type": "V", "path": "/tmp/movies"},
                {"type": "ALL", "path": "/tmp/all"}
            ],
            "inotify": "no"
        }
        res = self.client.post("/api/config", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Verify parsed back
        cfg = read_config()
        self.assertEqual(cfg["port"], "18200")
        self.assertEqual(cfg["friendly_name"], "Updated Server")
        self.assertEqual(len(cfg["media_dirs"]), 2)
        self.assertEqual(cfg["media_dirs"][0]["path"], "/tmp/movies")

    def test_api_post_config_invalid_port(self):
        payload = {
            "port": 999999,  # Invalid port
            "friendly_name": "Bad Port"
        }
        res = self.client.post("/api/config", json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_api_browse(self):
        res = self.client.get("/api/browse?path=/tmp")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("directories", data)

    def test_api_logs(self):
        res = self.client.get("/api/logs?lines=20")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("logs", data)

    def test_port_conflict_checker(self):
        # A valid unused ephemeral port should pass
        valid, msg = check_port_conflict(58921)
        self.assertTrue(valid)

        # Invalid port
        valid, msg = check_port_conflict("invalid")
        self.assertFalse(valid)

if __name__ == "__main__":
    unittest.main()
