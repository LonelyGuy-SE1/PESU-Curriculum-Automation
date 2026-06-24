# Curriculum Automation

## Phase 1 Flow Proposal

```mermaid id="phase1-flow"
flowchart TD

    A[Professor opens form] --> B[Enter course details]
    B --> C[Submit content, semester, credits, department, books]

    C --> D[FastAPI receives submission]
    D --> E[Check mandatory fields]

    E -->|Invalid| F[Reject submission]
    F --> G[Email professor with reasons]
    G --> H[Professor opens edit link]
    H --> I[Cached form shows old data and flagged issues]
    I --> C

    E -->|Valid| J[Generate derived fields]
    J --> J1[Course code]
    J --> J2[Credit pattern]
    J --> J3[Course type]
    J --> J4[Template data]

    J1 --> K[AI refinement]
    J2 --> K
    J3 --> K
    J4 --> K

    K --> K1[Refine content]
    K --> K2[Generate prelude]
    K --> K3[Generate objectives]
    K --> K4[Generate outcomes]
    K --> K5[Recommend tools]

    K1 --> L[Rubric check]
    K2 --> L
    K3 --> L
    K4 --> L
    K5 --> L

    L -->|Low score| M[Reject draft]
    M --> N[Store flagged issues]
    N --> G

    L -->|Pass| O[Create draft record]
    O --> P[Render preview with Jinja2]

    P --> Q[Faculty or admin review]

    Q -->|Rejected| R[Store rejection reasons]
    R --> G

    Q -->|Accepted| S[Update remote database]
    S --> T[Update curriculum template fields]
    T --> U[Keep incomplete template pending]

    U --> V{All course submissions received?}

    V -->|No| W[Wait for remaining professors]
    W --> U

    V -->|Yes| X[Compile final curriculum document]
    X --> Y[Final review]
    Y --> Z[Export final PDF or DOCX]
```

## Phase 1 Summary

Professors submit only the required academic material.

The system generates derived fields, refines the content, checks it using a rubric, and stores accepted drafts in a remote database.

Rejected submissions are returned by email with reasons. The professor gets an edit link where previous data is already cached and flagged issues are shown.

Accepted submissions do not immediately become the final document. They update the shared curriculum template and remain pending until all required course submissions are received.

The final curriculum document is compiled only after every required course entry is complete.
