# PRD — Learning Materials CMS

**Feature:** Content Management for Learning Materials
**Product:** GRM Web App (Benin)
**Status:** Draft
**Author:** Product
**Last updated:** 2026-06-23

---

## 1. Summary

Add a lightweight content management system (CMS) to the GRM platform that lets
authorized administrators create, organize, translate, publish, and update
**learning materials** (guides, tutorials, FAQs, videos, downloadable
documents) targeted at three audiences: **facilitators**, **citizens**, and
**village secretaries**.

Today, training and onboarding content is distributed out-of-band (printed
handouts, files shared by email, in-person sessions). This makes content
inconsistent, hard to keep current, and impossible to track. This feature brings
that content into the platform itself, where each role sees the materials
relevant to them, in their language, always up to date.

---

## 2. Background & Problem

The GRM platform serves a grievance-redress workflow across communes in Benin.
The system already distinguishes between roles — **facilitators** (ADLs),
**citizens**, **village secretaries**, and government workers — and is
multilingual (French and local languages via Django i18n).

Problems with the current state:

- **No single source of truth.** How to register a grievance, how to triage a
  task, or how to follow up is documented inconsistently across channels.
- **Stale content.** When a process changes, there is no reliable way to push
  the update to everyone, and no way to know who is still using old guidance.
- **No role targeting.** A citizen does not need the facilitator triage manual;
  a village secretary needs procedures specific to their commune-level duties.
- **Language gaps.** Materials are not consistently available in the languages
  users actually read.
- **No editorial control.** Non-technical program staff cannot publish or fix
  content without engineering involvement.

---

## 3. Goals & Non-Goals

### Goals

- Allow non-technical administrators to author and edit learning materials
  through a web UI, without code deploys.
- Target each material to one or more roles (facilitator, citizen, village
  secretary).
- Support multilingual content (at minimum French + the locales the platform
  already supports) with per-language publish state.
- Support a draft → published lifecycle.
- Let end users browse, search, and read materials relevant to their role and
  language inside the existing app.
- Support attachments/downloads (PDF, images) and embedded video links.

### Non-Goals

- Not building a general-purpose website CMS — scope is learning materials only.
- Not building authoring of interactive quizzes or graded courses (LMS features)
  in v1.
- Not replacing the existing grievance/task workflow content.
- No automated machine translation in v1 (translations are entered manually).
- No offline/mobile-app packaging in v1 (web responsive only).

---

## 4. Target Users & Personas

| Persona | Relationship to feature | Primary need |
| --- | --- | --- |
| **Content Administrator** (program/M&E staff) | Author/editor | Create, update, and publish materials without engineering |
| **Facilitator (ADL)** | Reader | Operational guides: registering, triaging, escalating grievances |
| **Citizen** | Reader | Plain-language guides: how to file a complaint, what to expect, rights |
| **Village Secretary** | Reader | Commune-level procedures, reporting duties, escalation paths |

---

## 5. User Stories

**Administrators**
- As an administrator, I can create a new material with a title, body, category,
  target role(s), and language so the right people can find it.
- As an administrator, I can save a draft and come back later before publishing.
- As an administrator, I can attach a PDF or image and embed a video link.
- As an administrator, I can add a translation of an existing material in
  another language and publish each language independently.
- As an administrator, I can edit a published material and the change is
  reflected immediately.
- As an administrator, I can unpublish or archive a material that is no longer
  relevant.

**End users (facilitator / citizen / village secretary)**
- As a user, I see a "Learning" / "Help" section with only the materials for my
  role, in my language.
- As a user, I can browse by category and search by keyword.
- As a user, I can open a material and download its attachments.

---

## 6. Functional Requirements

### 6.1 Content model

Each **Material** has:

- `title` (per language)
- `slug` (stable identifier, language-independent)
- `body` (rich text / Markdown, per language)
- `summary` (short description for list views, per language)
- `category` (e.g. Getting Started, Filing a Grievance, Triage, Reporting)
- `target_roles` — one or more of: `facilitator`, `citizen`,
  `village_secretary` (extensible to other roles)
- `attachments` — files (PDF, image) and external video URLs
- `language` set with per-language publish state
- `status` — `draft` | `published` | `archived`
- `published_at`, `created_by`, `updated_by`, timestamps
- `order` / pinning for manual sort within a category

### 6.2 Authoring

- WYSIWYG or Markdown editor with headings, lists, links, images.
- Create, edit, duplicate, delete (soft-delete/archive).
- Per-language tabs so one material holds all its translations.
- Preview as a given role + language before publishing.

### 6.3 Lifecycle

- Draft → Published → Archived.
- Editing a published material updates it in place; the change is reflected
  immediately.
- Publish/unpublish per language (e.g. French published, Fon still draft).

### 6.4 Delivery to end users

- A "Learning Materials" section accessible from the main navigation.
- Filtered automatically by the signed-in user's role and active locale.
- Browse by category, full-text search by title/summary/body.
- Material detail page with body, attachments, and video embeds.
- Graceful fallback: if a material is not translated in the user's locale, show
  the default-language version with a "not available in your language" notice
  (configurable).

### 6.5 Permissions

- Only users with a `content_admin` permission can access authoring; reuse the
  existing role/permission framework.
- End users have read-only access scoped to their role.

---

## 7. Non-Functional Requirements

- **Localization:** Integrate with the existing Django i18n stack; UI chrome
  remains translatable; material content is data, stored per language.
- **Performance:** List and detail pages should load comparably to existing
  dashboard pages; search responsive on the expected content volume
  (hundreds of materials, not millions).
- **Accessibility:** Readable on low-bandwidth connections and mobile browsers;
  attachments should note file size.
- **Auditability:** All publish/edit/archive actions logged with user and
  timestamp (reuse existing logging where possible).
- **Security:** Uploaded files validated by type/size; authoring restricted by
  permission; published content sanitized to prevent stored XSS.
- **Data store:** Relational Django models (the platform's primary database).
  CouchDB is **not** used for this feature.

---

## 8. Proposed Approach (high level)

- Introduce a `learning` (or `content`) Django app exposing authoring views in
  the dashboard and read views for end users.
- Store materials as relational Django models (a `Material` model plus a
  per-language `MaterialTranslation` table). CouchDB is not used for this
  feature.
- Reuse the existing `attachments` app for file upload/storage.
- Reuse the existing authentication/role model to derive `target_roles`
  filtering and authoring permissions.
- Reuse Django i18n for UI and store content translations as data.

---

## 9. Success Metrics

- **Adoption (authoring):** ≥ 80% of learning content lives in the CMS within
  one quarter of launch (vs. out-of-band distribution).
- **Freshness:** Median time from a process change to updated published material
  drops to under 1 week.
- **Engagement:** % of facilitators / village secretaries who open ≥ 1 material
  per month; trend of searches and views per role.
- **Coverage:** % of materials available in each supported language.
- **Self-service:** Number of content updates published with zero engineering
  involvement.

---

## 10. Rollout Plan

1. **Phase 1 (MVP):** Content model, authoring CRUD, draft/published states,
   role targeting, single-language, end-user browse/read.
2. **Phase 2:** Multilingual translations + per-language publish, attachments,
   video embeds, search.
3. **Phase 3:** Analytics on views/searches.

---

## 11. Open Questions

- **Languages:** Exact set of supported locales for content beyond French?
- **Roles:** Do we need finer targeting than the three roles (e.g. by commune or
  administrative level)?
- **Notifications:** Should users be notified (in-app / SMS / email) when new or
  updated materials are published for their role?
- **Editor:** Markdown vs. full WYSIWYG given the authoring audience's technical
  comfort?

---

## 12. Dependencies

- Existing authentication / role framework (facilitator, citizen,
  village_secretary).
- Existing `attachments` app for file handling.
- Django i18n / locale infrastructure.
- Existing dashboard navigation and permission mixins.
