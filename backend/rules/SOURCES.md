# Rule sources

A rule may only cite a source once it has been read. The release test
(`RELEASE=1 uv run pytest`) fails while any emitted rule cites a source with `status: pending`.

Format: one block per source key. Keep the keys in sync with `rules.yaml`.

## cpcb_naqi_2014
- title: CPCB, National Air Quality Index report (CUPS/82/2014-15), Table 3.12 "Health Statements for AQI Categories"
- link: https://cpcb.gov.in/displaypdf.php?id=bmF0aW9uYWwtYWlyLXF1YWxpdHktaW5kZXgvRklOQUwtUkVQT1JUX0FRSV8ucGRm (page 36)
- also: "About National Air Quality Index" (breakpoints), https://cpcb.gov.in/displaypdf.php?id=bmF0aW9uYWwtYWlyLXF1YWxpdHktaW5kZXgvQWJvdXRfQVFJLnBkZg==
- status: read
- read_by: AirDay team
- read_on: 2026-10-09
- quoted:
  - Good (0–50): "Minimal Impact"
  - Satisfactory (51–100): "May cause minor breathing discomfort to sensitive people"
  - Moderate (101–200): "May cause breathing discomfort to the people with lung disease such as asthma and discomfort to people with heart disease, children and older adults"
  - Poor (201–300): "May cause breathing discomfort to people on prolonged exposure and discomfort to people with heart disease with short exposure"
  - Very Poor (301–400): "May cause respiratory illness to the people on prolonged exposure. Effect may be more pronounced in people with lung and heart diseases"
  - Severe (401–500): "May cause respiratory effects even on healthy people and serious health impacts on people with lung/heart diseases. The health impacts may be experienced even during light physical activity"
- breakpoints (PM2.5 / PM10, µg/m³, 24-hour averages): Good 0–30 / 0–50, Satisfactory 31–60 / 51–100,
  Moderately Polluted 61–90 / 101–250, Poor 91–120 / 251–350, Very Poor 121–250 / 351–430, Severe 250+ / 430+.
  These match `rules.yaml`. CPCB defines them on 24-hour averages; AirDay applies them to hourly values as its own
  cautious choice (ADR 0003).
- notes: The Moderate statement does mention "children and older adults", so the earlier doubt in the PRD was wrong.
  CPCB's own Moderate category name is "Moderately Polluted".

## exertion_guidance
- title: US EPA / AirNow, "Air Quality and Outdoor Activity Guidance for Schools", EPA-456/F-14-003, August 2014
- link: https://document.airnow.gov/air-quality-and-outdoor-guidance-for-schools.pdf
- status: read
- read_by: AirDay team
- read_on: 2026-10-09
- quoted:
  - "Students breathe harder when they are active for a longer period of time or when they do more intense activities. More pollution enters the lungs when a person is breathing harder."
  - It helps to "reduce the intensity of activities so students are not breathing so hard (e.g., walk instead of run)".
  - Unhealthy for Sensitive Groups: "Consider moving longer or more intense activities indoors or rescheduling them to another day or time."
  - Unhealthy: "For all outdoor activities, take more breaks and do less intense activities."
  - Very Unhealthy: "Move all activities indoors or reschedule them to another day."
  - Particle pollution indoors: "If the building has a forced air heating or cooling system that filters out particles then the amount of particle pollution should be lower indoors".
- notes: Supports the principle "the harder the activity, the earlier it is restricted" (PE, then recess, then
  assembly). The EPA guide uses the US AQI, whose scale differs from India's; AirDay uses it for the principle, not
  for thresholds. Thresholds come from CPCB. The indoor-air quote is why the PRD says moving indoors reduces exertion
  but does not make indoor air clean.

## caqm_grap
- title: CAQM, Graded Response Action Plan schedule (current revision)
- link: https://caqm.nic.in (GRAP orders)
- status: pending
- read_by:
- read_on:
- notes: Not yet read from a primary source. Used only for the indicative GRAP badge (stage thresholds I 201–300,
  II 301–400, III 401–450, IV >450), which is display-only and labelled "not a CAQM order". No emitted rule cites it.
  School measures changed in late 2024; R-SV-NOTE deliberately names none of them.

## airday_policy
- title: AirDay design policy (our own choices, not an external source)
- link: PRD.md §7
- status: read
- read_by: AirDay team
- read_on: 2026-10-08
- notes: Used for unknown-data handling and window guidance. Always `basis: derived`.
