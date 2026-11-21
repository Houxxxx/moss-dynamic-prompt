import nodes
from comfy_extras.nodes_string import RegexReplace
from comfy_extras.nodes_textgen import TextGenerate

from .presets import TEXT_SYSTEM, JSON_SYSTEM
from .wildcard_expander import MOSSLocalDynamicPrompt
from .json_enhancer import MOSSJSONEnhancer


class MOSSDynamicPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        schema = {
            "required": {
                "positive_a": ("STRING", {"multiline": True}),
                "positive_b": ("STRING", {"multiline": True}),
                "positive_c": ("STRING", {"multiline": True}),
                "wildcard_folder": ("STRING", {"default": ""}),
                "generation_mode": (["random", "all_combinations"],),
                "balanced_wildcards": ("BOOLEAN", {"default": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "history_reset_interval": ("INT", {"default": -1, "min": -1}),
                "history_reset_token": ("INT", {"default": 0, "min": 0}),
                "enhancer_mode": (["TEXT", "OFF", "JSON", "TEXT_JSON"],),
                "text_enhancer": ("BOOLEAN", {"default": True}),
                "text_fallback": ("STRING", {"multiline": True}),
                "text_system": ("STRING", {"multiline": True, "default": TEXT_SYSTEM}),
                "json_system": ("STRING", {"multiline": True, "default": JSON_SYSTEM}),
                "width": ("INT", {"default": 1024, "min": 1}),
                "height": ("INT", {"default": 1024, "min": 1}),
                "text_max_length": ("INT", {"default": 1024, "min": 1, "max": 32768}),
                "text_sampling": (["on", "off"],),
                "text_temperature": ("FLOAT", {"default": 0.7, "min": 0.01, "max": 2.0}),
                "text_top_k": ("INT", {"default": 64, "min": 0, "max": 1000}),
                "text_top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0}),
                "text_min_p": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "text_repetition_penalty": ("FLOAT", {"default": 1.05, "min": 0.0, "max": 5.0}),
                "text_presence_penalty": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 5.0}),
                "text_thinking": ("BOOLEAN", {"default": False}),
                "text_use_default_template": ("BOOLEAN", {"default": True}),
                "text_mtp": (["auto", "off", "2", "3", "4", "5"], {"default": "off"}),
                "json_max_length": ("INT", {"default": 4096, "min": 1, "max": 32768}),
                "json_temperature": ("FLOAT", {"default": 0.3, "min": 0.01, "max": 2.0}),
                "json_thinking": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "clip": ("CLIP", {"lazy": True}),
                "settings_preset": (["recommended", "custom"], {
                    "default": "recommended", "display_name": "補強プリセット",
                    "tooltip": "recommendedは補強方式に合う設定を自動適用。customで詳細設定を表示します。",
                }),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }
        labels = {
            "positive_a": "A｜基本プロンプト",
            "positive_b": "B｜追加プロンプト",
            "positive_c": "C｜シーン原文",
            "wildcard_folder": "ワイルドカードフォルダ",
            "generation_mode": "展開方式（ランダム／全組み合わせ）",
            "balanced_wildcards": "Balanced（ランダムの重複を抑える）",
            "seed": "共通シード",
            "history_reset_interval": "履歴リセット間隔（-1で無効）",
            "history_reset_token": "履歴リセット番号（変更するとリセット）",
            "enhancer_mode": "プロンプト補強方式",
            "text_enhancer": "TEXTモードでC欄をLLM補強",
            "text_fallback": "C｜TEXT補強オフ時の文",
            "text_system": "TEXT用システムプロンプト",
            "json_system": "JSON用システムプロンプト",
            "width": "画像の幅",
            "height": "画像の高さ",
            "text_max_length": "TEXT｜最大トークン数",
            "text_sampling": "TEXT｜サンプリング",
            "text_temperature": "TEXT｜温度",
            "text_top_k": "TEXT｜Top-K",
            "text_top_p": "TEXT｜Top-P",
            "text_min_p": "TEXT｜Min-P",
            "text_repetition_penalty": "TEXT｜反復ペナルティ",
            "text_presence_penalty": "TEXT｜存在ペナルティ",
            "text_thinking": "TEXT｜Thinking",
            "text_use_default_template": "TEXT｜既定のチャットテンプレート",
            "text_mtp": "TEXT｜MTP",
            "json_max_length": "JSON｜最大トークン数",
            "json_temperature": "JSON｜温度",
            "json_thinking": "JSON｜Thinking",
        }
        for name, label in labels.items():
            spec = schema["required"][name]
            schema["required"][name] = (spec[0], dict(spec[1] if len(spec) > 1 else {}, display_name=label))
        schema["optional"]["clip"][1]["display_name"] = "補強用CLIP"
        return schema

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("最終プロンプト", "補強ステータス", "ワイルドカード履歴", "プロンプト総数")
    OUTPUT_IS_LIST = (True, True, True, False)
    FUNCTION = "generate"
    CATEGORY = "MOSS/Prompts"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def check_lazy_status(self, enhancer_mode, text_enhancer, clip=None, settings_preset="custom", **kwargs):
        text_enhancer = settings_preset == "recommended" or text_enhancer
        if clip is None and (enhancer_mode in ("JSON", "TEXT_JSON") or (enhancer_mode == "TEXT" and text_enhancer)):
            return ["clip"]
        return []

    def generate(self, positive_a, positive_b, positive_c, wildcard_folder, generation_mode,
                 balanced_wildcards, seed, history_reset_interval, history_reset_token,
                 enhancer_mode, text_enhancer, text_fallback, text_system, json_system, width, height,
                 text_max_length, text_sampling, text_temperature, text_top_k, text_top_p,
                 text_min_p, text_repetition_penalty, text_presence_penalty, text_thinking,
                 text_use_default_template, text_mtp, json_max_length, json_temperature,
                 json_thinking, clip=None, unique_id=None, settings_preset="custom"):
        if settings_preset == "recommended":
            text_enhancer = True
            text_system = TEXT_SYSTEM
            json_system = JSON_SYSTEM
            text_max_length = 1024
            text_sampling = "on"
            text_temperature = 0.7
            text_top_k = 64
            text_top_p = 0.95
            text_min_p = 0.05
            text_repetition_penalty = 1.05
            text_presence_penalty = 0.0
            text_thinking = False
            text_use_default_template = True
            text_mtp = "off"
            json_max_length = 4096
            json_temperature = 0.3
            json_thinking = False
        use_text = enhancer_mode == "TEXT_JSON" or (enhancer_mode == "TEXT" and text_enhancer)
        if clip is None and (use_text or enhancer_mode == "JSON"):
            raise ValueError("Connect the enhancer CLIP input for this mode.")

        expander = MOSSLocalDynamicPrompt()
        enhancer = MOSSJSONEnhancer()
        expand_args = (generation_mode, wildcard_folder, seed, balanced_wildcards,
                       history_reset_interval, history_reset_token)
        c_expanded, c_trace, c_enhanced = [], [], []
        if use_text or enhancer_mode == "JSON":
            c_expanded, _, _, c_trace = expander.expand(positive_c, *expand_args, unique_id=f"{unique_id}:c")
        text_retries = 0
        if use_text:
            sampling = {
                "sampling_mode": text_sampling, "temperature": text_temperature, "top_k": text_top_k,
                "top_p": text_top_p, "min_p": text_min_p, "seed": seed,
                "repetition_penalty": text_repetition_penalty, "presence_penalty": text_presence_penalty,
            }
            for text in c_expanded:
                nodes.before_node_execution()
                output = TextGenerate.execute(clip, text, text_max_length, sampling, thinking=text_thinking,
                                              use_default_template=text_use_default_template, mtp=text_mtp,
                                              system_prompt=text_system)
                if not output.result[0].strip() and output.result[1].strip():
                    nodes.before_node_execution()
                    output = TextGenerate.execute(clip, text, text_max_length, sampling, thinking=False,
                                                  use_default_template=text_use_default_template, mtp=text_mtp,
                                                  system_prompt=text_system)
                    text_retries += 1
                cleaned = RegexReplace.execute(output.result[0], r"\s*NEGATIVE(?:\s*PROMPT)?\s*:.*$", "", dotall=True)
                if not cleaned.result[0].strip():
                    raise ValueError("TEXT enhancement returned an empty C prompt. Increase TEXT max tokens or disable Thinking.")
                c_enhanced.append(cleaned.result[0])

        legacy_text, legacy_trace = [], []
        if enhancer_mode == "TEXT":
            for c in c_enhanced if use_text else (text_fallback,):
                nodes.before_node_execution()
                prompts, _, _, trace = expander.expand(", ".join((positive_a, positive_b, c)), *expand_args,
                                                       unique_id=f"{unique_id}:final")
                legacy_text.extend(prompts)
                legacy_trace.extend(trace)

        final, validation, profiles = enhancer.enhance(
            (enhancer_mode,), (positive_a,), (positive_b,), (generation_mode,), (wildcard_folder,),
            (seed,), (json_system,), (width,), (height,), (json_max_length,), (json_temperature,),
            (json_thinking,), clip=(clip,), c_expanded=c_expanded, legacy_text=legacy_text,
            c_enhanced=c_enhanced, balanced_wildcards=(balanced_wildcards,),
            history_reset_interval=(history_reset_interval,), history_reset_token=(history_reset_token,),
            unique_id=unique_id, legacy_trace=legacy_trace, c_trace=c_trace, legacy_c_enabled=(use_text,),
        )
        if use_text:
            detail = f"TEXT C enhanced: {len(c_enhanced)} prompt(s); reasoning-only retries: {text_retries}"
            validation = [f"{status}; {detail}" for status in validation]
        validation = [f"{status}; settings={settings_preset}" for status in validation]
        return (final, validation, profiles, len(final))


NODE_CLASS_MAPPINGS = {"MOSSDynamicPrompt": MOSSDynamicPrompt}
NODE_DISPLAY_NAME_MAPPINGS = {"MOSSDynamicPrompt": "MOSS Dynamic Prompt"}
WEB_DIRECTORY = "./web"
