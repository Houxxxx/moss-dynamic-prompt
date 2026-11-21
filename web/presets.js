import { app } from "../../scripts/app.js";

const textFields = new Set([
    "text_system", "text_max_length", "text_sampling", "text_temperature", "text_top_k",
    "text_top_p", "text_min_p", "text_repetition_penalty", "text_presence_penalty",
    "text_thinking", "text_use_default_template", "text_mtp",
]);
const jsonFields = new Set(["json_system", "json_max_length", "json_temperature", "json_thinking"]);

app.registerExtension({
    name: "MOSS.EnhancementPresets",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MOSSDynamicPrompt") return;
        function update(node) {
            const values = Object.fromEntries((node.widgets || []).map(widget => [widget.name, widget.value]));
            const custom = values.settings_preset === "custom";
            const text = values.enhancer_mode === "TEXT_JSON" ||
                (values.enhancer_mode === "TEXT" && values.text_enhancer);
            const json = values.enhancer_mode === "JSON" || values.enhancer_mode === "TEXT_JSON";
            for (const widget of node.widgets || []) {
                let visible;
                if (textFields.has(widget.name)) visible = custom && text;
                else if (jsonFields.has(widget.name)) visible = custom && json;
                else if (widget.name === "text_enhancer") visible = custom && values.enhancer_mode === "TEXT";
                else if (widget.name === "text_fallback") visible = custom && values.enhancer_mode === "TEXT" && !values.text_enhancer;
                else continue;
                // A connected widget belongs to the workflow input.
                if (node.inputs?.some(input => input.name === widget.name && input.link != null)) continue;
                widget.hidden = !visible;
                if (widget.element) widget.element.style.display = visible ? "" : "none";
                if (widget.inputEl) widget.inputEl.style.display = visible ? "" : "none";
            }
            node.setSize([node.size[0], node.computeSize()[1]]);
            node.setDirtyCanvas(true, true);
        }
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = onCreated?.apply(this, args);
            for (const widget of this.widgets || []) {
                if (!["settings_preset", "enhancer_mode", "text_enhancer"].includes(widget.name)) continue;
                const callback = widget.callback;
                widget.callback = (...values) => {
                    const result = callback?.apply(widget, values);
                    update(this);
                    return result;
                };
            }
            update(this);
            return result;
        };
        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = onConfigure?.apply(this, args);
            update(this);
            return result;
        };
    },
});
