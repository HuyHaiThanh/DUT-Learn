# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Students (primary):** IT undergraduates at the Faculty of Information Technology, University of Science and Technology – The University of Danang. They self-study a course's official materials (pilot: *Kỹ thuật lập trình*, C/C++-heavy) mostly on a **laptop**, reading a long PDF textbook and asking questions while they read. Phones must work but are secondary.
- **Lecturers:** upload, version, publish and revoke course materials; organise lessons; later review AI-proposed practice items and decide official grades.
- **Administrators:** manage accounts, courses, class sections and enrolment. They do not read class content by default.

## Product Purpose

DUTLearn is a course-scoped learning platform with an AI teaching assistant (trợ giảng) that answers only from the class's published materials, cites the exact page and passage, and says so when the materials do not contain enough evidence. Success: a student can read, ask, and verify an answer against the source without leaving their place in the text; a lecturer controls exactly what the assistant can draw on.

## Positioning

Not a general chatbot and not a file-dump LMS: the assistant's knowledge is bounded by what the lecturer published for that class, permission is enforced on the server, and every claim is traceable to a page the student can open.

## Operating Context

- Graduation thesis product (individual), evaluated by an advisor and a defence committee; demos run on a projector and via remote access to a desktop with a local GPU (Ollama, Qwen2.5-7B-Instruct). Answers take several seconds; no streaming.
- Materials are text PDFs with a text layer; the reader shows the PDF page plus an extracted-text view where cited passages are highlighted.
- Interface language is Vietnamese; code and commits are English.

## Capabilities and Constraints

- Roles: admin, lecturer, student; class membership decides access. Closed classes are unreadable by students.
- Materials have versions with states: uploaded, processing, ready, failed, published, superseded, revoked. One published version per material.
- Tutor modes: direct answer and step-by-step hints. Sessions per class with history; reading position is remembered.
- Stack: React + TypeScript + Vite + Tailwind + shadcn/ui; FastAPI backend.
- Out of scope: video, scanned-document OCR, automatic code grading, native mobile app, single sign-on with the university.
- Planned but not yet built: practice items, assignments/submissions/feedback, activity-based progress tracking (must not infer competence from visit counts).

## Brand Commitments

- Name **DUTLearn**, mark is a blue rounded square with the letter "D". Brand blue `#0B5CAD` stays.
- Must not feel like the old university LMS (dense tables, Moodle-like boxes) — confirmed by the user 17/11/2026.
- Pilot/disclaimer copy: "Phiên bản thử nghiệm, chưa phải hệ thống chính thức của trường."
- The product is not affiliated with any third-party learning platform and must not reference one.

## Evidence on Hand

- Pilot corpus: VOER "Giáo trình Lập trình căn bản" (CC BY 3.0), 201 pages.
- Seed accounts and classes (KTLT-01, KTLT-02, KTLT-CLOSED) for development only.
- No user-testing results, usage numbers or testimonials exist yet; never invent them.

## Product Principles

1. **The material leads, the assistant serves.** Reading is the primary activity; the tutor sits beside the text, never on top of it.
2. **Every answer is checkable in one step.** Citations open the exact page and passage while keeping the conversation in place.
3. **Honest about limits.** Missing evidence, a busy model, or revoked material is stated plainly with the next step.
4. **Lecturer is in control.** Nothing reaches students or the assistant until a lecturer publishes it, and the UI makes that state unmistakable.
5. **Calm, academic, current.** Serious enough for a defence committee, lighter than a legacy LMS.

## Accessibility & Inclusion

- Keyboard reachable controls with visible focus; status never conveyed by colour alone; Vietnamese labels on every control.
- Must remain legible on a classroom projector (contrast, minimum text sizes).
- Phone width 360 px must work without horizontal scrolling.
