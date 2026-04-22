# Contributing to EcoBarter (SwapSphere / TradeNexus)

First off, thank you for considering contributing to EcoBarter. It's people like you that make this open-source community to reinvent bartering possible!

This project adheres to a **Liberal Contribution Governance Model**. We believe in empowering our community, maintaining rapid innovation, and reducing bureaucracy for maintainers and contributors alike.

## Liberal Contribution Governance Model

The fundamental code of our liberal governance is simple:
1. **Trust by Default**: If an individual is willing to put in the time to write the code and tests, their judgment should be respected.
2. **Review for Quality, Not Preference**: Pull requests will be reviewed for security, architecture breaking, and bugs. We do not block PRs strictly for subjective styling or unopinionated structural choices unless they breach our explicit guidelines.
3. **Commit Access**: Contributors who land 3 substantial Pull Requests will automatically be granted write access to the repository.

### How to Contribute

#### 1. Found an Issue?
- Please check the existing Issues.
- If it's a bug, submit an issue and include reproduction steps. Better yet, submit a Pull Request solving it!

#### 2. Want to Propose a Feature?
- If it's small, feel free to submit a PR without asking.
- If it's a major architectural change or brand new microservice, please open a standard Discussion or Issue labeled `RFC` (Request for Comment). Wait a bit for feedback before drafting it all out.

#### 3. Submitting a Pull Request
- Create a fork / branch.
- Add tests where applicable.
- Ensure the CI (build / tests) passes.
- Provide a clear, detailed PR description.

### Code Guidelines
- Please utilize the standard formatters in our monorepo: `nx format:write`.
- Svelte components should rely on Tailwind classes where possible, moving complex scoped UI styles out of `<style>` tags unless structurally necessary.
- Python logic should be strictly typed using Pydantic.
- Go logic should be extremely concise and documented. Add unit tests for robust Trade Engine checks.

By contributing, you agree that your contributions will be licensed under its GNU AGPLv3 License.
