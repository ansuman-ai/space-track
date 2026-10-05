"""Situation-Report Copilot Agent.

Provider-agnostic LLM conversational agent supporting:
- Gemini (via google-genai / google.generativeai)
- OpenAI (via openai)
- Anthropic (via anthropic)
- Robust Offline Fallback engine

Enforces:
- Tool calling
- Multi-turn conversation context
- Strict NumberGuard verification with single retry + template fallback
- Language matching (English, Nepali, Hindi, romanised)
- Clarification for ambiguous place queries
- "Not available in the data" response for ungrounded queries
- Explicit mention of uncertainty (cloud-unverified routes, inferred areas)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .facts import FactStore
from .guard import NumberGuard
from .names import PlaceNameResolver
from .tools import CopilotTools, get_tool_definitions

logger = logging.getLogger("copilot.agent")

SYSTEM_PROMPT = """You are the Emergency Situation-Report Copilot for disaster search and rescue operations in Nepal.
Your duty is to provide accurate, strictly grounded answers to rescuers based on satellite and GIS pipeline outputs.

CRITICAL OPERATIONAL RULES:
1. TOOL CALLING REQUIRED: You MUST call one or more tools to retrieve real facts before answering any factual question.
2. ZERO NUMBER HALLUCINATION: Every single number in your answer must come directly from tool outputs. Never invent or estimate counts, percentages, distances, or dates.
3. DATA GAPS: If an entity, metric, or figure is not present in the data (e.g. casualties, population, weather forecasts, private individuals), explicitly state "not available in the data" (in Nepali: "तथ्याङ्कमा उपलब्ध छैन", in Hindi: "डेटा में उपलब्ध नहीं है").
4. LANGUAGE MATCHING: Always answer in the exact language the user queried in (English, Nepali, Hindi, or romanised). Use Devanagari script for Nepali and Hindi.
5. UNCERTAINTY DISCLOSURE: Explicitly highlight data uncertainties:
   - Cloud-covered roads and settlements are "unverified" (passability cannot be confirmed optically).
   - Tributary hazard zones are "hydraulically inferred" rather than directly observed by SAR.
   - Mention the optical evidence date latency when relevant.
6. AMBIGUITY: If a place name or question is ambiguous, present the candidate choices and ask the user to clarify.
"""


def detect_query_language(text: str) -> str:
    """Detect whether query is English, Nepali, Hindi, or romanised."""
    deva_chars = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    if deva_chars > 0:
        ne_markers = ["छ", "छन्", "थियो", "भयो", "भए", "कति", "बस्ती", "सडक", "पुल", "भत्किए", "बाढी", "कहाँ", "कसरी", "त्यहाँ", "के", "वटा", "मा"]
        hi_markers = ["है", "हैं", "था", "थी", "थे", "कितने", "कितना", "कितनी", "सड़क", "गाँव", "बस्तियां", "टूटे", "हुए", "बाढ़", "कहाँ", "कैसे", "वहाँ", "क्या", "पूरी", "नष्ट"]
        ne_score = sum(1 for m in ne_markers if m in text)
        hi_score = sum(1 for m in hi_markers if m in text)
        return "hi" if hi_score > ne_score else "ne"

    lower = text.lower().split()
    ne_rom = ["kati", "ghar", "basti", "bhatkie", "sadak", "chha", "chhan", "tyaha", "pul", "avastha", "kasari"]
    hi_rom = ["kitne", "kitna", "makan", "basteeya", "sadak", "hai", "hain", "wahan", "kya", "hua"]
    if any(m in lower for m in ne_rom):
        return "ne"
    if any(m in lower for m in hi_rom):
        return "hi"
    return "en"


@dataclass
class AgentResponse:
    """Structured response from the copilot."""

    text: str
    tools_called: List[str]
    tool_outputs: List[Dict[str, Any]]
    guard_passed: bool
    guard_retried: bool
    language: str
    active_settlement: Optional[str] = None
    clarification_needed: bool = False


class CopilotAgent:
    """Provider-agnostic conversational agent with guard verification and offline fallback."""

    def __init__(
        self,
        fact_store: FactStore,
        provider: str = "auto",  # "auto", "gemini", "openai", "anthropic", "offline"
        model: Optional[str] = None,
    ):
        self.store = fact_store
        self.tools = CopilotTools(fact_store)
        self.guard = NumberGuard()
        self.resolver = self.tools.resolver

        self.provider = self._select_provider(provider)
        self.model = model
        self.messages: List[Dict[str, Any]] = []
        self.active_settlement: Optional[str] = None
        self.conversation_tool_outputs: List[Dict[str, Any]] = []

        logger.info("CopilotAgent initialized with provider: %s", self.provider)

    def _select_provider(self, requested: str) -> str:
        req = requested.lower()
        if req in ["gemini", "openai", "anthropic", "offline"]:
            if req == "gemini" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                logger.warning("GEMINI_API_KEY not found; falling back to offline.")
                return "offline"
            if req == "openai" and not os.getenv("OPENAI_API_KEY"):
                logger.warning("OPENAI_API_KEY not found; falling back to offline.")
                return "offline"
            if req == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
                logger.warning("ANTHROPIC_API_KEY not found; falling back to offline.")
                return "offline"
            return req

        # Auto detection
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return "gemini"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "offline"

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool execution to CopilotTools."""
        if name == "event_summary":
            return self.tools.event_summary()
        elif name == "damage_summary":
            return self.tools.damage_summary(area=args.get("area"))
        elif name == "cutoff_settlements":
            return self.tools.cutoff_settlements(
                network=args.get("network", "vehicle"),
                scenario=args.get("scenario", "optimistic"),
            )
        elif name == "settlement_status":
            return self.tools.settlement_status(name=args.get("name", ""))
        elif name == "bridges_status":
            return self.tools.bridges_status()
        elif name == "repair_priority":
            return self.tools.repair_priority()
        elif name == "nearest_destination":
            return self.tools.nearest_destination(name=args.get("name", ""))
        elif name == "limitations":
            return self.tools.limitations()
        else:
            return {"error": f"Unknown tool '{name}'"}

    def ask(self, user_query: str) -> AgentResponse:
        """Process a user query, maintain context, call tools, and guard answers."""
        lang = detect_query_language(user_query)

        # Append to message history
        self.messages.append({"role": "user", "content": user_query})

        if self.provider == "offline":
            resp = self._offline_answer(user_query, lang)
            self.messages.append({"role": "assistant", "content": resp.text})
            return resp

        try:
            if self.provider == "gemini":
                resp = self._gemini_answer(user_query, lang)
            elif self.provider == "openai":
                resp = self._openai_answer(user_query, lang)
            elif self.provider == "anthropic":
                resp = self._anthropic_answer(user_query, lang)
            else:
                resp = self._offline_answer(user_query, lang)
        except Exception as e:
            logger.warning("LLM provider %s failed with %s; falling back to offline.", self.provider, e)
            resp = self._offline_answer(user_query, lang)

        self.messages.append({"role": "assistant", "content": resp.text})
        return resp

    # ==========================================
    # OFFLINE ENGINE (Deterministic Grounding)
    # ==========================================
    def _offline_answer(self, query: str, lang: str) -> AgentResponse:
        """Rule-based natural language intent parser and template answer generator."""
        q_lower = query.lower()

        # 1. Unanswerable topics check
        unanswerable_keywords = [
            "die", "died", "dying", "dead", "deaths", "death", "casualty", "casualties",
            "injured", "injuries", "killed", "kill", "weather", "forecast", "tomorrow",
            "prime minister", "minister", "budget", "cost", "money",
            "घाइते", "मृतक", "मृत्यु", "मरेका", "मरे", "मौत", "मौसम", "पूर्वानुमान",
            "प्रधानमन्त्री", "प्रधानमंत्री", "बजेट", "पैसा"
        ]
        if any(w in q_lower or w in query for w in unanswerable_keywords):
            msg = (
                "यो जानकारी भूउपग्रह तथा ओपन्स्ट्रीटम्याप विश्लेषणमा उपलब्ध छैन (not available in the data)। प्रणालीले केवल भौतिक पूर्वाधार क्षति, बस्ती पहुँच तथा सडक मर्मत प्राथमिकताको विश्लेषण गर्दछ।"
                if lang == "ne"
                else (
                    "यह जानकारी उपग्रह और ओपनस्ट्रीटमैप विश्लेषण में उपलब्ध नहीं है (not available in the data)। प्रणाली केवल बुनियादी ढांचे की क्षति, बस्ती पहुँच और सड़क मरम्मत प्राथमिकता का विश्लेषण करती है।"
                    if lang == "hi"
                    else "This information is not available in the data. The pipeline analyzes physical infrastructure damage, settlement accessibility, and repair prioritization only."
                )
            )
            return AgentResponse(
                text=msg,
                tools_called=[],
                tool_outputs=[],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                active_settlement=self.active_settlement,
            )

        # 2. Domain-specific general intents
        # Intent: Cut-off settlements
        if any(w in q_lower or w in query for w in ["cut off", "cutoff", "isolated", "disconnect", "सम्पर्कविहीन", "सम्पर्क विच्छेद", "कट अफ", "कटऑफ", "अलग्गिए"]):
            net = "walking" if any(w in q_lower or w in query for w in ["walk", "walking", "पैदल", "हिंडेर"]) else "vehicle"
            scen = "pessimistic" if any(w in q_lower or w in query for w in ["pessimistic", "worst", "निराशावादी"]) else "optimistic"
            out = self.tools.cutoff_settlements(network=net, scenario=scen)
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["cutoff_settlements"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # Intent: Repair priority
        if any(w in q_lower or w in query for w in ["repair", "fix", "priority", "marmat", "मर्मत", "प्राथमिकता", "मरम्मत"]):
            out = self.tools.repair_priority()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["repair_priority"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # Intent: Bridges status
        if any(w in q_lower or w in query for w in ["bridge", "bridges", "pul", "पुल", "पुलहरू"]):
            out = self.tools.bridges_status()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["bridges_status"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # Intent: Limitations & Uncertainty
        if any(w in q_lower or w in query for w in ["limitation", "limitations", "cloud", "clouds", "uncertain", "badal", "सीमितता", "बादल", "अनिश्चितता", "विश्वसनीयता"]):
            out = self.tools.limitations()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["limitations"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # 3. Follow-up detection (whole-word regex only)
        follow_up_regex = r"\b(there|that place|that|it|tyaha|त्यहाँ|वहाँ|उक्त)\b"
        is_follow_up = bool(re.search(follow_up_regex, query, flags=re.IGNORECASE))
        target_place = self.active_settlement if (is_follow_up and self.active_settlement) else None

        # 4. If not follow-up, try to extract specific place name candidate
        if not target_place:
            target_place, is_ambiguous, ambig_prompt = self._extract_and_resolve_place(query)
            if is_ambiguous:
                return AgentResponse(
                    text=ambig_prompt,
                    tools_called=["settlement_status"],
                    tool_outputs=[{"status": "ambiguous"}],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    clarification_needed=True,
                )

        # 5. If a target settlement is active/found
        if target_place:
            self.active_settlement = target_place
            if any(h in q_lower or h in query for h in ["hospital", "destination", "facility", "clinic", "अस्पताल", "स्वास्थ्य", "डाक्टर", "pugna sakinchha", "can reach"]):
                out = self.tools.nearest_destination(target_place)
                self.conversation_tool_outputs.append(out)
                text = self.guard.build_template_answer(out, lang)
                return AgentResponse(
                    text=text,
                    tools_called=["nearest_destination"],
                    tool_outputs=[out],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    active_settlement=self.active_settlement,
                )
            else:
                out = self.tools.settlement_status(target_place)
                self.conversation_tool_outputs.append(out)
                text = self.guard.build_template_answer(out, lang)
                return AgentResponse(
                    text=text,
                    tools_called=["settlement_status"],
                    tool_outputs=[out],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    active_settlement=self.active_settlement,
                )

        # Intent: Damage breakdown (buildings, roads)
        if any(w in q_lower or w in query for w in ["damage", "destroyed", "houses", "buildings", "roads", "भवन", "घर", "सडक", "क्षति"]):
            out = self.tools.damage_summary()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["damage_summary"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # Default fallback: event_summary
        out = self.tools.event_summary()
        self.conversation_tool_outputs.append(out)
        text = self.guard.build_template_answer(out, lang)
        return AgentResponse(
            text=text,
            tools_called=["event_summary"],
            tool_outputs=[out],
            guard_passed=True,
            guard_retried=False,
            language=lang,
        )

    def _extract_and_resolve_place(self, query: str) -> Tuple[Optional[str], bool, str]:
        """Attempt to extract place name from sentence and resolve."""
        clean = query.strip()
        # Remove common question phrasing
        patterns = [
            r"\b(what is the status of|status of|tell me about|how to reach|is there access to|how many houses in|how many buildings in|how many houses are there in)\b",
            r"\b(ko sthiti kasto chha|ma kati ghar chhan|ko sthiti|kasto chha|ma pugna sakinchha|pugna sakinchha|barema bhannuhos)\b",
            r"\b(की स्थिति क्या है|का हाल क्या है|में कितने घर हैं|के बारे में बताइए)\b",
            r"\b(ko|ma|in|about|to|the|is|of|for|at)\b",
        ]
        candidate_text = clean
        for p in patterns:
            candidate_text = re.sub(p, " ", candidate_text, flags=re.IGNORECASE)

        # Strip Devanagari postpositions from individual words
        tokens = candidate_text.split()
        cleaned_tokens = []
        for t in tokens:
            t_sub = re.sub(r"(को|का|की|मा|बाट|देखि|लाई|सम्म)$", "", t)
            t_sub = re.sub(r"[\?\.!,]", "", t_sub).strip()
            if t_sub:
                cleaned_tokens.append(t_sub)

        candidate = " ".join(cleaned_tokens).strip()
        if candidate and len(candidate) >= 3:
            res = self.resolver.resolve(candidate)
            if res.status == "ambiguous":
                return None, True, res.clarification_prompt
            if res.status in ["exact", "fuzzy"] and res.match and res.score >= 0.75:
                return res.match.get("name"), False, ""

        # Test full query as fallback only if short
        if len(clean.split()) <= 3:
            res = self.resolver.resolve(clean)
            if res.status == "ambiguous":
                return None, True, res.clarification_prompt
            if res.status in ["exact", "fuzzy"] and res.match and res.score >= 0.80:
                return res.match.get("name"), False, ""

        return None, False, ""

    # ==========================================
    # ONLINE PROVIDERS (Gemini, OpenAI, Anthropic)
    # ==========================================
    def _gemini_answer(self, query: str, lang: str) -> AgentResponse:
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return self._offline_answer(query, lang)

        client = genai.Client(api_key=api_key)
        model_name = self.model or "gemini-2.5-flash"

        # Construct tools
        tool_defs = get_tool_definitions()
        gemini_tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=d["name"],
                        description=d["description"],
                    )
                    for d in tool_defs
                ]
            )
        ]

        chat = client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=gemini_tools,
                temperature=0.1,
            ),
        )

        response = chat.send_message(query)
        tools_called = []
        tool_outputs = []

        # Check for function calls
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if part.function_call:
                    fc = part.function_call
                    fname = fc.name
                    fargs = dict(fc.args) if fc.args else {}
                    tools_called.append(fname)
                    out = self.execute_tool(fname, fargs)
                    tool_outputs.append(out)
                    self.conversation_tool_outputs.append(out)

                    # Send tool response
                    tool_resp = chat.send_message(
                        types.Part.from_function_response(
                            name=fname,
                            response={"result": out},
                        )
                    )
                    response = tool_resp

        answer_text = response.text or ""
        if not tool_outputs:
            return self._offline_answer(query, lang)

        # Number guard check
        guard_res = self.guard.check(answer_text, tool_outputs)
        guard_retried = False

        if not guard_res.is_valid:
            guard_retried = True
            retry_prompt = (
                f"NumberGuard Error: The numbers {guard_res.violating_numbers} in your response "
                f"do not exist in the tool outputs. Regenerate your answer strictly using only "
                f"numbers from the tool data."
            )
            retry_resp = chat.send_message(retry_prompt)
            answer_text = retry_resp.text or ""
            guard_res2 = self.guard.check(answer_text, tool_outputs)
            if not guard_res2.is_valid:
                answer_text = self.guard.build_template_answer(tool_outputs[0], lang)

        return AgentResponse(
            text=answer_text,
            tools_called=tools_called,
            tool_outputs=tool_outputs,
            guard_passed=guard_res.is_valid,
            guard_retried=guard_retried,
            language=lang,
            active_settlement=self.active_settlement,
        )

    def _openai_answer(self, query: str, lang: str) -> AgentResponse:
        import openai

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self._offline_answer(query, lang)

        client = openai.OpenAI(api_key=api_key)
        model_name = self.model or "gpt-4o-mini"

        defs = get_tool_definitions()
        openai_tools = [
            {"type": "function", "function": {"name": d["name"], "description": d["description"], "parameters": d["parameters"]}}
            for d in defs
        ]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in self.messages[-5:]:
            messages.append({"role": m["role"], "content": m["content"]})

        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=openai_tools,
            temperature=0.1,
        )

        choice = completion.choices[0]
        tools_called = []
        tool_outputs = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                fname = tc.function.name
                fargs = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tools_called.append(fname)
                out = self.execute_tool(fname, fargs)
                tool_outputs.append(out)
                self.conversation_tool_outputs.append(out)

                messages.append(choice.message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(out),
                })

            followup = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,
            )
            answer_text = followup.choices[0].message.content or ""
        else:
            answer_text = choice.message.content or ""
            if not tool_outputs:
                return self._offline_answer(query, lang)

        # Guard check
        guard_res = self.guard.check(answer_text, tool_outputs)
        guard_retried = False

        if not guard_res.is_valid:
            guard_retried = True
            messages.append({"role": "assistant", "content": answer_text})
            messages.append({
                "role": "user",
                "content": f"NumberGuard error: The numbers {guard_res.violating_numbers} were not found in the tool outputs. Re-write your answer using only numbers present in the tool results.",
            })
            retry_comp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,
            )
            answer_text = retry_comp.choices[0].message.content or ""
            guard_res2 = self.guard.check(answer_text, tool_outputs)
            if not guard_res2.is_valid:
                answer_text = self.guard.build_template_answer(tool_outputs[0], lang)

        return AgentResponse(
            text=answer_text,
            tools_called=tools_called,
            tool_outputs=tool_outputs,
            guard_passed=guard_res.is_valid,
            guard_retried=guard_retried,
            language=lang,
            active_settlement=self.active_settlement,
        )

    def _anthropic_answer(self, query: str, lang: str) -> AgentResponse:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return self._offline_answer(query, lang)

        client = anthropic.Anthropic(api_key=api_key)
        model_name = self.model or "claude-3-haiku-20240307"

        defs = get_tool_definitions()
        anthropic_tools = [
            {"name": d["name"], "description": d["description"], "input_schema": d["parameters"]}
            for d in defs
        ]

        messages = []
        for m in self.messages[-5:]:
            messages.append({"role": m["role"], "content": m["content"]})

        response = client.messages.create(
            model=model_name,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=anthropic_tools,
            max_tokens=1024,
            temperature=0.1,
        )

        tools_called = []
        tool_outputs = []
        answer_text = ""

        # Check for tool use blocks
        for block in response.content:
            if block.type == "tool_use":
                fname = block.name
                fargs = block.input or {}
                tools_called.append(fname)
                out = self.execute_tool(fname, fargs)
                tool_outputs.append(out)
                self.conversation_tool_outputs.append(out)

                tool_result_content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(out),
                    }
                ]
                followup = client.messages.create(
                    model=model_name,
                    system=SYSTEM_PROMPT,
                    messages=messages + [{"role": "assistant", "content": response.content}, {"role": "user", "content": tool_result_content}],
                    max_tokens=1024,
                    temperature=0.1,
                )
                for f_block in followup.content:
                    if f_block.type == "text":
                        answer_text += f_block.text
            elif block.type == "text":
                answer_text += block.text

        if not tool_outputs:
            return self._offline_answer(query, lang)

        guard_res = self.guard.check(answer_text, tool_outputs)
        guard_retried = False

        if not guard_res.is_valid:
            guard_retried = True
            answer_text = self.guard.build_template_answer(tool_outputs[0], lang)

        return AgentResponse(
            text=answer_text,
            tools_called=tools_called,
            tool_outputs=tool_outputs,
            guard_passed=guard_res.is_valid,
            guard_retried=guard_retried,
            language=lang,
            active_settlement=self.active_settlement,
        )
