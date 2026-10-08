# Rule sources

A rule may only cite a source once a team member has read it. The release test
(`RELEASE=1 uv run pytest`) fails while any emitted rule cites a source with `status: pending`.
Deadline: Fri Oct 9, 18:00 IST. A rule whose source isn't read by then is reworded as plain
guidance and keeps `basis: derived`.

Format: one block per source key. Keep the keys in sync with `rules.yaml`.

## cpcb_naqi_2014
- title: CPCB, National Air Quality Index (2014), health statements and breakpoints
- link: (fill in after reading)
- status: pending
- read_by:
- read_on:
- notes: Check the exact "Moderate" health statement wording. It may not mention children and older adults.

## caqm_grap
- title: CAQM, Graded Response Action Plan schedule (current revision)
- link: (fill in after reading)
- status: pending
- read_by:
- read_on:
- notes: Confirm stage thresholds (I 201–300, II 301–400, III 401–450, IV >450) and that GRAP is invoked on Delhi's average AQI. School measures changed in late 2024; quote only from the current schedule.

## exertion_guidance
- title: WHO or US EPA guidance on reducing physical exertion during high-pollution episodes
- link: (fill in after reading)
- status: pending
- read_by:
- read_on:
- notes: Supports the principle "the harder the activity, the earlier it is restricted".

## airday_policy
- title: AirDay design policy (our own choices, not an external source)
- link: PRD.md §7
- status: read
- read_by: team
- read_on: 2026-10-08
- notes: Used for unknown-data handling and window guidance. Always `basis: derived`.
