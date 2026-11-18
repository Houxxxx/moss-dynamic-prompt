import json
from pathlib import Path

import yaml
from dynamicprompts.generators import CombinatorialPromptGenerator, RandomPromptGenerator
from dynamicprompts.wildcards import WildcardManager
from dynamicprompts.wildcards.collection.list import ListWildcardCollection
from dynamicprompts.wildcards.collection import WildcardTextFile
from dynamicprompts.wildcards.item import WildcardItem

from .balanced_wildcards import SourceMarks, generate_balanced


def structured_entries(data, prefix, sources=None, document=None, path=None):
    for key, value in data.items():
        name = f"{prefix}/{key}".strip("/")
        if isinstance(value, dict):
            child = document[key] if document is not None else None
            yield from structured_entries(value, name, sources, child, path)
        elif isinstance(value, list):
            entries = []
            for item in value:
                if isinstance(item, str):
                    entries.append(item)
                elif isinstance(item, dict):
                    content = item.get("text") or item.get("content")
                    if content:
                        entries.append(WildcardItem(content=content, weight=float(item.get("weight", 1))))
            if sources is not None:
                sources[name] = (path, document[key])
            yield name, ListWildcardCollection(entries)


def wildcard_manager(folder, sources=None):
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Wildcard folder not found: {root}")
    collections = {}
    fallback = Path(__file__).parent.parent / "comfyui-dynamicprompts" / "wildcards"
    roots = [fallback, root] if fallback.is_dir() and fallback != root else [root]
    for source in roots:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".txt":
                name = path.relative_to(source).with_suffix("").as_posix()
                collections[name] = WildcardTextFile(path)
                if sources is not None:
                    sources[name] = (path.relative_to(source).as_posix(), None)
            elif path.suffix.lower() in (".yaml", ".yml", ".json"):
                text = path.read_text(encoding="utf-8-sig")
                data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
                prefix = path.parent.relative_to(source).as_posix().strip(".").strip("/")
                if isinstance(data, dict):
                    marks = SourceMarks(yaml.compose(text)) if sources is not None else None
                    collections.update(structured_entries(data, prefix, sources, marks, path.relative_to(source).as_posix()))
                elif isinstance(data, list):
                    name = path.relative_to(source).with_suffix("").as_posix()
                    collections[name] = ListWildcardCollection([x for x in data if isinstance(x, str)])
                    if sources is not None:
                        sources[name] = (path.relative_to(source).as_posix(), SourceMarks(yaml.compose(text)))
    return WildcardManager(root_map={"": [collections]})


class MOSSLocalDynamicPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "text": ("STRING", {"forceInput": True}),
            "mode": ("STRING", {"forceInput": True}),
            "wildcard_folder": ("STRING", {"forceInput": True}),
            "seed": ("INT", {"forceInput": True}),
        }, "optional": {
            "balanced_wildcards": ("BOOLEAN", {"default": False, "forceInput": True}),
            "history_reset_interval": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
            "history_reset_token": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
        }, "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("STRING", "INT", "STRING", "MOSS_WILDCARD_TRACE")
    RETURN_NAMES = ("prompts", "count", "summary", "wildcard_trace")
    OUTPUT_IS_LIST = (True, False, False, True)
    FUNCTION = "expand"
    CATEGORY = "MOSS/Prompts"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def expand(
        self, text, mode, wildcard_folder, seed, balanced_wildcards=False,
        history_reset_interval=-1, history_reset_token=0, unique_id=None,
    ):
        balanced = balanced_wildcards and mode != "all_combinations"
        sources = {} if balanced else None
        events = []
        balanced_status = ""
        if not text:
            # An empty C field is a valid workflow input.
            prompts = [""]
        elif mode == "all_combinations":
            manager = wildcard_manager(wildcard_folder)
            prompts = CombinatorialPromptGenerator(wildcard_manager=manager).generate(text, max_prompts=None)
        elif balanced:
            manager = wildcard_manager(wildcard_folder, sources)
            namespace = (Path(wildcard_folder).expanduser().resolve(), unique_id)
            prompts, bag_count, prompt_count = generate_balanced(
                manager, namespace, text, seed, history_reset_interval, history_reset_token,
                sources, events,
            )
            balanced_status = f" Balanced wildcard v4 native-recursion: {bag_count} collection(s), {prompt_count} prompt(s)."
        else:
            manager = wildcard_manager(wildcard_folder)
            prompts = RandomPromptGenerator(wildcard_manager=manager).generate(text, num_images=1, seeds=seed)
        count = len(prompts)
        summary = f"{mode}: {count} prompt(s). One run processes this entire list."
        trace = {"balanced": balanced, "mode": mode, "seed": str(seed), "events": events}
        return (prompts, count, summary + balanced_status, [trace] * count)
