# RepDefGen Architecture

```mermaid
graph TB
    subgraph Developer["👨‍💻 Developer"]
        CLI["CLI\nrepdefgen index\nrepdefgen generate"]
        Browser["Browser\nlocalhost:5173 / :8000"]
    end

    subgraph WebUI["🌐 Web UI  (React + Vite + Tailwind)"]
        Upload["Step 1 — Upload\nDrag-drop .rdl\nLU / Module / Description"]
        Review["Step 2 — Review\nField List chat\nCorrections loop"]
        Preview["Step 3 — Preview\nSyntax-highlighted viewer\nDownload .rdf / .report"]
        Upload -->|sessionId + proposal| Review
        Review -->|sessionId + files| Preview
    end

    subgraph API["⚡ FastAPI Backend  (repdefgen/api.py)"]
        Sessions["Session Store\nUUID → SessionState\nin-memory dict"]
        Routes["REST Routes\nPOST /api/sessions\nPOST .../field-list\nPOST .../generate\nPOST .../correct\nGET  .../download/:file"]
        Static["StaticFiles\nserves ui/dist/"]
    end

    subgraph Core["🐍 Core Python Modules"]
        Parser["rdl_parser.py\nparse() → ParsedRDL\nblocks · fields · title"]
        Retriever["retriever.py\nquery() top-8 chunks\nembeds with MiniLM"]
        Generator["generator.py\npropose_field_list()\ngenerate_files()\napply_correction()"]
        Session["session.py\nSession class\nfull message history\nclaude-sonnet-4-6"]
        Indexer["indexer.py\nbuild_index()\nchunks .view/.api/.apy\nbatch upsert"]
        CLI_cmd["cli.py\nindex command\ngenerate command"]
    end

    subgraph External["☁️ External Services"]
        Claude["Anthropic\nClaude Sonnet 4.6\nAPI"]
    end

    subgraph LocalData["💾 Local Data"]
        BuildHome["IFS Build Home\n.api / .apy / .view\n~26k files"]
        ChromaDB[("ChromaDB\n.repdefgen/index/\nrepdefgen_index collection")]
        TempFiles["Temp Files\nper-session dir\nuploaded .rdl\ngenerated .rdf/.report"]
        Samples["Sample Files\nsample/wo/\nsample/srvquo/\nstructural skeletons"]
    end

    %% Developer interactions
    Browser -->|HTTP| Static
    Browser <-->|/api/*| Routes
    CLI --> CLI_cmd

    %% Web UI ↔ API
    Upload <-->|multipart RDL upload| Routes
    Review <-->|JSON messages| Routes
    Preview <-->|JSON files / download| Routes

    %% API internals
    Routes <--> Sessions
    Routes --> Parser
    Routes --> Retriever
    Routes --> Generator
    Routes --> Session
    Sessions --> TempFiles

    %% CLI internals
    CLI_cmd --> Indexer
    CLI_cmd --> Parser
    CLI_cmd --> Retriever
    CLI_cmd --> Generator
    CLI_cmd --> Session

    %% Core module connections
    Indexer -->|embed chunks| ChromaDB
    Indexer -->|scan files| BuildHome
    Retriever -->|query top-k| ChromaDB
    Generator -->|load skeletons| Samples
    Session -->|messages API| Claude
    Parser -->|parse XML| TempFiles

    %% Styling
    classDef ui fill:#1e1b4b,stroke:#6366f1,color:#e0e7ff
    classDef api fill:#0c4a6e,stroke:#0ea5e9,color:#e0f2fe
    classDef core fill:#14532d,stroke:#22c55e,color:#dcfce7
    classDef ext fill:#451a03,stroke:#f59e0b,color:#fef3c7
    classDef data fill:#1c1917,stroke:#78716c,color:#d6d3d1
    classDef dev fill:#1e293b,stroke:#64748b,color:#cbd5e1

    class Upload,Review,Preview ui
    class Sessions,Routes,Static api
    class Parser,Retriever,Generator,Session,Indexer,CLI_cmd core
    class Claude ext
    class BuildHome,ChromaDB,TempFiles,Samples data
    class CLI,Browser dev
```

## Component Summary

| Component | Role |
|-----------|------|
| **React UI** | Three-step wizard — upload, field list review (chat), preview & download |
| **FastAPI** | Thin HTTP wrapper; holds session state; routes calls to core modules |
| **rdl_parser** | Extracts report name, block hierarchy, field names from `.rdl` XML |
| **retriever** | Embeds query with MiniLM; fetches top-8 chunks from ChromaDB |
| **generator** | Builds prompts; calls Claude for field list, file generation, corrections |
| **session** | Wraps Anthropic SDK; maintains full conversation history across all phases |
| **indexer** | Scans Build Home; chunks `.view` at column level, `.api/.apy` at proc level; upserts to ChromaDB |
| **ChromaDB** | Local vector store at `.repdefgen/index/`; `all-MiniLM-L6-v2` embeddings |
| **Claude Sonnet 4.6** | Proposes field lists, generates `.rdf` + `.report`, applies corrections |

## Data Flow — Generate Workflow

```
.rdl file
    │
    ▼
rdl_parser ──► ParsedRDL (report_name, blocks, visible fields)
    │
    ▼
retriever ──► ChromaDB query ──► top-8 relevant code chunks
    │
    ▼
generator.propose_field_list ──► Claude ──► Field List proposal
    │
    ▼
[developer reviews, corrects in chat loop]
    │
    ▼
generator.generate_files ──► Claude (8192 tokens) ──► .rdf + .report content
    │
    ▼
[developer applies SQL corrections]
    │
    ▼
generator.apply_correction ──► Claude ──► updated .rdf
    │
    ▼
Download .rdf  +  .report
```
