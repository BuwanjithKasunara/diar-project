# Benchmarks and rules

Benchmarks are curated evidence expectations, not validated hiring standards. Canonical concepts and every capability member must resolve to the taxonomy. API startup rejects unknown concepts.

## Version 3 capability model

AI Engineer uses six weighted any-of capabilities:

- Programming (`0.20`): Python, C, C++, Java, JavaScript, TypeScript, Go, or Rust.
- ML foundations (`0.25`): machine learning, deep learning, neural networks, or statistics.
- AI specialisation (`0.20`): LLMs, generative AI, NLP, computer vision, reinforcement learning, AI agents, or RAG.
- Model tooling (`0.15`): PyTorch, TensorFlow, Keras, scikit-learn, Hugging Face, transformers, CUDA, JAX, LangChain, or LangGraph.
- Delivery (`0.15`): MLOps, Docker, Kubernetes, FastAPI, REST APIs, AWS/Azure/GCP, CI/CD, system design, or model evaluation.
- Data systems (`0.05`): SQL, pandas, NumPy, ETL, data analysis, or vector databases.

Any one supported member can satisfy a capability at that evidence strength. Evidence for one capability does not imply another: an LLM match supports AI specialisation but cannot invent SQL or delivery evidence.

Software Engineer, Data Scientist, Researcher, and Entrepreneur initially model each existing required or preferred skill as an individual capability. Required capabilities collectively carry `0.70` and preferred capabilities `0.30`, distributed evenly within each non-empty group. Researcher and Entrepreneur retain optional-GitHub expectations.

Rules connect capability states, experience evidence, source scope, and visibility to explained suggestions. `not_assessed` prompts clarification. `not_observed` can produce one grouped request to supply or document evidence, not a claim that a skill is missing. Only `explicit_gap` or verified experience below the benchmark can produce a development recommendation.

Repository counts, push ratios, language diversity, and unmatched certifications do not automatically produce recommendations. Project actions ask the user to supply or document relevant project evidence; project keywords indicate relevance only, never quality. Privacy Focused favours private evidence/selective sharing, Semi-Public favours controlled exposure, and Fully Public permits public showcasing.

Version benchmark changes and document rationale. Substantive scoring/privacy changes require an [ADR](../adr/README.md); version 3 is governed by [ADR 0007](../adr/0007-capability-evidence-scoring.md).

