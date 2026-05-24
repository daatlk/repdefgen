# Use semantic vector index rather than symbol graph for codebase retrieval

A symbol graph (parsing `.view` column definitions and `.api` function signatures into a structured graph of nodes and edges) would give more precise retrieval — given the field name `CUSTOMER_NAME`, it could traverse to `customer_info_api.get_name()` directly. However, reliably parsing IFS PL/SQL into a symbol graph requires a robust parser that handles IFS-specific conventions and is expensive to build and maintain. Instead, `.view` files are chunked at column definition level and `.api`/`.apy` files at function/procedure level, embedded with `sentence-transformers`, and stored in ChromaDB. The LLM receives the top-k retrieved chunks as context and generates the cursor SQL from them. This degrades gracefully when field names don't match column names exactly, which is common in IFS reports where report attributes are computed expressions or API call results rather than direct column references.

## Considered Options

- **Symbol graph**: Higher precision for exact name lookups; would require parsing IFS PL/SQL reliably, which is complex given non-standard conventions (e.g. `&apos;` escaping, IFS-specific patterns).
- **Semantic vector index**: Chosen. Simpler to build and maintain, handles imprecise naming naturally, leverages the LLM's ability to reason over retrieved code chunks. Can be refined incrementally.
