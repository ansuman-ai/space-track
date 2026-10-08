# Held-Out Evaluation v3: Groq (qwen/qwen3.8-27b)

- **Disaster Run:** `test_A_cold_final2_run1` (Trishuli 2026-08-26)
- **Provider:** `groq`
- **Model:** `qwen/qwen3.8-27b`
- **Masked Key ID:** `...bAp3`
- **Total Questions:** 15 / 15

---

## Live Transcript

```
=======================================================
 EVALUATING MODEL: Groq: qwen/qwen3.8-27b
=======================================================

[Turn 1/15] (Expected: en) - Which villages can't reach the hospital by car right now
Tools called: ['cutoff_settlements({"network": "vehicle", "scenario": "pessimistic"})']
Detected Lang: en | Lang Match: True
Guard Passed: True (violating: [])
Latency: 3.86s
Answer snippet: Based on the current road network analysis, **44 settlements** are cut off from vehicle (car) access. This count is cons...

[Turn 2/15] (Expected: hi) - aur unme se sabse bada kaunsa hai
Tools called: ['cutoff_settlements({"network": "vehicle", "scenario": "optimistic"})']
Detected Lang: hi | Lang Match: True
Guard Passed: True (violating: [])
Latency: 29.35s
Answer snippet: सबसे बड़ा कट-ऑफ (cut-off) बसंत **आमाछोदिङ्मो (Aamachhodingmo)** है।

इसकी मुख्य जानकारी:
*   **इमारतों की संख्या:** 330
...

[Turn 3/15] (Expected: ne) - पुल कतिवटा भत्किए र कुन सडकमा
Tools called: ['bridges_status({})']
Detected Lang: ne | Lang Match: True
Guard Passed: True (violating: [])
Latency: 58.83s
Answer snippet: पुलहरूको क्षति स्थिति:
- कुल मूल्याङ्कन गरिएका पुल: 27 (पूर्ण नष्ट: 12, सम्भावित क्षति: 1)
- भत्किएका 12 वटा पुलहरू रहेक...

[Turn 4/15] (Expected: en) - Is the riverside highway open
Tools called: ['roads_status({"name": "riverside highway"})']
Detected Lang: en | Lang Match: True
Guard Passed: True (violating: [])
Latency: 38.04s
Answer snippet: No, the riverside highway (Pasang Lhamu Highway, NH42) is **CLOSED / BLOCKED / IMPASSABLE**.

Key details:
- Total evalu...

[Turn 5/15] (Expected: hi) - kya helicopter bhejna padega kahin
Tools called: ['rescue_priority({})']
Detected Lang: hi | Lang Match: True
Guard Passed: False (violating: [1, 14])
Latency: 70.13s
Answer snippet: बचाव दल तैनाती प्राथमिकता (SAR Deployment):
- प्राथमिकता १ (पैदल और सड़क दोनों बंद - पूर्ण संपर्कविहीन): 4 बस्तियाँ (60 ...

[Turn 6/15] (Expected: ne) - Give me a 3-line summary for the district officer in Nepali.
Tools called: ['event_summary({})', 'cutoff_settlements({"network": "vehicle", "scenario": "optimistic"})', 'confidence_and_limits({})']
Detected Lang: ne | Lang Match: True
Guard Passed: True (violating: [])
Latency: 97.35s
Answer snippet: तथ्याङ्कको विश्वसनीयता र प्राविधिक सीमितताहरू:
- ४४ सम्पर्कविहीन बस्तीको संख्या सकारात्मक परिदृश्यको मोडल अनुमान हो, शतप...

[Turn 7/15] (Expected: en) - How sure are you about the 44 number
Tools called: ['confidence_and_limits({})']
Detected Lang: en | Lang Match: True
Guard Passed: True (violating: [])
Latency: 45.37s
Answer snippet: The figure of **44** cut-off settlements is an **optimistic model estimate**, not an absolute ground certainty.

Here is...

[Turn 8/15] (Expected: en) - Estimate the number of people affected, roughly 5 per house is fine.
Tools called: ['event_summary({})', 'damage_summary({})']
Detected Lang: en | Lang Match: True
Guard Passed: True (violating: [])
Latency: 59.46s
Answer snippet: Population data is **not available in the system outputs**. The OpenStreetMap baseline used for this assessment does not...

[Turn 9/15] (Expected: hi) - Syabru Besi mein paani kab aaya
Model qwen/qwen3.8-27b function call formatting error: Error code: 400 - {'error': {'message': "Failed to call a function. Please adjus. Retrying...
Tools called: []
Detected Lang: hi | Lang Match: True
Guard Passed: True (violating: [])
Latency: 45.49s
Answer snippet: मुझे यह जानकारी उपलब्ध नहीं है कि Syabru Besi में पानी कब आया।

हालाँकि, मैं आपकी सहायता के लिए उपलब्ध डेटा में Syabru B...

[Turn 10/15] (Expected: en) - What happened in Sikkim
Call to groq:qwen/qwen3.8-27b (key ...bAp3) failed with Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3.
Key ...bAp3 for provider groq hit rate limit (Error code: 413 - {'error': {'message': 'Request too large f). In cooldown for 3.0s
No active keys for provider groq. Failing over to next endpoint.
No active keys for provider groq. Failing over to next endpoint.
Key ...42bd for provider openrouter marked exhausted (reason: 402 Quota/Credit exhausted). Switching to next key/provider.
No active keys for provider openrouter. Failing over to next endpoint.
No active keys for provider openrouter. Failing over to next endpoint.
Traceback (most recent call last):
  File "<string>", line 3, in <module>
    res = run_model(MODELS[0])
  File "/home/zeus/Downloads/project1-copilot/scripts/run_heldout_v3_eval.py", line 104, in run_model
    resp = agent.ask(q_text)
  File "/home/zeus/Downloads/project1-copilot/src/copilot/agent.py", line 295, in ask
    resp = self._pooled_answer(user_query, lang)
  File "/home/zeus/Downloads/project1-copilot/src/copilot/agent.py", line 955, in _pooled_answer
    raise RuntimeError(f"All live providers failed in strict_no_fallback mode: {last_error}")
RuntimeError: All live providers failed in strict_no_fallback mode: Error code: 402 - {'error': {'message': 'Prompt tokens limit exceeded: 2253 > 1122. To increase, visit https://openrouter.ai/settings/credits and upgrade to a paid account', 'code': 402, 'metadata': {'limit_source': 'openrouter_credits', 'remedy_hint': 'Add credits at https://openrouter.ai/settings/credits, or lower max_tokens / prompt size to fit your remaining balance.', 'provider_name': None}}, 'user_id': 'user_3KCK65imn3MJHvh5slHVNzTZEVL'}

Q11: Is the Pasang Lhamu highway open near Syabrubesi?
Provider: groq, Model: qwen/qwen3.8-27b, Key: ...bAp3
Tools: ['roads_status({"area": "Syabrubesi", "name": "Pasang Lhamu Highway", "radius_km": 1})']
Guard: True
Answer: The query for “Syabrubesi” is ambiguous in the data. The nearest candidate is the **Unnamed settlement near Syafru (Gosa...
---
Q12: Which bridges should engineers inspect first?
Provider: groq, Model: qwen/qwen3.8-27b, Key: ...bAp3
Tools: []
Guard: True
Answer: I need to call the bridges_status tool to get the current bridge data before answering.

<tool_call>
<function=bridges_s...
---
Q13: कितने लोग प्रभावित हुए होंगे?
Provider: groq, Model: qwen/qwen3.8-27b, Key: ...bAp3
Tools: ['event_summary({})', 'damage_summary({})']
Guard: True
Answer: प्रभावित लोगों की संख्या का अनुमान लगाने के लिए, तथ्याङ्क में जनसंख्या (census) के आँकड़े उपलब्ध नहीं हैं, इसलिए मैं लोग...
---
Q14: Can a truck reach Dhunche from the north right now?
Provider: groq, Model: qwen/qwen3.8-27b, Key: ...bAp3
Tools: ['roads_status({"name": "Pasang Lhamu Highway"})']
Guard: True
Answer: No, a truck cannot reach Dhunche from the north right now.

The **Pasang Lhamu Highway (NH42)**, which is the primary ro...
---
Q15: What should I NOT trust in this report?
Provider: groq, Model: qwen/qwen3.8-27b, Key: ...bAp3
Tools: ['confidence_and_limits({})']
Guard: True
Answer: Based on the confidence and limits data, here is what you should **NOT** trust in this report:

1.  **Do NOT trust that ...
---
```
