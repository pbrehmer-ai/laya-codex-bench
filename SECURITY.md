# Security policy

Do not include API keys, Codex authentication files, Hugging Face tokens, customer data, or unsanitized agent traces in issues or pull requests.

The public CI workflow intentionally performs only offline compilation and unit tests. Real Codex benchmarks should run on a trusted local machine. If remote execution is later added, use least-privilege permissions, trusted triggers, and secret isolation.

Report a suspected credential exposure privately to the repository owner and rotate the affected credential immediately.
