```mermaid
flowchart TD
  subgraph CLI
    A[oai CLI entrypoint] -->|flags| B[main command]
    B --> P[Preflight checks (Git, Node.js, Docker)]
  end
  P -->|success| H[Headless mode]
  P -->|success| C[prompt-toolkit REPL]
  P -->|failure| G[Print errors & exit]
  H --> D[Agent backend]
  C -->|user input| D
  D -->|assistant messages| E[Rich Markdown renderer]
  D -->|tool events| F[Inline tool output]
```