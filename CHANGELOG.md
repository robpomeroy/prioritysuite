# Changelog

All notable changes to PrioritySuite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-11-26

### Added
- Predefined Life Framework Template Library (§11.2):
  - Gallery of 6 curated starter frameworks tailored to common seasons of life
    (Balanced Life, Career Transition, Independent Creator, Parenting & Family
    Stewardship, Academic Research & Deep Work, Civic Engagement & Community).
  - Users can preview and instantiate any template as an editable personal
    framework or exploratory sample.
- Interactive Relationship Map & Structural Alignment View (§11.2):
  - Canvas mapping Domains -> Whys -> Objectives -> Goals flow.
  - Structural diagnostics highlighting unanchored goals, unexpressed Whys, and
    cross-domain bridges.
- Historical Framework Snapshots & Version Comparison (§11.2):
  - Named point-in-time framework snapshots with reflection notes.
  - Side-by-side diff comparing historical snapshots against live frameworks.
  - Encrypted vault backup support preserving snapshot history.

### Changed
- Bumped application version to 0.5.0 across project metadata and configuration.

## [0.4.0] - 2026-11-24

### Added
- Automated Public Demonstration System (§8.3 & §11.2):
  - Added `DEMO_MODE` configuration and single-click "Explore Live Demo" entrypoint
    on login screen.
  - Implemented `manage.py reset_demo` management command for scheduled or automated
    periodic reset of visitor modifications.
  - Expanded starter framework library with sample Decision Assessments and simulated
    Thinking Partner LLM reflection logs.
  - Added curated starter templates: *Career & Vocation Transition* and
    *Independent Creator & Sustainable Pace*.
  - Enforced strict demo safety boundaries preventing demo account password modifications,
    profile updates, or account deletions.
- Password-Encrypted Vault Backup (§11.2):
  - Added cryptographic encrypted vault export and restore in user settings.
  - Password-derived key encryption using PBKDF2-HMAC-SHA256 (600,000 iterations)
    and Fernet AES-128-CBC cipher.
  - Portable offline framework and decision archives encrypted with user password.

### Changed
- Bumped application version to 0.4.0 across project metadata and configuration.

## [0.3.0] - 2026-11-24

### Added
- Self-service token-based password reset flow via email with Autumn-themed
  templates.
- Ability for staff and superusers to trigger password reset emails from
  User Administration.
- Autumn styling for Django Admin with Terracotta and Sage accents in light
  and dark modes.
- Superuser navigation shortcuts to the Django Admin portal from the navbar
  and User Administration view.
- Active navigation tab highlighting in the top-level navbar.
- Multi-framework switcher dropdown and clipboard copy status feedback in
  Markdown Export Preview.

### Changed
- Removed direct password setting by superusers and administrators to guarantee
  user privacy and prevent administrator account takeover.
- Theme button now displays initial theme name and icon on page load without
  flicker.
- Moved Theme Mode setting from LLM Thinking Partner to User Profile section.
- Separated Account Deletion into a dedicated danger section in settings.
- Form modal, delete confirmation, and export views use safe return links
  instead of `history.back()`.
- Periodic review status updates preserve active filter context and return to
  the review view.
- Overhauled dark mode contrast across all hardcoded light background utility
  classes.
- Bumped version to 0.3.0 across project metadata and configuration.

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
