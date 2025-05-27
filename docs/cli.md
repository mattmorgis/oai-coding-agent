```mermaid
flowchart TD
  subgraph CLI
    A[oai CLI entrypoint] -->|flags| B[main command]
  end
  B --> C[prompt-toolkit REPL]
  C -->|user message| D[Agent backend]
  D -->|stream chunks| E[Rich Markdown renderer]
  D -->|file operations / commands| F[Rich Live log panel]
```
