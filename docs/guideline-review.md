# Published-guidance review, 18 November 2026

This is a source-based engineering review of the three camera exercises and
progression behavior. It is not an independent clinician sign-off on the app
or an audit of every imported catalog exercise. No outside person is claimed
to have reviewed this work.

| Source and scope | Finding applied to LIMBER | Concrete change |
| --- | --- | --- |
| [NHS strength exercises](https://www.nhs.uk/live-well/exercise/strength-exercises/), general home exercise | Controlled movement and comfortable range; wall press-up is a described exercise | Replaced imported instructions to reverse a squat quickly at full depth with slow, comfortable movement. Added wall press-up with controlled-return instructions. |
| [Leeds Teaching Hospitals: knee exercises](https://www.leedsth.nhs.uk/patients/resources/knee-exercises/), knee rehabilitation | Describes knee extension in sitting, then bending the knee again | Added a seated knee-extension catalog entry and an extension/return camera protocol. A stable chair and the same visible side are requested. |
| [NHS sitting exercises](https://www.nhs.uk/live-well/exercise/sitting-exercises/), general mobility | Stable seating and gradual progression; suitability may need a health professional's advice | Included stable-chair setup and comfortable-range instructions. Counting does not tell the person to force a target angle. |
| [NICE NG226, 1.3.1–1.3.4](https://www.nice.org.uk/guidance/ng226/chapter/Recommendations), diagnosed osteoarthritis | Exercise should be tailored, and supervised exercise may be appropriate | Retained eligibility/referral checks; camera counts cannot override them. No claim that NICE establishes self-guided suitability for undiagnosed minor pain. Added conservative evidence requirements before the existing increase rule can fire. |

The two-week window, pain ceiling, tracking coverage, angle bands and tolerated
range change are explicit student-project policies in `thresholds.yaml` and
`movementTracker.ts`. These sources do not validate those exact numerical
values. The camera observes a 2D angle span; it does not establish clinical range
of motion, technique quality, diagnosis or treatment effectiveness.

The reproducible catalog curation lives in `catalog_overrides.yaml`, including
the added exercises. Re-importing the upstream dataset retains these changes.
The remaining catalog has not received this same exercise-by-exercise review.
A clinician can use this matrix to record further changes and their rationale.

## Planner verdict

Use the deterministic planner for final delivery. The live plan route no longer
obtains an AI client, even if API keys exist in the environment. Existing AI
adapter/validation tests remain for reproducibility; a valid JSON response does
not demonstrate better plans or outcomes. No head-to-head superiority result
is claimed. Reconsider only after a prespecified comparison and outside review.

## Position and naming

Proposed value sentence: **LIMBER offers a self-guided student prototype for
minor-pain recovery with explicit referral reasons, local camera processing,
and visible measured progress, without requiring employer enrollment.**
This describes the implemented workflow; it does not establish clinical
superiority, real-world effectiveness, affordability at scale, or a replacement
for clinician-led care.

[Limber Health](https://www.limberhealth.com/for-providers/home-exercise-program)
already offers a home-exercise product with the same name. Treat LIMBER as a
course-project name pending the team's naming decision; no trademark clearance
or affiliation is implied. A public release name still needs review.
