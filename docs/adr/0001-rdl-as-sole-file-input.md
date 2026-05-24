# Use Report Layout (.rdl) as the sole file input

The `.xsd` schema file sits alongside the `.rdl` and contains richer structural data: module, parameters, field types, lengths, and the complete block hierarchy. However, the `.xsd` is unavailable as an input in this context. The `.rdl` alone is used as the file input, which means module, parameters, and field types cannot be parsed — module and LU name are collected interactively, and parameters and field types are inferred by the LLM during the Generation Session and confirmed by the developer via the Field List review step before generation proceeds.

## Considered Options

- **`.rdl` + `.xsd`**: Would have given us module, all parameters, and typed field lengths for free, removing several interactive prompts and reducing LLM inference burden.
- **`.rdl` only**: Chosen. Requires two extra interactive prompts (module, LU name) and LLM inference for parameters and types, compensated by a mandatory developer-confirmation step on the Field List.
