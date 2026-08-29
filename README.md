# NEUROSCOPE

NEUROSCOPE is a student-led research project exploring whether patterns across different kinds of decisions can be studied as one continuous behavioral sequence.

The repository currently contains the participant-facing data collection system and its research protocol. It does not contain a trained model, produce clinical conclusions, or assign personality and ability scores.

## Research direction

Most behavioral tasks examine one kind of choice in isolation. NEUROSCOPE instead records how the same participant learns from feedback, responds to uncertainty, weighs time, discovers patterns, and makes social decisions during one session.

The project asks whether those responses share enough structure to support a general representation of decision-making. Each trial is recorded in a consistent form containing the situation, action, outcome, and response time, while task-specific context remains available for later analysis.

## Current status

The current milestone is the data collection protocol. It provides:

- Five connected decision activities totaling 240 trials in the full protocol.
- Anonymous participant sessions that do not collect names or direct identifiers.
- Immediate, retryable trial logging with protection against duplicate records.
- A short participant summary at the end that avoids diagnostic or personality claims.
- A demo mode for development and a full mode for research sessions.

Representation learning and held-out evaluation are later stages. Until those exist, the project should be treated as an experimental data collection system rather than evidence of a validated behavioral model.

## Research boundaries

Participation is voluntary, and the website collects age bracket and education level alongside task responses. Participants aged 13–17 must confirm guardian consent. The browser cannot read stored research records, and researchers access them separately through protected database credentials.

The protocol has practical limitations: activity order is fixed, browser storage supports resume only on the same device and profile, and the programmed social partner is not a human participant.

## Repository

The complete application lives in [`web`](web). Its [website README](web/README.md) covers the participant flow, technical architecture, local setup, database schema, testing, and deployment.

Detailed activity notes are available in [`web/docs/questions.md`](web/docs/questions.md).
