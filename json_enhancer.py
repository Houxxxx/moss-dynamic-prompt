import json
import math

import re
import time

from comfy_extras.nodes_textgen import TextGenerate

from .wildcard_expander import MOSSLocalDynamicPrompt


def validate_json(raw):
    text = raw.strip()
    repaired = []
    if text.startswith('```') and text.endswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text, count=1)
        text = text[:-3].strip()
        repaired.append('removed code fence')
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f'duplicate key: {key}')
            result[key] = value
        return result
    try:
        data = json.loads(text, object_pairs_hook=pairs)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f'MOSS JSON invalid or truncated: {exc}. Increase max_length if truncated. No image generated.') from exc
    def require(condition, message):
        if not condition:
            raise ValueError('MOSS JSON: ' + message + '. No image generated.')
    require(isinstance(data, dict), 'root must be an object')
    summary = data.get('summary')
    require(isinstance(summary, dict), 'summary must be an object')
    require(isinstance(summary.get('meta'), list) and all(isinstance(x, str) for x in summary['meta']), 'summary.meta must be a string array')
    require(isinstance(summary.get('canvas'), str) and bool(summary['canvas']), 'summary.canvas must be a nonempty string')
    require(isinstance(summary.get('caption'), str) and bool(summary['caption'].strip()), 'summary.caption must be a nonempty string')
    require(data.get('bbox_coord_space') == 'abs_centralized', 'bbox_coord_space must be abs_centralized')
    require(data.get('bbox_format') == 'yxyx', 'bbox_format must be yxyx')
    require(isinstance(data.get('items'), list), 'items must be an array')
    for index, item in enumerate(data['items']):
        prefix = f'items[{index}]'
        require(isinstance(item, dict), prefix + ' must be an object')
        require(item.get('label') in ('object', 'text'), prefix + '.label must be object or text')
        require(isinstance(item.get('caption'), str) and bool(item['caption'].strip()), prefix + '.caption must be a nonempty string')
        if item['label'] == 'text':
            require(isinstance(item.get('text'), str), prefix + '.text must be a string')
        box = item.get('bbox')
        require(isinstance(box, list) and len(box) == 4, prefix + '.bbox must contain 4 numbers')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in box), prefix + '.bbox must contain finite numbers')
        if any(v < -512 or v > 512 for v in box):
            box = [max(-512, min(512, v)) for v in box]
            item['bbox'] = box
            repaired.append(prefix + '.bbox clipped to canvas [-512,512]')
        require(all(-512 <= v <= 512 for v in box), prefix + '.bbox out of range')
        require(box[0] < box[2] and box[1] < box[3], prefix + '.bbox requires ymin<ymax and xmin<xmax')
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), 'VALID' + (': ' + ', '.join(repaired) if repaired else '')


class MOSSJSONEnhancer:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'mode': (['OFF', 'TEXT', 'JSON', 'TEXT_JSON'], {'default': 'JSON'}),
            'positive_a': ('STRING', {'forceInput': True}),
            'positive_b': ('STRING', {'forceInput': True}),
            'dynamic_mode': ('STRING', {'forceInput': True}),
            'wildcard_folder': ('STRING', {'forceInput': True}),
            'seed': ('INT', {'forceInput': True}),
            'json_system': ('STRING', {'forceInput': True}),
            'width': ('INT', {'forceInput': True}),
            'height': ('INT', {'forceInput': True}),
            'max_length': ('INT', {'default': 4096, 'min': 1, 'max': 32768}),
            'temperature': ('FLOAT', {'default': 0.3, 'min': 0.01, 'max': 2.0, 'step': 0.01}),
            'thinking': ('BOOLEAN', {'default': False}),
        }, 'optional': {
            'clip': ('CLIP', {'lazy': True}),
            'c_expanded': ('STRING', {'forceInput': True, 'lazy': True}),
            'legacy_text': ('STRING', {'forceInput': True, 'lazy': True}),
            'c_enhanced': ('STRING', {'forceInput': True, 'lazy': True}),
            'legacy_c_enabled': ('BOOLEAN', {'default': False, 'forceInput': True}),
            'legacy_trace': ('MOSS_WILDCARD_TRACE', {'lazy': True}),
            'c_trace': ('MOSS_WILDCARD_TRACE', {'lazy': True}),
            'balanced_wildcards': ('BOOLEAN', {'default': False, 'forceInput': True}),
            'history_reset_interval': ('INT', {'default': -1, 'min': -1, 'forceInput': True}),
            'history_reset_token': ('INT', {'default': 0, 'min': 0, 'forceInput': True}),
        }, 'hidden': {'unique_id': 'UNIQUE_ID'}}

    RETURN_TYPES = ('STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('final_prompt', 'validation', 'wildcard_profile')
    OUTPUT_IS_LIST = (True, True, True)
    INPUT_IS_LIST = True
    FUNCTION = 'enhance'
    CATEGORY = 'MOSS/Prompts'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def check_lazy_status(self, mode, clip=None, c_expanded=None, legacy_text=None, c_enhanced=None, legacy_trace=None, c_trace=None, legacy_c_enabled=(False,), **kwargs):
        selected = mode[0]
        needed = {'JSON': {'clip': clip, 'c_expanded': c_expanded}, 'TEXT': {'legacy_text': legacy_text}, 'TEXT_JSON': {'clip': clip, 'c_expanded': c_expanded, 'c_enhanced': c_enhanced}, 'OFF': {}}[selected]
        trace_name = {'TEXT': 'legacy_trace', 'JSON': 'c_trace', 'TEXT_JSON': 'c_trace'}.get(selected)
        if trace_name:
            needed[trace_name] = legacy_trace if trace_name == 'legacy_trace' else c_trace
        if selected == 'TEXT' and legacy_c_enabled[0]:
            needed['c_trace'] = c_trace
        return [key for key, value in needed.items() if not value or value[0] is None]

    def enhance(self, mode, positive_a, positive_b, dynamic_mode, wildcard_folder, seed,
                json_system, width, height, max_length, temperature, thinking,
                clip=None, c_expanded=None, legacy_text=None, c_enhanced=None,
                balanced_wildcards=(False,), history_reset_interval=(-1,),
                history_reset_token=(0,), unique_id=None, legacy_trace=None, c_trace=None, legacy_c_enabled=(False,)):
        mode = mode[0]
        def profile(**stages):
            return json.dumps({'version': 1, 'enhancer_mode': mode, 'stages': stages}, ensure_ascii=False)

        if mode == 'TEXT':
            profiles = []
            for index, trace in enumerate(legacy_trace or [None] * len(legacy_text)):
                stages = {'final': trace}
                if legacy_c_enabled[0]:
                    stages['c'] = c_trace[min(index, len(c_trace) - 1)] if c_trace else None
                profiles.append(profile(**stages))
            return (legacy_text, ['TEXT: original enhancer path; A/B unchanged'], profiles)
        expander = MOSSLocalDynamicPrompt()
        balance_options = {
            'balanced_wildcards': balanced_wildcards[0],
            'history_reset_interval': history_reset_interval[0],
            'history_reset_token': history_reset_token[0],
            'unique_id': f'{unique_id}:ab',
        }
        marker = '\nMOSS_AB_BOUNDARY_7e1a9c\n'
        if marker in positive_a[0] or marker in positive_b[0]:
            raise ValueError('Reserved MOSS input separator found in A/B')
        if mode == 'OFF':
            source = ', '.join((positive_a[0], positive_b[0]))
            expanded, _, _, trace = expander.expand(source, dynamic_mode[0], wildcard_folder[0], seed[0], **balance_options)
            return (expanded, ['OFF: A+B only; LLM and JSON skipped'], [profile(ab=item) for item in trace])
        ab_values, _, _, ab_trace = expander.expand(positive_a[0] + marker + positive_b[0], dynamic_mode[0], wildcard_folder[0], seed[0], **balance_options)
        if mode == 'TEXT_JSON' and len(c_expanded) != len(c_enhanced):
            raise ValueError('MOSS TEXT_JSON: original/enhanced C list lengths differ; refusing mismatched combinations.')
        prompts, statuses, profiles = [], [], []
        for ab, trace in zip(ab_values, ab_trace):
            a, b = ab.split(marker, 1)
            for c_index, c in enumerate(c_expanded):
                payload = json.dumps({'positive_a': a, 'positive_b': b, 'positive_c': c,
                                      'image_width': width[0], 'image_height': height[0]}, ensure_ascii=False)
                if mode == 'TEXT_JSON':
                    data = json.loads(payload)
                    enhanced = c_enhanced[c_index].strip()
                    if not enhanced:
                        raise ValueError('MOSS TEXT_JSON: TEXT enhancer returned empty C. No image generated.')
                    data['positive_c_enhanced'] = enhanced
                    payload = json.dumps(data, ensure_ascii=False)
                started = time.perf_counter()
                def generate(request):
                    sampling = {'sampling_mode': 'on', 'temperature': temperature[0], 'top_k': 64,
                                'top_p': 0.95, 'min_p': 0.05, 'repetition_penalty': 1.05,
                                'presence_penalty': 0.0, 'seed': seed[0]}
                    output = TextGenerate.execute(clip[0], request, max_length[0], sampling,
                                                  thinking=thinking[0], use_default_template=True,
                                                  mtp='off', system_prompt=json_system[0])
                    if not output.result[0].strip() and output.result[1].strip():
                        output = TextGenerate.execute(clip[0], request, max_length[0], sampling,
                                                      thinking=False, use_default_template=True,
                                                      mtp='off', system_prompt=json_system[0])
                    return output.result[0]
                raw = generate(payload)
                if not raw:
                    raise ValueError('MOSS JSON: empty/truncated generation; increase max_length. No image generated.')
                try:
                    prompt, status = validate_json(raw)
                except ValueError as exc:
                    repair_request = json.dumps({'original_input': json.loads(payload), 'invalid_output': raw,
                        'validation_error': str(exc), 'task': 'Repair the JSON using the required schema. Preserve original input meaning. label must be object or text. summary.meta is an array of short style strings, closed with ] before canvas. Return ONLY the complete corrected JSON.'}, ensure_ascii=False)
                    raw = generate(repair_request)
                    try:
                        prompt, status = validate_json(raw)
                    except ValueError:
                        print('MOSS rejected JSON after one repair:\n' + raw)
                        raise
                    status += '; LLM repair=1'
                prompts.append(prompt)
                profiles.append(profile(ab=trace, c=c_trace[c_index] if c_trace else None))
                statuses.append(f'{status}; mode={mode}; json_stage={time.perf_counter()-started:.3f}s; seed={seed[0]}; bbox is estimated')
        return (prompts, statuses, profiles)
