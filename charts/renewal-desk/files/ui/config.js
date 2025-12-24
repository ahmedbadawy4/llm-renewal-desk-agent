window.RUNTIME_CONFIG = {
  API_BASE_URL: "http://localhost:8000",
  DEFAULT_LLM_PROVIDER: "mock",
  LLM_OPTIONS: [
    { value: "mock", label: "Mock (heuristic)" },
    { value: "ollama", label: "Ollama" },
  ],
  OLLAMA_BASE_URL: "http://localhost:11434",
  OLLAMA_MODEL: "llama3.1:8b",
};
