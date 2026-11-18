# MOSS Dynamic Prompt specification

The pack registers `MOSSDynamicPrompt` with the same input names and output order as the integrated V5 workflow. Its wildcard expander, Balanced history, and JSON enhancer are bundled as internal modules to avoid requiring the older custom node packs.

Inputs cover A/B/C, a local wildcard root, random or exhaustive mode, seed, Balanced and history resets, enhancer settings, image dimensions, and optional enhancer CLIP. Outputs are the final prompt list, validation messages, matching wildcard profiles, and the final prompt count.

- OFF expands A and B.
- TEXT expands A and B with either the text fallback or the enhanced C input.
- JSON builds structured prompts from the A/B and C combinations.
- TEXT_JSON enhances C before structured prompt generation.

Dependencies are declared in `requirements.txt` and `pyproject.toml`. The pack uses ComfyUI's local TextGenerate and RegexReplace. Private prompt data and models are supplied separately by the user.
