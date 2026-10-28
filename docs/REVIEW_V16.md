# v1.6 product review

Three independent reviewer contexts inspected the implemented product: HTML/accessibility/security, product design, and simulated student journeys across computer science, finance, mechanical engineering, law and life sciences. Reports were frozen before the second implementation pass.

| Observed problem | Implemented change | Regression |
| --- | --- | --- |
| Domain IDs disappeared between parsing and ranking | Preserve IDs; support historical profiles | `matching_resume_v16.mjs` |
| Keyword substrings crossed Chinese words or English tokens | Token boundaries and explicit role-function evidence | `matching_adversarial_v16.mjs` |
| A 2028 internship carried an old 2027 label | Title-cohort precedence and conflict handling | `matching_adversarial_v16.mjs` |
| Packaging ranked as backend development; production work as R&D | Role anchors, domain hierarchy and career-level checks | `matching_adversarial_v16.mjs` |
| Homepages and event notices received job scores | Position classification and separate lead handling | `matching_adversarial_v16.mjs` |
| Concurrent registration overwrote an account | Web Locks, write-time checks and cross-tab conflict detection | Concurrent synthetic browser review |
| Search blur replaced results before a click completed | Search uses input events | `frontend_accessibility_v16.mjs` |
| Hidden dialogs remained focusable; drawers left backgrounds active | Dialog semantics, inert background and focus restoration | `frontend_accessibility_v16.mjs` |
| Uploads and review selection required a pointer | Keyboard file actions and native buttons | `frontend_accessibility_v16.mjs` |
| Asset links accepted unsafe schemes | HTTP/HTTPS validation at input and rendering | `frontend_accessibility_v16.mjs` |
| Parsing immediately saved uncertain results | Editable preview and explicit confirmation | `matching_resume_browser_v16.mjs` |
| Raw timestamps and address fragments appeared in filters | Date normalization and canonical city choices | `workspace_v15.mjs` |
| Analysis panels pushed jobs below the fold | Compact profile summary; inspector details; folded mobile filters | Visual review |
| Failed collectors appeared healthy when cache remained | Separate collection health from preserved data | `test_source_integrity_v16.py` |
| Portal cohorts labelled unrelated positions | Job-level cohort evidence for portal results | `test_source_integrity_v16.py` |

Visual checks cover 360, 390, 768, 1024, 1280 and 1440 CSS pixels, plus light and dark appearances. Brand assets and the English font are served locally. Browser tests generate their documents and account records in isolated contexts.

Source coverage remains measured in the living audit report: official portals, observed positions, inaccessible sources and unknown cohorts are counted separately. Existing scheduled collectors and the daily industry-source audit continue refreshing the catalog.
