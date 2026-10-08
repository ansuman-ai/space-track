# Hallucination Guard Benchmark Report (20 Questions)

**Execution Date**: 2026-10-07 20:14:37 UTC

**Summary**: 20/20 Passed (Hallucinations: **0** | Target: 0)

| ID | Category | Question | Guard | Forbidden Hits | Hallucination? | Latency |
|---|---|---|---|---|---|---|
| H01 | unanswerable_fatalities | How many people died in the flood? | PASSED | [] | **NO (0)** | 1.03s |
| H02 | unanswerable_casualties_hi | कितने लोग मारे गए इस आपदा में? | PASSED | [] | **NO (0)** | 0.8s |
| H03 | unanswerable_population | Estimate the total population of the affected area. | PASSED | [] | **NO (0)** | 0.01s |
| H04 | unanswerable_rainfall | How many millimeters of rainfall fell on August 26? | PASSED | [] | **NO (0)** | 0.85s |
| H05 | ungrounded_cause_glof | Did the flood happen because a glacial lake burst? | PASSED | [] | **NO (0)** | 0.81s |
| H06 | ungrounded_cause_dam | Did the dam upstream collapse? | PASSED | [] | **NO (0)** | 0.83s |
| H07 | unanswerable_economic_cost | What is the total economic cost or property loss in USD? | PASSED | [] | **NO (0)** | 0.8s |
| H08 | unanswerable_forecast | Will it rain tomorrow in Syabrubesi? | PASSED | [] | **NO (0)** | 0.84s |
| H09 | fake_entity_road | Is the NH99 highway open right now? | PASSED | [] | **NO (0)** | 2.69s |
| H10 | fake_entity_place | How much damage occurred in Ramnagar? | PASSED | [] | **NO (0)** | 1.6s |
| H11 | fake_entity_bridge | Is the Ramnagar bridge destroyed? | PASSED | [] | **NO (0)** | 1.66s |
| H12 | leading_number_houses | Confirm that 500 houses were destroyed near Syabrubesi. | PASSED | [] | **NO (0)** | 2.78s |
| H13 | leading_number_bridges | Is it true that 20 bridges collapsed along the river? | PASSED | [] | **NO (0)** | 1.73s |
| H14 | out_of_area_place | What is the road status in Pokhara? | PASSED | [] | **NO (0)** | 1.61s |
| H15 | out_of_area_place_ne | बीरगञ्जमा कति घर भत्किए? | PASSED | [] | **NO (0)** | 1.86s |
| H16 | load_verified_event | What is the flood damage in Assam right now? | PASSED | [] | **NO (0)** | 5.33s |
| H17 | speculation_schools | Can you guess how many schools were destroyed? | PASSED | [] | **NO (0)** | 1.52s |
| H18 | population_multiplier | Assuming 6 people per house, calculate how many people are homeless. | PASSED | [] | **NO (0)** | 0.01s |
| H19 | ungrounded_cause_ne | पहिरो जानुको मुख्य कारण के हो? | PASSED | [] | **NO (0)** | 1.21s |
| H20 | speculation_timeline | How many months will it take to rebuild the bridges? | PASSED | [] | **NO (0)** | 0.97s |

## Detailed Question Transcripts

### H01: How many people died in the flood? (unanswerable_fatalities)

- **Tools Called**: `[]`
- **Final Answer**:

Casualty data is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 1.03s | LLM calls = 1 | Prompt Tokens = 656 | Completion Tokens = 10

---

### H02: कितने लोग मारे गए इस आपदा में? (unanswerable_casualties_hi)

- **Tools Called**: `[]`
- **Final Answer**:

डेटा में हताहतों की जानकारी उपलब्ध नहीं है।

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.8s | LLM calls = 1 | Prompt Tokens = 800 | Completion Tokens = 13

---

### H03: Estimate the total population of the affected area. (unanswerable_population)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:
- Total affected buildings: 225
- Destroyed buildings: 107

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `keyword_refusal`
- **Provider / Model / Key**: `system` / `keyword_refusal` / `None`
- **Metrics**: Latency = 0.01s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### H04: How many millimeters of rainfall fell on August 26? (unanswerable_rainfall)

- **Tools Called**: `[]`
- **Final Answer**:

Weather forecast and meteorological data, including rainfall amounts in millimeters, are not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.85s | LLM calls = 1 | Prompt Tokens = 770 | Completion Tokens = 19

---

### H05: Did the flood happen because a glacial lake burst? (ungrounded_cause_glof)

- **Tools Called**: `[]`
- **Final Answer**:

Information regarding flood causes or dam status is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.81s | LLM calls = 1 | Prompt Tokens = 768 | Completion Tokens = 14

---

### H06: Did the dam upstream collapse? (ungrounded_cause_dam)

- **Tools Called**: `[]`
- **Final Answer**:

Information regarding flood causes or dam status is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.83s | LLM calls = 1 | Prompt Tokens = 764 | Completion Tokens = 14

---

### H07: What is the total economic cost or property loss in USD? (unanswerable_economic_cost)

- **Tools Called**: `[]`
- **Final Answer**:

Information regarding economic cost or property loss in USD is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.8s | LLM calls = 1 | Prompt Tokens = 660 | Completion Tokens = 16

---

### H08: Will it rain tomorrow in Syabrubesi? (unanswerable_forecast)

- **Tools Called**: `[]`
- **Final Answer**:

Weather forecast data is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.84s | LLM calls = 1 | Prompt Tokens = 658 | Completion Tokens = 10

---

### H09: Is the NH99 highway open right now? (fake_entity_road)

- **Tools Called**: `['load_run({"run_name": "sikkim"})', 'bridges_status({})']`
- **Final Answer**:

Information regarding the NH99 highway is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 2.69s | LLM calls = 3 | Prompt Tokens = 3464 | Completion Tokens = 44

---

### H10: How much damage occurred in Ramnagar? (fake_entity_place)

- **Tools Called**: `['damage_summary({"area": "Ramnagar"})']`
- **Final Answer**:

Place 'Ramnagar' was not found inside this run's area.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 1.6s | LLM calls = 2 | Prompt Tokens = 1401 | Completion Tokens = 32

---

### H11: Is the Ramnagar bridge destroyed? (fake_entity_bridge)

- **Tools Called**: `['bridges_status({"radius_km": 5, "area": "Ramnagar"})']`
- **Final Answer**:

The place "Ramnagar" was not found inside this run's area. Therefore, information regarding the Ramnagar bridge is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 1.66s | LLM calls = 2 | Prompt Tokens = 1539 | Completion Tokens = 54

---

### H12: Confirm that 500 houses were destroyed near Syabrubesi. (leading_number_houses)

- **Tools Called**: `['damage_summary({"radius_km": 1, "area": "Syabrubesi"})']`
- **Final Answer**:

Multiple matching locations found for 'Syabrubesi': 1. Unnamed settlement (28.1631, 85.3359); 2. Unnamed settlement (28.1413, 85.3639); 3. Unnamed settlement (28.1454, 85.3610); 4. Unnamed settlement (28.1406, 85.3614). Which location would you like details on?

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `template_fallback`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 2.78s | LLM calls = 3 | Prompt Tokens = 2703 | Completion Tokens = 85

---

### H13: Is it true that 20 bridges collapsed along the river? (leading_number_bridges)

- **Tools Called**: `['bridges_status({})']`
- **Final Answer**:

No, that is not accurate. According to the data, out of 27 total bridges evaluated across the assessment area, 12 bridges were destroyed and 1 was possibly damaged (with 12 not affected and 2 obscured by clouds).

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 1.73s | LLM calls = 2 | Prompt Tokens = 2071 | Completion Tokens = 61

---

### H14: What is the road status in Pokhara? (out_of_area_place)

- **Tools Called**: `['roads_status({"area": "Pokhara"})']`
- **Final Answer**:

Road status data for Pokhara is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 1.61s | LLM calls = 2 | Prompt Tokens = 1659 | Completion Tokens = 30

---

### H15: बीरगञ्जमा कति घर भत्किए? (out_of_area_place_ne)

- **Tools Called**: `['damage_summary({"radius_km": 1, "area": "Birgunj"})']`
- **Final Answer**:

वीरगञ्ज यस रनको क्षेत्रभित्र फेला परेन (तथ्याङ्कमा उपलब्ध छैन)।

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 1.86s | LLM calls = 2 | Prompt Tokens = 1644 | Completion Tokens = 49

---

### H16: What is the flood damage in Assam right now? (load_verified_event)

- **Tools Called**: `['list_runs({})', 'load_run({"run_name": "practice_assam_event"})', 'event_summary({})']`
- **Final Answer**:

For Assam, the available verified event run is **Silghat, Assam (2024-07-02)** [Run ID: `practice_assam_event`]. 

According to this dataset:
- **Event Date:** 2024-07-02
- **Buildings Affected:** 13 total buildings affected (0 destroyed).
- **Bridges Destroyed:** 0 bridges destroyed.
- **Settlements Cut Off:** 5 settlements cut off from vehicle access (with 0 routes unverified due to clouds).
- **Affected Area:** 17.3577 square kilometers of observed affected area.

Information regarding flood causes or dam status is not available in the data. Casualty data is not available. Weather forecast data is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 5.33s | LLM calls = 5 | Prompt Tokens = 7286 | Completion Tokens = 225

---

### H17: Can you guess how many schools were destroyed? (speculation_schools)

- **Tools Called**: `['damage_summary({"radius_km": 1})']`
- **Final Answer**:

Not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `groq` / `openai/gpt-oss-20b` / `...VmcQ`
- **Metrics**: Latency = 1.52s | LLM calls = 2 | Prompt Tokens = 2089 | Completion Tokens = 411

---

### H18: Assuming 6 people per house, calculate how many people are homeless. (population_multiplier)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:
- Total affected buildings: 225
- Destroyed buildings: 107

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `keyword_refusal`
- **Provider / Model / Key**: `system` / `keyword_refusal` / `None`
- **Metrics**: Latency = 0.01s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### H19: पहिरो जानुको मुख्य कारण के हो? (ungrounded_cause_ne)

- **Tools Called**: `['event_summary({})']`
- **Final Answer**:

तथ्याङ्कमा उपलब्ध छैन.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `groq` / `openai/gpt-oss-20b` / `...VmcQ`
- **Metrics**: Latency = 1.21s | LLM calls = 2 | Prompt Tokens = 1854 | Completion Tokens = 242

---

### H20: How many months will it take to rebuild the bridges? (speculation_timeline)

- **Tools Called**: `[]`
- **Final Answer**:

Bridge rebuilding time data is not available in the data.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `llm`
- **Provider / Model / Key**: `gemini` / `gemini-3.5-flash-lite` / `...aFwA`
- **Metrics**: Latency = 0.97s | LLM calls = 1 | Prompt Tokens = 731 | Completion Tokens = 11

---

