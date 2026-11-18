from dataclasses import dataclass, field
from math import isfinite
from threading import RLock

import yaml
from dynamicprompts.utils import is_empty_line

from dynamicprompts.generators import RandomPromptGenerator
from dynamicprompts.wildcards.values import WildcardValues


class SourceMarks:
    def __init__(self, node):
        self.node = node

    def __getitem__(self, key):
        return SourceMarks(next(value for name, value in self.node.value if name.value == str(key)))

    def candidates(self):
        for item in self.node.value:
            if isinstance(item, yaml.ScalarNode):
                candidate = BalancedValues.candidate(item.value)[0]
            elif isinstance(item, yaml.MappingNode):
                fields = {key.value: value.value for key, value in item.value}
                candidate = fields.get("text") or fields.get("content")
            else:
                continue
            yield item.start_mark.line + 1, candidate


@dataclass
class Bag:
    signature: tuple
    remaining: list = field(default_factory=list)
    last: str | None = None

    def choose(self, rng):
        if not self.remaining:
            self.remaining = list(self.signature)
            eligible = [i for i, (value, _) in enumerate(self.remaining) if value != self.last]
        else:
            eligible = []
        if not eligible:
            eligible = range(len(self.remaining))
        weights = [self.remaining[i][1] for i in eligible]
        index = rng.choices(eligible, weights=weights)[0] if any(weights) else rng.choice(eligible)
        self.last, _ = self.remaining.pop(index)
        return self.last


class BalancedValues(WildcardValues):
    def __init__(self, items, bags, key, report):
        super().__init__(items)
        self.bags = bags
        self.key = key
        self.report = report
        self.signature = tuple(sorted(self.candidate(item) for item in items))

    @staticmethod
    def candidate(item):
        value = str(item)
        weight = getattr(item, "weight", 1.0)
        # MOSS loads YAML string entries as-is, including leading weight markers.
        if isinstance(item, str):
            prefix, separator, content = value.partition("::")
            if separator:
                try:
                    weight = float(prefix)
                except ValueError:
                    pass
                else:
                    value = content
        return value, weight if isfinite(weight) and weight >= 0 else 0.0

    def get_weighted_random_generator(self, rng):
        while True:
            bag = self.bags.get(self.key)
            if bag is None or bag.signature != self.signature:
                bag = self.bags[self.key] = Bag(self.signature)
            selected = bag.choose(rng)
            self.report(selected, len(bag.remaining), len(bag.signature))
            yield selected


class BalancedManager:
    def __init__(self, manager, bags, sources, events):
        self.manager = manager
        self.bags = bags
        self.sources = sources
        self.events = events
        self.names = {
            id(manager.get_file(name)): name for name in manager.get_collection_names()
        }

    def __getattr__(self, name):
        return getattr(self.manager, name)

    def get_values(self, wildcard):
        values = self.manager.get_values(wildcard)
        if not values:
            self.manager.clear_cache()
            values = self.manager.get_values(wildcard)
            if not values:
                self.events.append({"query": wildcard, "status": "unresolved"})
                return values

        collections = list(self.manager.match_collections(wildcard))
        if not any(collection.get_values() for collection in collections):
            if not wildcard.startswith("**"):
                collections = self.manager.match_collections(f"**/{wildcard}")
        key = tuple(sorted(self.names[id(collection)] for collection in collections))
        def report(selected, remaining, candidate_count):
            matches = []
            for name in key:
                path, marks = self.sources.get(name, (None, None))
                if path is None:
                    continue
                if marks is None:
                    lines = self.manager.get_file(name).read_text().splitlines()
                    candidates = ((index, line.strip()) for index, line in enumerate(lines, 1) if not is_empty_line(line))
                else:
                    candidates = marks.candidates()
                matches.extend({"collection": name, "path": path, "line": index}
                               for index, value in candidates if BalancedValues.candidate(value or "")[0] == selected)
            self.events.append({"query": wildcard, "status": "selected", "sources": matches,
                                "candidate_count": candidate_count, "remaining": remaining})

        return BalancedValues(values.items, self.bags, key or wildcard, report)


@dataclass
class History:
    bags: dict = field(default_factory=dict)
    count: int = 0
    reset_token: int = 0


_histories = {}
_lock = RLock()


def generate_balanced(manager, namespace, text, seed, interval, reset_token, sources=None, events=None):
    with _lock:
        history = _histories.setdefault(namespace, History())
        if history.reset_token != reset_token or (interval > 0 and history.count >= interval):
            history.bags.clear()
            history.count = 0
        history.reset_token = reset_token
        generator = RandomPromptGenerator(wildcard_manager=BalancedManager(manager, history.bags, sources or {}, events if events is not None else []))
        prompts = generator.generate(text, num_images=1, seeds=seed)
        history.count += len(prompts)
        return prompts, len(history.bags), history.count
