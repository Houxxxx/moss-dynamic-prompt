import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class Output:
    def __init__(self, *values):
        self.result = values


class TextGenerate:
    calls = []

    @classmethod
    def execute(cls, clip, prompt, max_length, sampling, **options):
        cls.calls.append((max_length, options["thinking"]))
        if options["thinking"]:
            return Output("", "unfinished reasoning")
        if prompt.startswith("{"):
            payload = json.loads(prompt)
            result = {
                "summary": {"meta": [], "canvas": "single", "caption": payload["positive_c"]},
                "items": [], "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx",
            }
            return Output(json.dumps(result), "")
        return Output("enhanced " + prompt, "")


class RegexReplace:
    @classmethod
    def execute(cls, text, pattern, replacement, **kwargs):
        return Output(re.sub(pattern, replacement, text, flags=re.S))


class DynamicPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = {"existing": object()}
        cls.module_patch = patch.dict(sys.modules, {
            "nodes": types.SimpleNamespace(NODE_CLASS_MAPPINGS=cls.registry, before_node_execution=lambda: None),
            "comfy_extras": types.ModuleType("comfy_extras"),
            "comfy_extras.nodes_textgen": types.SimpleNamespace(TextGenerate=TextGenerate),
            "comfy_extras.nodes_string": types.SimpleNamespace(RegexReplace=RegexReplace),
        })
        cls.module_patch.start()
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("moss_dynamic_test", root / "__init__.py",
                                                     submodule_search_locations=[str(root)])
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.node = cls.module.MOSSDynamicPrompt()

    @classmethod
    def tearDownClass(cls):
        cls.module_patch.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        TextGenerate.calls.clear()

    def arguments(self, **overrides):
        result = {}
        for name, spec in self.node.INPUT_TYPES()["required"].items():
            options = spec[1] if len(spec) > 1 else {}
            default = spec[0][0] if isinstance(spec[0], list) else ""
            result[name] = options.get("default", default)
        result.update(positive_a="subject", positive_b="", positive_c="scene",
                      wildcard_folder=str(self.folder), clip=object(), unique_id=self.id())
        result.update(overrides)
        return result

    def test_registration_preserves_comfy_registry(self):
        self.assertIn("MOSSDynamicPrompt", self.module.NODE_CLASS_MAPPINGS)
        self.assertEqual(list(self.registry), ["existing"])

    def test_recommended_modes(self):
        for mode in ("TEXT", "JSON", "TEXT_JSON"):
            with self.subTest(mode=mode):
                TextGenerate.calls.clear()
                result = self.node.generate(**self.arguments(
                    enhancer_mode=mode, settings_preset="recommended",
                    text_enhancer=False, text_thinking=True, json_thinking=True))
                self.assertEqual(len(result[0]), 1)
                self.assertIn("settings=recommended", result[1][0])
                self.assertEqual(len(TextGenerate.calls), 2 if mode == "TEXT_JSON" else 1)
                self.assertTrue(all(not thinking for _, thinking in TextGenerate.calls))
                json.loads(result[2][0])
        self.assertEqual(self.node.check_lazy_status("TEXT", False, settings_preset="recommended"), ["clip"])
        self.assertEqual(self.node.check_lazy_status("OFF", False, settings_preset="recommended"), [])

    def test_custom_reasoning_retry(self):
        result = self.node.generate(**self.arguments(
            enhancer_mode="TEXT", text_enhancer=True, text_thinking=True, settings_preset="custom"))
        self.assertEqual([thinking for _, thinking in TextGenerate.calls], [True, False])
        self.assertIn("enhanced scene", result[0][0])
        self.assertIn("reasoning-only retries: 1", result[1][0])

    def test_legacy_fallback_and_off(self):
        result = self.node.generate(**self.arguments(
            enhancer_mode="TEXT", text_enhancer=False, text_fallback="fallback"))
        self.assertIn("fallback", result[0][0])
        self.assertFalse(TextGenerate.calls)
        result = self.node.generate(**self.arguments(enhancer_mode="OFF", clip=None, settings_preset="recommended"))
        self.assertNotIn("scene", result[0][0])
        self.assertFalse(TextGenerate.calls)

    def test_file_order_and_trace(self):
        (self.folder / "values.txt").write_text(chr(10).join(["Z", "A", "M", ""]), encoding="utf-8")
        (self.folder / "nested.yaml").write_text(json.dumps({"group": {"child": ["Y", "X"]}}), encoding="utf-8")
        expander = self.module.MOSSLocalDynamicPrompt()
        for enabled in (False, True):
            self.assertEqual(expander.expand("__values__", "all_combinations", str(self.folder), 42, enabled)[0],
                             ["Z", "A", "M"])
            self.assertEqual(expander.expand("__group/child__", "all_combinations", str(self.folder), 42, enabled)[0],
                             ["Y", "X"])
        selected = []
        for _ in range(3):
            result = expander.expand("__values__", "random", str(self.folder), 42, True, unique_id=self.id())
            event = result[3][0]["events"][0]
            selected.append(event["sources"][0]["line"])
            self.assertEqual(event["sources"][0]["path"], "values.txt")
        self.assertEqual(set(selected), {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
