# Changelog

All notable changes to PrioritySuite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-20

### Added
- In-app User Administration for staff and superusers with user creation,
  profile editing, password reset, and account deletion.
- Metadata-only visibility in user administration to guarantee administrator
  isolation from user private frameworks, Whys, objectives, and decisions.
- Strict Django Admin privacy isolation preventing superusers from querying
  or inspecting other users' framework and decision records.
- Self-service user profile editing (name, email) and password change in
  account settings.
- Multi-framework management: framework switcher dropdown and CRUD actions
  (create, edit, delete) in workspace.
- Global navigation link and workspace button for the Thinking Partner LLM
  chat.
- Application version display in the global footer and template context
  processor.
- Specification update documenting administrator privacy boundaries and a
  future roadmap for PBKDF2/Argon2id encryption at rest for user data.

### Changed
- Bumped package version to 0.2.0 across configuration and project metadata.

## [0.1.0] - 2026-11-19

### Added
- Core personal priorities architecture: Frameworks, Domains, Whys,
  Objectives, and Goals.
- Cross-domain Decision Assessment matrix with tension analysis, confidence
  ratings, and alternatives.
- Periodic Review workflow for stale priorities and life alignment.
- Bring-Your-Own-Key (BYOK) multi-provider LLM Thinking Partner integration
  (Ollama, OpenRouter, OpenAI, Anthropic, Gemini) with explicit consent and
  API key encryption at rest.
- Autumn-inspired accessible visual theme with system/dark/light modes.
- Export framework and decision assessments to GitHub Flavored Markdown.
- Local SQLite database storage and multi-platform UNC path normalization.
