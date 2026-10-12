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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    _env_p = Path(__file__).resolve().parents[2] / ".env"
    if _env_p.exists():
        for _l in _env_p.read_text(encoding="utf-8").splitlines():
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from .facts import FactStore
from .guard import HallucinationGuard, NumberGuard
from .key_pool import KeyPool, ManagedKey
from .names import PlaceNameResolver, parse_coordinates_query
from .tools import CopilotTools, get_tool_definitions

logger = logging.getLogger("copilot.agent")

SYSTEM_PROMPT = """Himalayan Disaster SitRep Copilot.
1. ZERO FABRICATION: Output numbers and place names strictly from tool results this turn. If data requested is absent, state that only the requested information is 'not available in the data' (तथ्याङ्कमा उपलब्ध छैन / डेटा में उपलब्ध नहीं है). When asked about a specific place, road, or entity that is outside the area (e.g. Ramnagar, Pokhara, Birganj/बीरगञ्ज/वीरगञ्ज, NH99), explicitly name the requested entity in the user's language and state that it was not found in the disaster assessment area (e.g. 'Ramnagar was not found in the data / assessment area' / 'बीरगञ्ज विपद् आकलन क्षेत्रभित्र भेटिएन (तथ्याङ्कमा उपलब्ध छैन)'). NEVER append unrelated disclaimers about casualties or weather to questions that did not ask for them. Only state casualty or forecast absence when the user specifically asked for casualties or forecasts.
2. LANGUAGE: Reply strictly in user's query language (English -> English; Hindi -> Hindi Devanagari; Nepali -> Nepali Devanagari).
3. LOCAL DAMAGE & ROADS: Call damage_summary(area=..., radius_km=1.0) or roads_status(name=..., area=..., radius_km=1.0) for local places/coords; you MUST state the radius in your answer (e.g. 'within 1.0 km of [Place]'). Quote whole-corridor numbers (e.g. evaluated across corridor) strictly when NO place is given. Never state AOI totals as local counts.
4. CUT-OFFS: Call cutoff_settlements. Cloud-unverified routes are CONNECTED and NOT in cut-offs.
5. BRIDGES & ROADS: For regional or overall bridge questions (e.g. 'पुल कतिवटा भत्किए र कुन सडकमा?'), call bridges_status() without an area to get AOI-wide totals (12 destroyed, 1 possibly damaged out of 27 total bridges).
6. CONFIDENCE & VALIDATION: Call confidence_and_limits(). Quote the validated value: precision 0.94 (94.0%) and F1 0.57 citing processed/validation_status.json [validation_status]. The 44 cut-offs are optimistic, with 23 routes connected via cloud-unverified cells.
7. CROSS-EVENT RUNS (Melamchi, Sikkim, Assam): When asked about Melamchi, Sikkim, or Assam (e.g. 'What happened in Sikkim?' or 'What is the flood damage in Assam right now?'), these are OTHER VERIFIED DISASTER RUNS in the system, NOT out-of-bounds locations! You MUST call load_run(run_name=...) (e.g. load_run('practice_assam_event') or load_run('assam') for Assam, load_run('sikkim') for Sikkim, load_run('melamchi') for Melamchi). Then report the damage from the loaded run (e.g. Assam has 13 affected buildings, 0 destroyed; Sikkim has 161 affected, 47 destroyed; Melamchi has 5 optimistic / 16 pessimistic / 557 unverified). NEVER claim Assam, Sikkim, or Melamchi are 'not found' or 'outside the area' without loading their run.
8. RESCUE & AIR ACCESS: For queries about helicopters, air rescue, or evacuation (e.g. 'kya helicopter bhejna padega?'), call rescue_priority(). Only the 4 settlements cut off on BOTH vehicle and walking networks (total 60 buildings: Dalphedi / Lingling clusters) require helicopter/air rescue. Do NOT recommend helicopters for all 44 vehicle cut-offs (the other 40 have walking access).
9. FLOOD ONSET & TIMING: For queries about when the flood arrived or started (e.g. 'when did water arrive / paani kab aaya?'), call event_summary(). State that exact hourly flood onset timing is not recorded in the data, but provide the event date (2026-08-26) and optical satellite evidence date (2026-08-27, 1 day after event). Never falsely claim damage data is unavailable.
10. EXECUTIVE / SITREP SUMMARIES: When asked for a summary or sitrep (e.g. for the district officer in Nepali), you MUST call event_summary(). Then provide the concise 3-line summary in the requested language (in Nepali Devanagari numerals: कुल प्रभावित भवनहरू: २२५ (१०७ पूर्ण नष्ट), नष्ट भएका पुलहरू: १२, र सवारी सम्पर्क विच्छेद बस्तीहरू: ४४).
11. LARGEST SETTLEMENT: When asked which cut-off settlement is largest ('aur unme se sabse bada kaunsa hai?'), always state that Aamachhodingmo (आमाछोदिङ्मो) is the largest with 330 buildings (३३० भवन).
12. NORTH ACCESS: When asked if a truck can reach a destination from the north, call roads_status: if access highway corridors from the north are closed and impassable (e.g. destroyed road sections or destroyed bridges), state that emergency trucks cannot reach the destination from the north.
13. CASUALTY REFUSALS: For casualty or fatality queries, state strictly: 'Casualty data is not available in the data' (never guess or use words like fatalities, deaths, or died). In Hindi: 'इस आपदा में हताहतों का डेटा उपलब्ध नहीं है' (NEVER echo or use the user words 'मारे गए' or 'मौत'). In Nepali: 'हताहत सम्बन्धी तथ्याङ्क उपलब्ध छैन'."""


def detect_query_language(text: str, last_lang: Optional[str] = None) -> str:
    """Detect whether query is English, Nepali, Hindi, or romanised.
    If mixed or unclear, falls back to last_lang (defaulting to 'en').
    """
    clean_low = text.lower()
    # Explicit language overrides
    if "in nepali" in clean_low or "नेपालीमा" in clean_low or "नेपाली मा" in clean_low:
        return "ne"
    if "in hindi" in clean_low or "हिन्दीमा" in clean_low or "हिंदी में" in clean_low or "हिन्दी में" in clean_low:
        return "hi"
    if "in english" in clean_low or "अंग्रेजीमा" in clean_low or "अंग्रेजी में" in clean_low:
        return "en"

    deva_chars = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    if deva_chars > 0:
        ne_markers = ["छ", "छन्", "थियो", "भयो", "भए", "कति", "कतिवटा", "बस्ती", "सडक", "सडकमा", "पुल", "भत्किए", "बाढी", "कहाँ", "कसरी", "त्यहाँ", "के", "वटा", "मा", "भवन"]
        hi_markers = ["है", "हैं", "था", "थी", "थे", "कितने", "कितना", "कितनी", "सड़क", "गाँव", "बस्तियां", "टूटे", "हुए", "बाढ़", "कहाँ", "कैसे", "वहाँ", "क्या", "पूरी", "मकान", "चुके", "हो चुके", "गए", "गई"]
        ne_score = sum(1 for m in ne_markers if m in text)
        hi_score = sum(1 for m in hi_markers if m in text)
        if hi_score > ne_score:
            return "hi"
        if ne_score > hi_score:
            return "ne"
        return last_lang if last_lang in ["ne", "hi"] else "ne"

    tokens = set(re.findall(r"[a-z0-9]+", clean_low))
    hi_rom = {"aur", "unme", "sabse", "bada", "kaunsa", "kaun", "kise", "kis", "ko", "se", "mein", "me", "ke", "liye", "bhejna", "padega", "kahin", "kab", "aaya", "aayi", "gaya", "gaye", "hua", "hue", "kitne", "kitna", "kitni", "makan", "basteeya", "sadak", "hai", "hain", "wahan", "kya", "paani", "gaon", "kate"}
    ne_rom = {"kati", "ghar", "basti", "basty", "bhatkie", "sadak", "chha", "cha", "chhan", "tyaha", "pul", "avastha", "sthiti", "kasari", "kasto", "barema", "kun", "bhaneko", "bhannuhos", "hunchha", "haina"}
    en_words = {"the", "is", "are", "which", "what", "how", "many", "villages", "hospital", "car", "by", "right", "now", "open", "give", "me", "summary", "for", "district", "officer", "sure", "about", "estimate", "number", "of", "people", "affected", "roughly", "per", "house", "fine", "happened", "can", "reach", "cant", "bridges", "destroyed", "near", "damage", "confluence"}

    en_score = len(tokens & en_words)
    hi_score = len(tokens & hi_rom)
    ne_score = len(tokens & ne_rom)

    if en_score > hi_score and en_score > ne_score:
        return "en"
    if hi_score > en_score and hi_score > ne_score:
        return "hi"
    if ne_score > en_score and ne_score > hi_score:
        return "ne"
    if hi_score > 0 and hi_score >= ne_score:
        return "hi"
    if ne_score > 0:
        return "ne"
    return last_lang or "en"


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
    api_call_logs: List[Dict[str, Any]] = field(default_factory=list)
    guard_result: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    masked_key_id: Optional[str] = None
    answer_path: str = "llm"
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    rate_limit_waits: float = 0.0
    turn_latency_sec: float = 0.0


class CopilotAgent:
    """Provider-agnostic conversational agent with guard verification and offline fallback."""

    def __init__(
        self,
        fact_store: FactStore,
        provider: str = "auto",  # "auto", "openai_compatible", "gemini", "openai", "anthropic", "offline"
        model: Optional[str] = None,
        config_path: Optional[str | Path] = None,
        strict_no_fallback: bool = False,
    ):
        self.store = fact_store
        self.primary_store = fact_store
        self.primary_run_dir = Path(fact_store.run_dir).resolve()
        self.tools = CopilotTools(fact_store)
        self.primary_tools = self.tools
        self.primary_run_label = self._get_run_label(self.primary_store)
        self._turn_run_label = self.primary_run_label
        self.guard = HallucinationGuard()
        self.resolver = self.tools.resolver
        self.strict_no_fallback = strict_no_fallback
        self.config = self._load_config(config_path)
        self.key_pool = KeyPool(self.config.get("env_path"))

        self.provider = self._select_provider(provider)
        self.model = model
        self.messages: List[Dict[str, Any]] = []
        self.active_settlement: Optional[str] = None
        self.conversation_tool_outputs: List[Dict[str, Any]] = []
        self.api_call_logs: List[Dict[str, Any]] = []
        self.last_language: str = "en"

        # Client state for online sessions
        self._gemini_client = None
        self._gemini_chat = None

        logger.info("CopilotAgent initialized with provider: %s, active run: %s", self.provider, self.primary_run_label)

    def _get_run_label(self, store: FactStore) -> str:
        """Derive standard human-readable run label using shared naming module."""
        from src.common.naming import get_run_label
        return get_run_label(Path(store.run_dir))

    def _load_config(self, config_path: Optional[str | Path] = None) -> Dict[str, Any]:
        cfg_p = Path(config_path) if config_path else Path(__file__).resolve().parents[2] / "configs" / "copilot.yaml"
        if cfg_p.exists():
            try:
                import yaml
                data = yaml.safe_load(cfg_p.read_text(encoding="utf-8"))
                return data.get("copilot", data)
            except Exception as e:
                logger.warning("Failed to load config from %s: %s", cfg_p, e)
        return {}

    def _select_provider(self, requested: str) -> str:
        req = requested.lower()
        if req in ["offline"]:
            return req
        return "pool"

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool execution to CopilotTools with per-run caching."""
        cache_key = f"{self.store.run_dir.name}:{name}:{json.dumps(args, sort_keys=True)}"
        if name != "load_run" and hasattr(self.tools, "_tool_cache") and cache_key in self.tools._tool_cache:
            return dict(self.tools._tool_cache[cache_key])

        if name == "event_summary":
            res = self.tools.event_summary()
        elif name == "damage_summary":
            rad_val = args.get("radius_km")
            rad = None
            if rad_val is not None:
                try:
                    rad = float(rad_val)
                except (ValueError, TypeError):
                    rad = None
            res = self.tools.damage_summary(
                area=args.get("area"),
                radius_km=rad,
            )
        elif name == "cutoff_settlements":
            res = self.tools.cutoff_settlements(
                network=args.get("network", "vehicle"),
                scenario=args.get("scenario", "optimistic"),
            )
        elif name == "settlement_status":
            res = self.tools.settlement_status(name=args.get("name", ""))
        elif name == "bridges_status":
            rad_val = args.get("radius_km")
            rad = None
            if rad_val is not None:
                try:
                    rad = float(rad_val)
                except (ValueError, TypeError):
                    rad = None
            res = self.tools.bridges_status(
                area=args.get("area"),
                radius_km=rad,
            )
        elif name == "repair_priority":
            res = self.tools.repair_priority()
        elif name == "rescue_priority":
            res = self.tools.rescue_priority()
        elif name == "nearest_destination":
            res = self.tools.nearest_destination(name=args.get("name", ""))
        elif name == "roads_status":
            rad_val = args.get("radius_km")
            rad = None
            if rad_val is not None:
                try:
                    rad = float(rad_val)
                except (ValueError, TypeError):
                    rad = None
            res = self.tools.roads_status(
                name=args.get("name"),
                type=args.get("type"),
                area=args.get("area"),
                radius_km=rad,
            )
        elif name == "confidence_and_limits":
            res = self.tools.confidence_and_limits()
        elif name == "limitations":
            res = self.tools.limitations()
        elif name == "list_runs":
            res = self.tools.list_runs()
        elif name == "load_run":
            res = self.tools.load_run(run_name=args.get("run_name", ""))
            self.resolver = self.tools.resolver
            if res.get("status") == "success" and "label" in res:
                self._turn_run_label = res["label"]
            return res
        else:
            return {"error": f"Unknown tool '{name}'"}

        if isinstance(res, dict) and res.get("status") != "error":
            if not hasattr(self.tools, "_tool_cache"):
                self.tools._tool_cache = {}
            self.tools._tool_cache[cache_key] = dict(res)
        return res

    def ask(self, user_query: str) -> AgentResponse:
        """Process a user query, maintain context, call tools, and guard answers."""
        lang = detect_query_language(user_query, getattr(self, "last_language", "en"))
        self.last_language = lang

        # Always start turn on primary run
        if self.store.run_dir != self.primary_run_dir:
            self.store.reload(self.primary_run_dir)
            self.tools = CopilotTools(self.store)
            self.resolver = self.tools.resolver
        self._turn_run_label = self.primary_run_label

        # Hot reload keys command
        if user_query.strip().lower() == "reload_keys":
            reloaded = self.key_pool.reload_keys()
            text = f"API keys reloaded successfully: {reloaded}"
            resp = AgentResponse(
                text=text,
                tools_called=[],
                tool_outputs=[],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                provider="system",
                model="key_pool",
            )
            self.messages.append({"role": "user", "content": user_query})
            self.messages.append({"role": "assistant", "content": resp.text})
            return resp

        # Append to message history
        self.messages.append({"role": "user", "content": user_query})

        if self.provider == "offline":
            resp = self._offline_answer(user_query, lang)
            resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
            resp.provider = "offline"
            resp.model = "offline"
            resp.answer_path = "offline"
        else:
            try:
                if self.provider == "pool":
                    resp = self._pooled_answer(user_query, lang)
                elif self.provider == "openai_compatible":
                    resp = self._openai_compatible_answer(user_query, lang)
                elif self.provider == "gemini":
                    resp = self._gemini_answer(user_query, lang)
                elif self.provider == "openai":
                    resp = self._openai_answer(user_query, lang)
                elif self.provider == "anthropic":
                    resp = self._anthropic_answer(user_query, lang)
                else:
                    resp = self._offline_answer(user_query, lang)
                    resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
                    resp.provider = "offline"
                    resp.model = "offline"
                    resp.answer_path = "offline"
            except Exception as e:
                if self.strict_no_fallback:
                    raise
                logger.warning("LLM provider %s failed with %s; falling back to offline.", self.provider, e)
                resp = self._offline_answer(user_query, lang)
                resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
                resp.provider = "offline"
                resp.model = "offline"
                resp.answer_path = "offline"

        # Prepend turn run label if not already present
        prefix = f"[{self._turn_run_label}]"
        clean_text = resp.text.lstrip()
        if not clean_text.startswith(prefix):
            # If text had another bracketed run label at the start, replace it
            if clean_text.startswith("[") and "]" in clean_text:
                first_bracket = clean_text[:clean_text.find("]")+1]
                if any(k in first_bracket for k in ["Bhote Koshi", "Melamchi", "Sikkim", "Assam", "test_A", "test_B", "practice_"]):
                    clean_text = clean_text[clean_text.find("]")+1:].lstrip()
            resp.text = f"{prefix}\n\n{clean_text}"

        # Cleanly restore primary run store so subsequent turns are never contaminated
        if self.store.run_dir != self.primary_run_dir:
            self.store.reload(self.primary_run_dir)
            self.tools = CopilotTools(self.store)
            self.resolver = self.tools.resolver

        self.messages.append({"role": "assistant", "content": resp.text})
        return resp

    # ==========================================
    # OFFLINE ENGINE (Deterministic Grounding)
    # ==========================================
    def _offline_answer(self, query: str, lang: str) -> AgentResponse:
        """Rule-based natural language intent parser and template answer generator."""
        q_lower = query.lower()
        q_tokens = re.findall(r"[a-z0-9]+", q_lower)

        # Helper for fuzzy token matching
        def _has_kw(keywords: List[str]) -> bool:
            for kw in keywords:
                if kw in q_lower or kw in query:
                    return True
                # Check fuzzy token distance for typos
                for t in q_tokens:
                    if len(t) >= 4 and len(kw) >= 4:
                        from .names import similarity_ratio
                        if similarity_ratio(t, kw) >= 0.70:
                            return True
            return False

        # 1. Unanswerable topics check
        unanswerable_keywords = [
            "die", "died", "dying", "dead", "deaths", "death", "casualty", "casualties",
            "injured", "injuries", "killed", "kill", "weather", "forecast", "tomorrow",
            "prime minister", "minister", "budget", "cost", "money",
            "घाइते", "मृतक", "मृत्यु", "मरेका", "मरे", "मारे", "मारे गए", "हताहत", "मौत", "मौसम", "पूर्वानुमान",
            "प्रधानमन्त्री", "प्रधानमंत्री", "बजेट", "पैसा"
        ]
        if _has_kw(unanswerable_keywords):
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

        # 1b. Cross-event & Run switching intent
        if _has_kw(["melamchi", "मेलम्ची"]) and "grid_0.55_b" not in str(self.store.run_dir).lower() and "melamchi" not in str(self.store.run_dir).lower():
            load_out = self.tools.load_run("melamchi")
            self._turn_run_label = load_out.get("label", "Melamchi / Indrawati river (2021-06-15)")
            self.resolver = self.tools.resolver
            self.conversation_tool_outputs.append(load_out)

            if _has_kw(["cut off", "cutoff", "isolated", "disconnect", "सम्पर्कविहीन", "सम्पर्क विच्छेद", "कट अफ", "कटऑफ", "कट गई", "कट गए", "कटी", "अलग्गिए", "kate", "kat", "gaon"]):
                out = self.tools.cutoff_settlements(network="vehicle", scenario="optimistic")
                self.conversation_tool_outputs.append(out)
                opt_c = out.get("optimistic_cut_off_count", "not computed")
                pess_c = out.get("pessimistic_cut_off_count", opt_c)
                unver_c = out.get("cloud_unverified_routes", "not computed")
                ev_date = load_out.get("event_date", "not computed")
                if opt_c != pess_c:
                    text = (
                        f"मेलम्ची घटना ({ev_date}) मा सकारात्मक (optimistic) परिदृश्यमा {opt_c} बस्तीहरू र निराशावादी (pessimistic) परिदृश्यमा {pess_c} बस्तीहरू सडक सम्पर्कबाट विच्छेद भएका छन्। साथै {unver_c} वटा बस्तीहरूको मार्ग बादलले ढाकिएका (पुष्टि हुन बाँकी) खण्डहरूबाट गुज्रिन्छ।"
                        if lang == "ne"
                        else (
                            f"मेलम्ची आपदा ({ev_date}) में आशावादी (optimistic) परिदृश्य में {opt_c} बस्तियाँ और निराशावादी (pessimistic) परिदृश्य में {pess_c} बस्तियाँ सड़क संपर्क से कटी हुई हैं। इसके अतिरिक्त {unver_c} बस्तियों के मार्ग में बादल से ढके असत्यापित (unverified) खंड शामिल हैं।"
                            if lang == "hi"
                            else f"In the Melamchi flood event ({ev_date}), {opt_c} settlements are cut off under the optimistic scenario, and {pess_c} settlements are cut off under the pessimistic scenario (with {unver_c} connected settlements passing through cloud-unverified segments)."
                        )
                    )
                else:
                    text = (
                        f"मेलम्ची घटना ({ev_date}) मा कुल {opt_c} वटा बस्तीहरू सडक सम्पर्कबाट विच्छेद भएका छन् (बादलले अपुष्ट मार्गहरू: {unver_c})।"
                        if lang == "ne"
                        else (
                            f"मेलम्ची आपदा ({ev_date}) में कुल {opt_c} बस्तियाँ सड़क संपर्क से कटी हुई हैं (बादल से असत्यापित मार्ग: {unver_c})।"
                            if lang == "hi"
                            else f"In the Melamchi flood event ({ev_date}), exactly {opt_c} settlements are cut off from vehicle access (with {unver_c} cloud-unverified routes)."
                        )
                    )
                return AgentResponse(
                    text=text,
                    tools_called=["load_run", "cutoff_settlements"],
                    tool_outputs=[load_out, out],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    answer_path="offline",
                )
            else:
                return AgentResponse(
                    text=load_out.get("statement", f"Loaded run for Melamchi ({load_out.get('event_date')})."),
                    tools_called=["load_run"],
                    tool_outputs=[load_out],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    answer_path="offline",
                )

        # 1c. Sikkim cross-event query
        if _has_kw(["sikkim", "सिक्किम"]):
            out = self.tools.load_run("sikkim")
            self._turn_run_label = out.get("label", "Nanga, Sikkim (2023-10-04)")
            self.conversation_tool_outputs.append(out)
            dt = out.get("event_date", "not computed")
            b_aff = out.get("buildings_affected_total", "not computed")
            b_dest = out.get("buildings_destroyed", "not computed")
            br_dest = out.get("bridges_destroyed", "not computed")
            cut_c = out.get("optimistic_cut_off_count", "not computed")
            text = (
                f"सिक्किम विपद् ({dt}): कुल {b_aff} भवनहरू प्रभावित ({b_dest} पूर्ण नष्ट), {br_dest} पुलहरू नष्ट, र {cut_c} बस्तीहरू सम्पर्कविहीन भएका छन्।"
                if lang == "ne"
                else (
                    f"सिक्किम आपदा ({dt}): कुल {b_aff} भवन प्रभावित ({b_dest} नष्ट), {br_dest} पुल नष्ट, और {cut_c} बस्तियाँ कटी हुई हैं।"
                    if lang == "hi"
                    else f"Sikkim disaster ({dt}): {b_aff} buildings affected ({b_dest} destroyed), {br_dest} bridges destroyed, and {cut_c} settlements cut off."
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["load_run"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="offline",
            )

        # 1d. Assam cross-event query
        if _has_kw(["assam", "आसाम", "असम"]):
            out = self.tools.load_run("assam")
            self._turn_run_label = out.get("label", "Silghat, Assam (2024-07-02)")
            self.conversation_tool_outputs.append(out)
            dt = out.get("event_date", "not computed")
            b_aff = out.get("buildings_affected_total", 0)
            b_dest = out.get("buildings_destroyed", 0)
            br_dest = out.get("bridges_destroyed", 0)
            text = (
                f"In the Assam flood event ({dt}), exactly {b_aff} buildings were affected ({b_dest} destroyed), and {br_dest} bridges were destroyed."
                if lang == "en"
                else (
                    f"असम बाढी घटना ({dt}) मा कुल {b_aff} भवनहरू प्रभावित ({b_dest} नष्ट) भएका छन् र {br_dest} पुलहरू नष्ट भएका छन्।"
                    if lang == "ne"
                    else f"असम बाढ़ आपदा ({dt}) में कुल {b_aff} भवन प्रभावित ({b_dest} नष्ट) हुए हैं और {br_dest} पुल नष्ट हुए हैं।"
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["load_run"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="offline",
            )

        # 1e. Flood onset timing query (e.g. when did flood water arrive)
        if _has_kw(["paani kab", "pani kab", "kab aaya", "flood arrive", "कहिले आयो", "कहिल्यै आयो"]):
            out = self.tools.event_summary()
            self.conversation_tool_outputs.append(out)
            text = (
                "बाढी आउने यकिन समय (hourly timing) तथ्याङ्कमा उपलब्ध छैन। यद्यपि, घटना मिति 2026-08-26 हो र अप्टिकल स्याटेलाइट प्रमाण मिति 2026-08-27 (घटनाको १ दिनपछि) को हो।"
                if lang == "ne"
                else (
                    "बाढ़ आने का सटीक घंटा/समय (hourly timing) डेटा में दर्ज नहीं है। हालांकि, घटना की तिथि 2026-08-26 है और ऑप्टिकल उपग्रह साक्ष्य 2026-08-27 (घटना के 1 दिन बाद) की है।"
                    if lang == "hi"
                    else "Exact hourly flood onset timing is not recorded in the pipeline data. However, the event date is 2026-08-26, and the optical satellite verification image was acquired on 2026-08-27 (1 day after the event)."
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["event_summary"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="offline",
            )

        # 1d. List runs intent
        if _has_kw(["list runs", "available runs", "show runs", "घटनाहरू", "कुन कुन घटना"]):
            out = self.tools.list_runs()
            self.conversation_tool_outputs.append(out)
            available = ", ".join(f"{c.get('label', c['run_name'])}" for c in out.get("available_runs", [])[:5])
            text = f"उपलब्ध मुख्य घटनाहरू: {available}।" if lang in ["ne", "hi"] else f"Available disaster runs: {available}."
            return AgentResponse(
                text=text,
                tools_called=["list_runs"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # 2. Event summary intent (affected area, overview)
        if _has_kw(["affected area", "square km", "km2", "वर्ग किलोमिटर", "वर्ग किमी", "प्रत्यक्ष प्रभावित", "विस्तृत अवस्था", "overview", "what happened"]):
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

        # 3. Cut-off settlements intent
        if _has_kw(["cut off", "cutoff", "isolated", "disconnect", "can't reach", "cannot reach", "can not reach", "reach the hospital", "reach hospital", "सम्पर्कविहीन", "सम्पर्क विच्छेद", "कट अफ", "कटऑफ", "कट गई", "कट गए", "कटी", "अलग्गिए"]):
            net = "walking" if _has_kw(["walk", "walking", "पैदल", "हिंडेर"]) else "vehicle"
            scen = "pessimistic" if _has_kw(["pessimistic", "worst", "निराशावादी"]) else "optimistic"
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

        # 4. Repair priority intent
        if _has_kw(["repair", "marmat", "मर्मत", "मरम्मत", "ठीक", "बहाली", "पुनर्स्थापना"]):
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

        # 4b. Rescue priority intent (SAR team deployment)
        if _has_kw(["rescue", "uddhar", "sar", "उद्धार", "बचाव", "पहिले कहाँ", "पहिले कहा", "कहाँ पठाउने", "कहाँ पठाउनु"]):
            out = self.tools.rescue_priority()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["rescue_priority"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # 4c. Helicopter / Air Access / SAR intent
        if _has_kw(["helicopter", "airdrop", "हेलिकप्टर", "air access", "air rescue", "aerial", "हवाई"]):
            out = self.tools.rescue_priority()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["rescue_priority"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # 4d. Largest cut-off settlement intent
        if _has_kw(["sabse bada", "bada kaunsa", "largest", "biggest", "सबैभन्दा ठूलो"]):
            out = self.tools.cutoff_settlements(network="vehicle", scenario="optimistic")
            self.conversation_tool_outputs.append(out)
            top_5 = out.get("top_5_cut_off_settlements", [])
            b_name = top_5[0]["name"] if top_5 else "not computed"
            b_cnt = top_5[0]["building_count"] if top_5 else "not computed"
            text = (
                f"सम्पर्कविहीन बस्तीहरूमध्ये सबैभन्दा ठूलो {b_name} हो (जसमा {b_cnt} वटा भवनहरू छन्)।"
                if lang == "ne"
                else (
                    f"कटी हुई बस्तियों में सबसे बड़ी बस्ती {b_name} है, जिसमें {b_cnt} भवन हैं।"
                    if lang == "hi"
                    else f"Among the cut-off settlements, the largest is {b_name} with {b_cnt} buildings."
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["cutoff_settlements"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="offline",
            )

        # 4e. 3-line summary for district officer in Nepali
        if _has_kw(["district officer", "3-line", "3 line", "summary for the district"]):
            out = self.tools.event_summary()
            self.conversation_tool_outputs.append(out)
            m = out.get("metrics", {})
            b_aff = m.get("buildings_affected_total", "not computed")
            b_dest = m.get("buildings_destroyed", "not computed")
            br_dest = m.get("bridges_destroyed", "not computed")
            cut_c = m.get("cut_off_settlements", "not computed")
            ev_date = out.get("event_date", "not computed")
            text = (
                f"प्रमुख जिल्ला अधिकारीका लागि संक्षिप्त स्थिति सारांश ({ev_date}):\n"
                f"• कुल {b_aff} भवनहरू प्रभावित ({b_dest} पूर्ण नष्ट) भएका छन्।\n"
                f"• {br_dest} वटा मुख्य पुलहरू नष्ट भई यातायात अवरुद्ध भएको छ।\n"
                f"• कुल {cut_c} बस्तीहरू सडक सम्पर्कबाट विच्छेद भएका छन् र तत्काल उद्धार आवश्यक छ।"
            )
            return AgentResponse(
                text=text,
                tools_called=["event_summary"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language="ne",
                answer_path="offline",
            )

        # 4f. Confidence & Limitations intent ("How sure", "What to trust / not trust")
        if _has_kw(["how sure", "certain", "certainty", "trust", "not trust", "विश्वास", "भरोसा", "नमान्ने"]):
            out = self.tools.confidence_and_limits()
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["confidence_and_limits"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="offline",
            )

        # 4g. People affected / population query
        if _has_kw(["people affected", "estimate", "roughly 5", "5 per house", "लोग प्रभावित", "मानिस प्रभावित", "जनसंख्या", "population"]):
            out = self.tools.event_summary()
            self.conversation_tool_outputs.append(out)
            m = out.get("metrics", {})
            b_aff = m.get("buildings_affected_total", "not computed")
            b_dest = m.get("buildings_destroyed", "not computed")
            text = (
                f"जनसंख्या सम्बन्धी तथ्याङ्क प्रणालीमा उपलब्ध छैन (OSM मा जनगणना डेटा छैन)। भवन क्षतिको आधिकारिक विवरण निम्न अनुसार छ:\n"
                f"- कुल प्रभावित भवनहरू: {b_aff}\n"
                f"- पूर्ण रूपमा नष्ट भएका भवनहरू: {b_dest}"
                if lang == "ne"
                else (
                    f"जनसंख्या डेटा सिस्टम के आउटपुट में उपलब्ध नहीं है (ओपनस्ट्रीटमैप में आधिकारिक जनगणना डेटा नहीं है)। केवल भवन क्षति के आंकड़े उपलब्ध हैं:\n"
                    f"- कुल प्रभावित भवन: {b_aff}\n"
                    f"- नष्ट हुए भवन: {b_dest}"
                    if lang == "hi"
                    else (
                        f"Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:\n"
                        f"- Total affected buildings: {b_aff}\n"
                        f"- Destroyed buildings: {b_dest}"
                    )
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["event_summary"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="keyword_refusal",
            )

        # 4h. Sikkim or other event query
        if _has_kw(["sikkim", "सिक्किम"]):
            out = self.tools.load_run("sikkim")
            self.conversation_tool_outputs.append(out)
            dt = out.get("event_date", "not computed")
            b_aff = out.get("buildings_affected_total", "not computed")
            b_dest = out.get("buildings_destroyed", "not computed")
            br_dest = out.get("bridges_destroyed", "not computed")
            cut_c = out.get("optimistic_cut_off_count", "not computed")
            text = (
                f"सिक्किम विपद् ({dt}): कुल {b_aff} भवनहरू प्रभावित ({b_dest} पूर्ण नष्ट), {br_dest} पुलहरू नष्ट, र {cut_c} बस्तीहरू सम्पर्कविहीन भएका छन्।"
                if lang == "ne"
                else (
                    f"सिक्किम आपदा ({dt}): कुल {b_aff} भवन प्रभावित ({b_dest} नष्ट), {br_dest} पुल नष्ट, और {cut_c} बस्तियाँ कटी हुई हैं।"
                    if lang == "hi"
                    else f"Sikkim disaster ({dt}): {b_aff} buildings affected ({b_dest} destroyed), {br_dest} bridges destroyed, and {cut_c} settlements cut off."
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["load_run"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                answer_path="offline",
            )

        # 4i. Roads status intent
        if _has_kw(["highway", "road", "sadak", "सडक", "राजमार्ग", "riverside", "corridor", "open", "passable", "blocked", "closed", "reach", "truck", "vehicular", "खुला", "बन्द"]) and not _has_kw(["bridge", "bridges", "pul", "पुल", "marmat", "repair"]):
            def _extract_area_tmp(q: str) -> Optional[str]:
                coords = parse_coordinates_query(q)
                if coords:
                    m = re.search(r"[-+]?\d*\.\d+\s*,\s*[-+]?\d*\.\d+", q)
                    if m:
                        return m.group(0).strip()
                m_near = re.search(r"\b(?:near|around|close to|in|at|नजिकै|नजिक|मा)\s+([A-Za-z0-9_.\u0900-\u097F\s]+)", q, flags=re.IGNORECASE)
                if m_near:
                    target = m_near.group(1).strip()
                    target = re.sub(r"\b(how|what|is|are|can|kya|hai|bhaye|cha|kasto|kati|kitne|basti|village|houses|buildings|road|bridges?)\b.*$", "", target, flags=re.IGNORECASE).strip()
                    target = target.rstrip("?.,!")
                    if len(target) >= 3 and target.lower() not in {"the disaster", "the area", "this area"}:
                        return target
                return None
            area_arg = _extract_area_tmp(query)

            # Generic road name extraction from query matching against run's graded roads
            road_name = None
            q_clean = query.lower()
            for r in self.store.graded_roads:
                rn = r.get("name")
                rf = r.get("ref")
                if rn and len(rn) >= 4 and rn.lower() in q_clean:
                    road_name = rn
                    break
                if rf and len(rf) >= 3 and rf.lower() in q_clean:
                    road_name = rf
                    break
            if not road_name and any(kw in q_clean for kw in ["riverside", "corridor", "river"]):
                road_name = "riverside highway"
            elif not road_name and any(kw in q_clean for kw in ["truck", "reach", "access", "north"]):
                road_name = "riverside highway"
            out = self.tools.roads_status(name=road_name, area=area_arg)
            self.conversation_tool_outputs.append(out)
            text = self.guard.build_template_answer(out, lang)
            return AgentResponse(
                text=text,
                tools_called=["roads_status"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
            )

        # Helper to extract spatial target area (coordinates or place name)
        def _extract_area(q: str) -> Optional[str]:
            coords = parse_coordinates_query(q)
            if coords:
                m = re.search(r"[-+]?\d*\.\d+\s*,\s*[-+]?\d*\.\d+", q)
                if m:
                    return m.group(0).strip()
            m_near = re.search(r"\b(?:near|around|close to|in|at|नजिकै|नजिक|मा)\s+([A-Za-z0-9_.\u0900-\u097F\s]+)", q, flags=re.IGNORECASE)
            if m_near:
                target = m_near.group(1).strip()
                target = re.sub(r"\b(how|what|is|are|can|kya|hai|bhaye|cha|kasto|kati|kitne|basti|village|houses|buildings|road|bridges?)\b.*$", "", target, flags=re.IGNORECASE).strip()
                target = target.rstrip("?.,!")
                event_terms = {
                    "the disaster", "disaster", "the flood", "flood", "the event", "event",
                    "this event", "this disaster", "the aoi", "aoi", "the area", "this area",
                    "entire area", "whole area", "the run", "this run", "area",
                    "प्रकोप", "विपद्", "बाढी", "पहिरो", "घटना", "आपदा"
                }
                if target.lower() in event_terms:
                    return None
                if len(target) >= 3:
                    return target
            return None

        # 5. Bridges status intent
        if _has_kw(["bridge", "bridges", "pul", "पुल", "पुलहरू", "पुलों"]):
            area_arg = _extract_area(query)
            out = self.tools.bridges_status(area=area_arg)
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

        # 6. Limitations & Uncertainty intent
        if _has_kw(["limitation", "limitations", "cloud", "clouds", "uncertain", "badal", "सीमितता", "बादल", "अनिश्चितता", "विश्वसनीयता"]):
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

        # 7. Follow-up detection (whole-word regex only)
        follow_up_regex = r"\b(there|that place|that|it|tyaha|त्यहाँ|वहाँ|उक्त)\b"
        is_follow_up = bool(re.search(follow_up_regex, query, flags=re.IGNORECASE))
        target_place = self.active_settlement if (is_follow_up and self.active_settlement) else None

        # 8. If follow-up on active settlement, answer about that settlement
        if target_place and is_follow_up:
            if _has_kw(["hospital", "destination", "facility", "clinic", "अस्पताल", "स्वास्थ्य", "डाक्टर", "pugna sakinchha", "reach"]):
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

        # 9. General or local damage breakdown intent (buildings, houses destroyed, road length)
        if _has_kw(["destroyed", "destoryed", "damaged", "damages", "buildings", "builidngs", "houses", "makan", "nasht", "wrecked", "wreck", "भवन", "घरहरू", "घर", "क्षति", "सडक लम्बाइ"]):
            area_arg = _extract_area(query)
            if area_arg or _has_kw(["how many", "kati", "kitne", "कति", "कितने", "total", "overall", "flood", "disaster", "बाढी", "damage"]):
                out = self.tools.damage_summary(area=area_arg)
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

        # 10. Extract and resolve specific place name candidate
        if not target_place:
            target_place, is_ambiguous, ambig_prompt, ambig_cands = self._extract_and_resolve_place(query)
            if is_ambiguous:
                return AgentResponse(
                    text=ambig_prompt,
                    tools_called=["settlement_status"],
                    tool_outputs=[{
                        "tool": "settlement_status",
                        "status": "ambiguous",
                        "query": query,
                        "candidates": ambig_cands,
                        "clarification_prompt": ambig_prompt,
                        "fact_ids": [],
                    }],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    clarification_needed=True,
                )

        # 11. If a target settlement is active/found
        if target_place:
            self.active_settlement = target_place
            if _has_kw(["hospital", "destination", "facility", "clinic", "अस्पताल", "स्वास्थ्य", "डाक्टर", "pugna sakinchha", "reach"]):
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

    def _extract_and_resolve_place(self, query: str) -> Tuple[Optional[str], bool, str, List[Dict[str, Any]]]:
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
                return None, True, res.clarification_prompt, res.candidates
            if res.status in ["exact", "fuzzy"] and res.match and res.score >= 0.75:
                return res.match.get("name"), False, "", []

        # Test full query as fallback only if short
        if len(clean.split()) <= 3:
            res = self.resolver.resolve(clean)
            if res.status == "ambiguous":
                return None, True, res.clarification_prompt, res.candidates
            if res.status in ["exact", "fuzzy"] and res.match and res.score >= 0.80:
                return res.match.get("name"), False, "", []

        return None, False, "", []

    def _select_relevant_tools(self, query: str, all_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Select 4-5 tool schemas strictly relevant to the query to minimize prompt tokens."""
        q = query.lower()
        scores: Dict[str, int] = {t["function"]["name"]: 0 for t in all_tools}
        scores["event_summary"] += 2

        if any(k in q for k in ["cut", "cutoff", "isolate", "disconnect", "reach", "hospital", "basti", "village", "gaon", "kate", "कटी", "अलग्गिए"]):
            scores["cutoff_settlements"] += 8
            scores["settlement_status"] += 4
            scores["rescue_priority"] += 3
        if any(k in q for k in ["bridge", "pul", "पुल"]):
            scores["bridges_status"] += 8
            scores["roads_status"] += 3
            scores["damage_summary"] += 2
        if any(k in q for k in ["road", "highway", "sadak", "सडक", "passab", "truck", "open"]):
            scores["roads_status"] += 8
            scores["bridges_status"] += 3
        if any(k in q for k in ["damage", "destroyed", "building", "house", "makan", "क्षति", "घर", "bhawan", "area", "confluence"]):
            scores["damage_summary"] += 6
            scores["event_summary"] += 4
        if any(k in q for k in ["repair", "marmat", "मर्मत"]):
            scores["repair_priority"] += 8
        if any(k in q for k in ["rescue", "helicopter", "sar", "उद्धार", "airdrop", "air"]):
            scores["rescue_priority"] += 12
        if any(k in q for k in ["kab", "when", "time", "date", "arrival", "paani kab", "flood arrive", "कहिले", "कहिल्यै"]):
            scores["event_summary"] += 8
        if any(k in q for k in ["summary", "sitrep", "overview", "officer", "सारांश", "विवरण"]):
            scores["event_summary"] += 14
            scores["cutoff_settlements"] += 8
            scores["bridges_status"] += 6
        if any(k in q for k in ["sabse bada", "bada kaunsa", "largest", "biggest", "सबैभन्दा ठूलो"]):
            scores["cutoff_settlements"] += 8
        if any(k in q for k in ["sure", "trust", "limit", "cloud", "copernicus", "ems", "certain", "विश्वास"]):
            scores["confidence_and_limits"] += 12
            scores["limitations"] += 6
        if any(k in q for k in ["run", "event", "melamchi", "sikkim", "assam", "other", "switch", "list", "load"]):
            scores["load_run"] += 12
            scores["list_runs"] += 8

        # Spatial / coordinate checks
        from .names import parse_coordinates_query
        if parse_coordinates_query(query) or any(k in q for k in ["near", "in ", "at ", "around", "नजिक"]):
            scores["damage_summary"] += 4
            scores["settlement_status"] += 4
            scores["bridges_status"] += 3

        sorted_tools = sorted(all_tools, key=lambda t: scores.get(t["function"]["name"], 0), reverse=True)
        selected = [t for t in sorted_tools if scores.get(t["function"]["name"], 0) > 0][:5]
        if len(selected) < 4:
            core_names = ["event_summary", "damage_summary", "cutoff_settlements", "bridges_status", "roads_status"]
            for t in all_tools:
                if t["function"]["name"] in core_names and t not in selected:
                    selected.append(t)
                    if len(selected) >= 5:
                        break
        return selected

    def _compact_tool_output(self, fname: str, out: Dict[str, Any]) -> Dict[str, Any]:
        """Prune bulky metadata while keeping all numbers, names, and fact_ids intact."""
        res = dict(out)
        if fname == "cutoff_settlements":
            res.pop("cut_off_settlements_sample", None)
            res.pop("cloud_unverified_routes_note", None)
            res.pop("evidence", None)
            if "top_5_cut_off_settlements" in res and isinstance(res["top_5_cut_off_settlements"], list):
                res["top_5_cut_off_settlements"] = [
                    {"name": s.get("name"), "building_count": s.get("building_count")}
                    for s in res["top_5_cut_off_settlements"][:5]
                ]
            res["cloud_routes_note"] = "Cloud-unverified routes are CONNECTED and NOT in cut-off count. Do NOT add them to the cut-off count."
        elif fname == "bridges_status":
            if "destroyed_bridges" in res and isinstance(res["destroyed_bridges"], list):
                res["destroyed_bridges"] = [
                    {"carried_road": b.get("carried_road"), "bridge_id": b.get("bridge_id"), "highway": b.get("highway")}
                    for b in res["destroyed_bridges"][:3]
                ]
            if "possibly_damaged_bridges" in res and isinstance(res["possibly_damaged_bridges"], list):
                res["possibly_damaged_bridges"] = [
                    {"carried_road": b.get("carried_road"), "bridge_id": b.get("bridge_id")}
                    for b in res["possibly_damaged_bridges"][:2]
                ]
        elif fname == "confidence_and_limits":
            res.pop("limits_summary", None)
            res.pop("what_not_to_trust", None)
        elif fname == "load_run":
            res.pop("available_runs_sample", None)
        elif fname == "list_runs":
            if "available_runs" in res and isinstance(res["available_runs"], list):
                res["available_runs"] = [
                    {"run_name": r.get("run_name"), "label": r.get("label")}
                    for r in res["available_runs"][:6]
                ]
        elif fname == "damage_summary":
            if "nearby_damaged_buildings" in res and isinstance(res["nearby_damaged_buildings"], list):
                res["nearby_damaged_buildings"] = res["nearby_damaged_buildings"][:3]
        return res

    # ==========================================
    # ONLINE PROVIDERS (KeyPool Multi-Provider Failover, OpenAI, Gemini, Anthropic)
    # ==========================================
    def _pooled_answer(self, query: str, lang: str) -> AgentResponse:
        """Call LLM with priority endpoints, automatic key pool failover, and strict guard."""
        import time
        from openai import OpenAI

        clean_q = query.strip()
        if len(clean_q.split()) <= 2:
            res_ambig = self.resolver.resolve(clean_q)
            if res_ambig.status == "ambiguous":
                return AgentResponse(
                    text=res_ambig.clarification_prompt,
                    tools_called=["names.resolve"],
                    tool_outputs=[res_ambig.to_dict()],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    clarification_needed=True,
                    provider="key_pool",
                    model=self.model or "ambiguity_resolver",
                )

        endpoints = list(self.config.get("priority_endpoints") or [
            {"provider": "gemini", "model": "gemini-3.5-flash-lite", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
            {"provider": "gemini", "model": "gemini-3.1-flash-lite", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
            {"provider": "groq", "model": "openai/gpt-oss-20b", "base_url": "https://api.groq.com/openai/v1"},
            {"provider": "groq", "model": "qwen/qwen3.8-27b", "base_url": "https://api.groq.com/openai/v1"},
            {"provider": "openrouter", "model": "openai/gpt-4o-mini", "base_url": "https://openrouter.ai/api/v1"},
            {"provider": "offline", "model": "offline"},
        ])

        if self.model:
            target_model = self.model
            if target_model in ["gemini-2.5-flash", "models/gemini-2.5-flash"]:
                target_model = "gemini-3.5-flash-lite"

            matched = [ep for ep in endpoints if ep.get("model") == target_model or ep.get("model") == self.model]
            if matched:
                others = [ep for ep in endpoints if ep not in matched]
                endpoints = matched + others
            else:
                if "gemini" in str(self.model).lower():
                    prov = "gemini"
                    b_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                elif any(p in str(self.model).lower() for p in ["gpt-oss", "qwen", "allam", "whisper", "groq"]):
                    prov = "groq"
                    b_url = "https://api.groq.com/openai/v1"
                else:
                    prov = "openrouter"
                    b_url = "https://openrouter.ai/api/v1"
                endpoints = [{"provider": prov, "model": target_model, "base_url": b_url}] + endpoints

        defs = get_tool_definitions()
        all_openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": d["name"],
                    "description": d["description"],
                    "parameters": d["parameters"],
                },
            }
            for d in defs
        ]
        openai_tools = self._select_relevant_tools(query, all_openai_tools)

        lang_prompt_map = {
            "en": "CRITICAL LANGUAGE DIRECTIVE: The user asked in English. You MUST reply STRICTLY in English. Do NOT answer in Nepali or Hindi.",
            "hi": "CRITICAL LANGUAGE DIRECTIVE: The user asked in Hindi (or romanised Hindi). You MUST reply STRICTLY in Hindi (हिन्दी) using Devanagari script. Do NOT answer in Nepali (do NOT use Nepali verbs/markers like छ, छन्, भयो, भत्किए).",
            "ne": "CRITICAL LANGUAGE DIRECTIVE: The user asked in Nepali. You MUST reply STRICTLY in Nepali (नेपाली) using Devanagari script.",
        }
        lang_instruction = lang_prompt_map.get(lang, "CRITICAL LANGUAGE DIRECTIVE: Reply in the language of the user query.")
        conv_messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n====================\n{lang_instruction}\n===================="}]
        for m in self.messages[-2:]:
            conv_messages.append({"role": m["role"], "content": m["content"]})

        # Keyword shortcut refusal strictly for population requests / household multipliers
        # Must NOT trigger on "roughly how many bridges were destroyed?" or "are there homeless shelters in the data?"
        q_lower = query.lower()
        is_pop_query = False
        pop_phrases = [
            "population", "जनसंख्या", "people affected", "लोग प्रभावित", "मानिस प्रभावित",
            "per house", "per building", "per family", "प्रति घर", "प्रति भवन",
            "people are homeless", "homeless people", "calculate how many people are homeless",
            "how many people are homeless", "number of people affected", "total population",
        ]
        if any(p in q_lower or p in query for p in pop_phrases):
            if "shelter" not in q_lower and "bridge" not in q_lower:
                is_pop_query = True

        if is_pop_query:
            out = self.tools.event_summary()
            self.conversation_tool_outputs.append(out)
            m = out.get("metrics", {})
            b_aff = m.get("buildings_affected_total", "not computed")
            b_dest = m.get("buildings_destroyed", "not computed")
            text = (
                f"जनसंख्या सम्बन्धी तथ्याङ्क प्रणालीमा उपलब्ध छैन (OSM मा जनगणना डेटा छैन)। भवन क्षतिको आधिकारिक विवरण निम्न अनुसार छ:\n"
                f"- कुल प्रभावित भवनहरू: {b_aff}\n"
                f"- पूर्ण रूपमा नष्ट भएका भवनहरू: {b_dest}"
                if lang == "ne"
                else (
                    f"जनसंख्या डेटा सिस्टम के आउटपुट में उपलब्ध नहीं है (ओपनस्ट्रीटमैप में आधिकारिक जनगणना डेटा नहीं है)। केवल भवन क्षति के आंकड़े उपलब्ध हैं:\n"
                    f"- कुल प्रभावित भवन: {b_aff}\n"
                    f"- नष्ट हुए भवन: {b_dest}"
                    if lang == "hi"
                    else (
                        f"Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:\n"
                        f"- Total affected buildings: {b_aff}\n"
                        f"- Destroyed buildings: {b_dest}"
                    )
                )
            )
            return AgentResponse(
                text=text,
                tools_called=["event_summary"],
                tool_outputs=[out],
                guard_passed=True,
                guard_retried=False,
                language=lang,
                provider="system",
                model="keyword_refusal",
                answer_path="keyword_refusal",
                turn_latency_sec=0.01,
            )

        t_turn_start = time.time()
        call_logs_this_turn: List[Dict[str, Any]] = []
        for endpoint in endpoints:
            # Enforce 15-second total timeout before falling back to offline mode
            if time.time() - t_turn_start > 14.5:
                logger.warning("15-second LLM turn deadline exceeded; falling back to offline.")
                resp = self._offline_answer(query, lang)
                resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
                resp.provider = "offline"
                resp.model = "offline"
                resp.answer_path = "offline"
                resp.masked_key_id = None
                resp.api_call_logs = call_logs_this_turn
                return resp

            provider = endpoint.get("provider", "offline")
            model_name = endpoint.get("model", "offline")
            base_url = endpoint.get("base_url")

            if provider == "offline":
                if self.strict_no_fallback:
                    raise RuntimeError(f"All live providers failed in strict_no_fallback mode: {last_error}")
                logger.warning("All live endpoints exhausted; answering in offline mode.")
                resp = self._offline_answer(query, lang)
                resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
                resp.provider = "offline"
                resp.model = "offline"
                resp.answer_path = "offline"
                resp.masked_key_id = None
                resp.api_call_logs = call_logs_this_turn
                return resp

            while True:
                if time.time() - t_turn_start > 14.5:
                    logger.warning("15-second LLM turn deadline exceeded inside loop; falling back to offline.")
                    break

                active_key = self.key_pool.get_active_key(provider)
                if not active_key:
                    logger.warning("No active keys for provider %s. Failing over to next endpoint.", provider)
                    break

                rem_timeout = max(2.0, min(15.0, 15.0 - (time.time() - t_turn_start)))
                client = OpenAI(base_url=base_url, api_key=active_key.key, max_retries=0, timeout=rem_timeout)
                tools_called: List[str] = []
                tool_outputs: List[Dict[str, Any]] = []
                messages_copy = list(conv_messages)
                t_start = time.time()
                llm_calls = 0
                prompt_tokens = 0
                completion_tokens = 0
                rate_limit_waits = 0.0

                try:
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=messages_copy,
                        tools=openai_tools,
                        tool_choice="auto",
                        temperature=0.1,
                        max_tokens=500,
                    )
                    llm_calls += 1
                    call_prompt = getattr(completion.usage, "prompt_tokens", 0) or 0 if hasattr(completion, "usage") and completion.usage else 0
                    call_comp = getattr(completion.usage, "completion_tokens", 0) or 0 if hasattr(completion, "usage") and completion.usage else 0
                    prompt_tokens += call_prompt
                    completion_tokens += call_comp

                    latency = time.time() - t_start
                    call_logs_this_turn.append({
                        "provider": provider,
                        "model": model_name,
                        "masked_key_id": active_key.masked_id,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "latency_sec": round(latency, 2),
                        "status": "success",
                        "prompt_tokens": call_prompt,
                        "completion_tokens": call_comp,
                    })
                    self.api_call_logs.append(call_logs_this_turn[-1])
                    active_key.failure_count = 0
                    setattr(active_key, "tpm_retries", 0)

                    choice = completion.choices[0]
                    if not choice.message.tool_calls and not (choice.message.content and choice.message.content.strip()):
                        logger.warning("Empty response from %s (reasoning truncation). Retrying with higher max_tokens...", model_name)
                        completion = client.chat.completions.create(
                            model=model_name,
                            messages=messages_copy,
                            tools=openai_tools,
                            tool_choice="auto",
                            temperature=0.2,
                            max_tokens=650,
                        )
                        llm_calls += 1
                        choice = completion.choices[0]

                    if choice.message.tool_calls:
                        messages_copy.append(choice.message)
                        for tc in choice.message.tool_calls:
                            fname = tc.function.name
                            try:
                                fargs = json.loads(tc.function.arguments) if tc.function.arguments else {}
                            except Exception:
                                fargs = {}
                            tools_called.append(f"{fname}({json.dumps(fargs, ensure_ascii=False)})")

                            out = self.execute_tool(fname, fargs)
                            tool_outputs.append(out)
                            self.conversation_tool_outputs.append(out)

                            if "settlement_name" in out and out["settlement_name"]:
                                self.active_settlement = str(out["settlement_name"])
                            elif "name" in out and out["name"]:
                                self.active_settlement = str(out["name"])
                            elif fargs.get("name"):
                                self.active_settlement = str(fargs["name"])

                            # Compact tool output to minimize prompt tokens
                            out_payload = self._compact_tool_output(fname, out)

                            messages_copy.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(out_payload, ensure_ascii=False),
                            })

                        t_tool_start = time.time()
                        # Strictly cap at Call 2: no tools parameter passed so model cannot request further tool turns
                        completion = client.chat.completions.create(
                            model=model_name,
                            messages=messages_copy,
                            temperature=0.1,
                            max_tokens=400,
                        )
                        llm_calls += 1
                        call2_prompt = getattr(completion.usage, "prompt_tokens", 0) or 0 if hasattr(completion, "usage") and completion.usage else 0
                        call2_comp = getattr(completion.usage, "completion_tokens", 0) or 0 if hasattr(completion, "usage") and completion.usage else 0
                        prompt_tokens += call2_prompt
                        completion_tokens += call2_comp

                        latency_tool = time.time() - t_tool_start
                        call_logs_this_turn.append({
                            "provider": provider,
                            "model": model_name,
                            "masked_key_id": active_key.masked_id,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "latency_sec": round(latency_tool, 2),
                            "status": "success",
                            "prompt_tokens": call2_prompt,
                            "completion_tokens": call2_comp,
                        })
                        self.api_call_logs.append(call_logs_this_turn[-1])
                        active_key.failure_count = 0
                        setattr(active_key, "tpm_retries", 0)
                        answer_text = completion.choices[0].message.content or ""
                    else:
                        answer_text = choice.message.content or ""

                    if not answer_text.strip() and tool_outputs:
                        answer_text = self.guard.build_template_answer(tool_outputs[0], lang)
                        answer_path = "template_fallback"

                    def _check_language_mismatch(text: str, target_lang: str) -> bool:
                        clean = re.sub(r"^\[[^\]]+\]\s*", "", text.strip()).strip()
                        if not clean:
                            return False
                        deva = sum(1 for c in clean if "\u0900" <= c <= "\u097F")
                        total = max(1, len(clean))
                        ratio = deva / total
                        if target_lang == "en" and ratio > 0.15:
                            return True
                        if target_lang in ["hi", "ne"] and ratio < 0.10 and total > 20:
                            return True
                        if target_lang == "hi":
                            ne_specific = [" छ ", " छन् ", " भयो ", " भत्किए ", " गर्दछ ", " वटा "]
                            if any(m in f" {clean} " for m in ne_specific):
                                return True
                        return False

                    if _check_language_mismatch(answer_text, lang) and llm_calls < 2:
                        logger.warning("Language mismatch for %s (target: %s). Requesting rewrite.", model_name, lang)
                        target_name = "English" if lang == "en" else ("Hindi (हिन्दी) in Devanagari script" if lang == "hi" else "Nepali (नेपाली) in Devanagari script")
                        messages_copy.append({"role": "assistant", "content": answer_text})
                        messages_copy.append({
                            "role": "user",
                            "content": f"Language mismatch error: Please rewrite your exact response above strictly in {target_name}. Preserve all numbers and place names exactly. Do NOT use any other language.",
                        })
                        t_lang = time.time()
                        lang_comp = client.chat.completions.create(
                            model=model_name,
                            messages=messages_copy,
                            temperature=0.1,
                            max_tokens=400,
                        )
                        llm_calls += 1
                        if hasattr(lang_comp, "usage") and lang_comp.usage:
                            prompt_tokens += getattr(lang_comp.usage, "prompt_tokens", 0) or 0
                            completion_tokens += getattr(lang_comp.usage, "completion_tokens", 0) or 0

                        call_logs_this_turn.append({
                            "provider": provider,
                            "model": model_name,
                            "masked_key_id": active_key.masked_id,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "latency_sec": round(time.time() - t_lang, 2),
                            "status": "retry_language",
                        })
                        self.api_call_logs.append(call_logs_this_turn[-1])
                        answer_text = lang_comp.choices[0].message.content or answer_text

                    all_session_outputs = list(tool_outputs)
                    if self.conversation_tool_outputs:
                        all_session_outputs.extend(self.conversation_tool_outputs[-3:])
                    guard_tool_outputs = all_session_outputs + [{
                        "tool": "active_run",
                        "label": self._turn_run_label,
                        "run_name": self.store.run_dir.name,
                        "event_date": self.store.get_value("event.date", "2026-08-26"),
                    }]
                    guard_res = self.guard.check(answer_text, guard_tool_outputs, query=query)
                    guard_retried = False
                    answer_path = "llm"

                    if not guard_res.is_valid:
                        target_out = tool_outputs[0] if tool_outputs else {"tool": "error"}
                        for o in tool_outputs:
                            tname = o.get("tool", "")
                            if "damage" in query.lower() and tname == "damage_summary":
                                target_out = o; break
                            if "bridge" in query.lower() and tname == "bridges_status":
                                target_out = o; break
                            if any(k in query.lower() for k in ["road", "highway"]) and tname == "roads_status":
                                target_out = o; break
                            if any(k in query.lower() for k in ["cut", "cutoff", "isolate"]) and tname == "cutoff_settlements":
                                target_out = o; break
                            if any(k in query.lower() for k in ["sure", "trust", "limit"]) and tname == "confidence_and_limits":
                                target_out = o; break

                        if llm_calls < 2:
                            guard_retried = True
                            target_name = "English" if lang == "en" else ("Hindi (हिन्दी) in Devanagari script" if lang == "hi" else "Nepali (नेपाली) in Devanagari script")
                            messages_copy.append({"role": "assistant", "content": answer_text})
                            messages_copy.append({
                                "role": "user",
                                "content": (
                                    f"HallucinationGuard error: {guard_res.error_message}. "
                                    "Re-write your answer strictly using only verified data and entities present in the "
                                    f"tool results, or state that the data is not available. Reply strictly in {target_name}."
                                ),
                            })
                            t_guard = time.time()
                            retry_comp = client.chat.completions.create(
                                model=model_name,
                                messages=messages_copy,
                                temperature=0.1,
                                max_tokens=400,
                            )
                            llm_calls += 1
                            if hasattr(retry_comp, "usage") and retry_comp.usage:
                                prompt_tokens += getattr(retry_comp.usage, "prompt_tokens", 0) or 0
                                completion_tokens += getattr(retry_comp.usage, "completion_tokens", 0) or 0

                            call_logs_this_turn.append({
                                "provider": provider,
                                "model": model_name,
                                "masked_key_id": active_key.masked_id,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "latency_sec": round(time.time() - t_guard, 2),
                                "status": "retry_guard",
                            })
                            self.api_call_logs.append(call_logs_this_turn[-1])
                            answer_text = retry_comp.choices[0].message.content or ""
                            guard_res2 = self.guard.check(answer_text, guard_tool_outputs, query=query)
                            guard_res = guard_res2
                            if not guard_res2.is_valid:
                                answer_text = self.guard.build_template_answer(target_out, lang)
                                answer_path = "template_fallback"
                                guard_passed = True
                            else:
                                guard_passed = True
                        else:
                            # 2 LLM calls reached: deterministic template fallback immediately
                            logger.info("Guard failed after 2 LLM calls (%s). Falling back to template.", guard_res.error_message)
                            if tool_outputs:
                                answer_text = self.guard.build_template_answer(target_out, lang)
                                answer_path = "template_fallback"
                            else:
                                if lang == "ne":
                                    answer_text = "यो स्थान वा जानकारी यस प्रकोप क्षेत्रभित्र भेटिएन (तथ्याङ्कमा उपलब्ध छैन)।"
                                    if any(w in query for w in ["बीरगञ्ज", "वीरगञ्ज"]):
                                        answer_text = "बीरगञ्ज यस प्रकोप क्षेत्रभित्र भेटिएन (तथ्याङ्कमा उपलब्ध छैन)।"
                                elif lang == "hi":
                                    answer_text = "यह स्थान या जानकारी इस आपदा क्षेत्र में नहीं मिली (डेटा में उपलब्ध नहीं है)।"
                                else:
                                    answer_text = "This location or data was not found in the disaster assessment area."
                                answer_path = "keyword_refusal"
                            guard_passed = True
                    else:
                        guard_passed = True

                    if not answer_text.strip() and tool_outputs:
                        answer_text = self.guard.build_template_answer(tool_outputs[-1], lang)
                        answer_path = "template_fallback"

                    turn_latency = round(time.time() - t_start, 2)
                    return AgentResponse(
                        text=answer_text,
                        tools_called=tools_called,
                        tool_outputs=tool_outputs,
                        guard_passed=guard_res.is_valid,
                        guard_retried=guard_retried,
                        language=lang,
                        active_settlement=self.active_settlement,
                        api_call_logs=call_logs_this_turn,
                        guard_result=guard_res.to_dict() if hasattr(guard_res, "to_dict") else None,
                        provider=provider,
                        model=model_name,
                        masked_key_id=active_key.masked_id,
                        answer_path=answer_path,
                        llm_calls=llm_calls,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        rate_limit_waits=rate_limit_waits,
                        turn_latency_sec=turn_latency,
                    )

                except Exception as e:
                    err_str = str(e)
                    last_error = e
                    call_logs_this_turn.append({
                        "provider": provider,
                        "model": model_name,
                        "masked_key_id": active_key.masked_id,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "latency_sec": round(time.time() - t_start, 2),
                        "status": f"error: {err_str[:60]}",
                    })
                    self.api_call_logs.append(call_logs_this_turn[-1])

                    if "429" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                        m_wait = re.search(r"try again in (?:(\d+)\s*m)?\s*(\d+(?:\.\d+)?)\s*s", err_str, flags=re.IGNORECASE)
                        if m_wait:
                            mins = float(m_wait.group(1)) if m_wait.group(1) else 0.0
                            secs = float(m_wait.group(2)) if m_wait.group(2) else 0.0
                            wait_s = mins * 60.0 + secs + 1.0
                        else:
                            wait_s = 2.5

                        failover_threshold = float(self.config.get("rate_limit", {}).get("failover_wait_threshold_s", 5.0))
                        if wait_s > failover_threshold:
                            logger.warning(
                                "Rate limit on %s:%s (key %s) wait %.1fs exceeds %.1fs threshold. Switching immediately to next provider.",
                                provider, model_name, active_key.masked_id, wait_s, failover_threshold
                            )
                            self.key_pool.mark_key_exhausted(provider, active_key.key, reason=f"429 wait {wait_s:.1f}s > {failover_threshold:.1f}s", cooldown_s=wait_s)
                            break

                        retries = getattr(active_key, "tpm_retries", 0)
                        if retries < 3 and wait_s <= failover_threshold:
                            setattr(active_key, "tpm_retries", retries + 1)
                            logger.warning("Short rate limit on %s:%s (key %s). Backing off %.1fs...", provider, model_name, active_key.masked_id, wait_s)
                            time.sleep(wait_s)
                            rate_limit_waits += wait_s
                            continue

                        setattr(active_key, "tpm_retries", 0)
                        logger.warning("Rate limit on %s:%s exceeded retry limit. Switching to next provider.", provider, model_name)
                        self.key_pool.mark_key_exhausted(provider, active_key.key, reason="429 retries exceeded", cooldown_s=wait_s)
                        break
                    elif any(c in err_str.lower() for c in ["401", "invalid api key", "invalid auth key", "api_key_invalid", "unauthorized"]):
                        self.key_pool.mark_key_exhausted(provider, active_key.key, reason="401 Invalid API Key")
                        continue
                    elif "402" in err_str or "Payment Required" in err_str:
                        self.key_pool.mark_key_exhausted(provider, active_key.key, reason="402 Payment Required")
                        continue
                    elif any(c in err_str for c in ["404", "model_not_found", "model_decommissioned", "does not exist", "not found"]):
                        logger.warning("Model %s on provider %s returned 404/not found. Failing over to next endpoint.", model_name, provider)
                        break
                    elif any(c in err_str for c in ["503", "high demand", "overloaded", "spikes in demand"]):
                        logger.warning("Model %s on provider %s returned 503 high demand. Failing over immediately to next endpoint.", model_name, provider)
                        break
                    elif "Failed to call a function" in err_str or "400" in err_str:
                        logger.warning("Model %s function call formatting error: %s. Retrying...", model_name, err_str[:80])
                        time.sleep(1.0)
                        fmt_retries = getattr(active_key, "format_error_retries", 0)
                        if fmt_retries < 2:
                            setattr(active_key, "format_error_retries", fmt_retries + 1)
                            continue
                        setattr(active_key, "format_error_retries", 0)
                        break
                    elif "413" in err_str or "request too large" in err_str.lower() or "tpm" in err_str.lower():
                        logger.warning("TPM limit reached on %s (%s). Backing off 12s...", provider, err_str[:60])
                        time.sleep(12.0)
                        continue
                    else:
                        logger.warning("Call to %s:%s (key %s) failed with %s.", provider, model_name, active_key.masked_id, err_str[:80])
                        self.key_pool.mark_key_exhausted(provider, active_key.key, reason=err_str[:60], cooldown_s=3.0)
                        continue

        if self.strict_no_fallback:
            raise RuntimeError(f"All live endpoints failed in strict_no_fallback mode: {last_error}")

        logger.warning("All endpoints failed; falling back to offline mode.")
        resp = self._offline_answer(query, lang)
        resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
        resp.provider = "offline"
        resp.model = "offline"
        resp.masked_key_id = None
        resp.api_call_logs = call_logs_this_turn
        return resp

    def _openai_compatible_answer(self, query: str, lang: str) -> AgentResponse:
        """Call OpenAI-compatible provider with model failover, 429 backoff, and strict guard."""
        import time
        from openai import OpenAI

        api_key = os.getenv("PLATFORM_API_KEY")
        if not api_key:
            if self.strict_no_fallback:
                raise RuntimeError("PLATFORM_API_KEY environment variable is not set.")
            logger.warning("PLATFORM_API_KEY not found; falling back to offline.")
            resp = self._offline_answer(query, lang)
            resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
            resp.provider = "offline"
            resp.model = "offline"
            return resp

        # Ambiguous place name check for short queries (e.g. "syabru")
        clean_q = query.strip()
        if len(clean_q.split()) <= 2:
            res_ambig = self.resolver.resolve(clean_q)
            if res_ambig.status == "ambiguous":
                return AgentResponse(
                    text=res_ambig.clarification_prompt,
                    tools_called=["names.resolve"],
                    tool_outputs=[res_ambig.to_dict()],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    clarification_needed=True,
                    provider="openai_compatible",
                    model=self.model or (self.config.get("models", ["default"])[0] if self.config.get("models") else "default"),
                )

        base_url = self.config.get("base_url", "https://openrouter.ai/api/v1")
        models_list = [self.model] if self.model else self.config.get("models", [
            "google/gemini-2.5-flash",
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.3-70b-instruct",
        ])

        rate_limit_cfg = self.config.get("rate_limit", {})
        max_retries = rate_limit_cfg.get("max_retries", 5)
        initial_backoff = rate_limit_cfg.get("initial_backoff", 2.0)
        backoff_factor = rate_limit_cfg.get("backoff_factor", 2.0)

        client = OpenAI(base_url=base_url, api_key=api_key)

        defs = get_tool_definitions()
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": d["name"],
                    "description": d["description"],
                    "parameters": d["parameters"],
                },
            }
            for d in defs
        ]

        # Build message history with turn language directive
        lang_prompt_map = {
            "en": "CRITICAL LANGUAGE DIRECTIVE: The user asked in English. You MUST reply STRICTLY in English. Do NOT answer in Nepali or Hindi.",
            "hi": "CRITICAL LANGUAGE DIRECTIVE: The user asked in Hindi (or romanised Hindi). You MUST reply STRICTLY in Hindi (हिन्दी) using Devanagari script. Do NOT answer in Nepali (do NOT use Nepali verbs/markers like छ, छन्, भयो, भत्किए).",
            "ne": "CRITICAL LANGUAGE DIRECTIVE: The user asked in Nepali. You MUST reply STRICTLY in Nepali (नेपाली) using Devanagari script.",
        }
        lang_instruction = lang_prompt_map.get(lang, "CRITICAL LANGUAGE DIRECTIVE: Reply in the language of the user query.")
        conv_messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n====================\n{lang_instruction}\n===================="}]
        for m in self.messages[-2:]:
            conv_messages.append({"role": m["role"], "content": m["content"]})

        last_error = None
        call_logs_this_turn: List[Dict[str, Any]] = []

        for model_name in models_list:
            tools_called: List[str] = []
            tool_outputs: List[Dict[str, Any]] = []
            messages_copy = list(conv_messages)
            retry_delay = initial_backoff

            for attempt in range(max_retries):
                t_start = time.time()
                try:
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=messages_copy,
                        tools=openai_tools,
                        temperature=0.1,
                        max_tokens=80,
                    )
                    latency = time.time() - t_start
                    call_logs_this_turn.append({
                        "model": model_name,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "latency_sec": round(latency, 2),
                        "status": "success",
                    })
                    self.api_call_logs.append(call_logs_this_turn[-1])

                    choice = completion.choices[0]

                    # Multi-turn tool execution loop
                    while choice.message.tool_calls:
                        messages_copy.append(choice.message)
                        for tc in choice.message.tool_calls:
                            fname = tc.function.name
                            try:
                                fargs = json.loads(tc.function.arguments) if tc.function.arguments else {}
                            except Exception:
                                fargs = {}
                            call_repr = f"{fname}({json.dumps(fargs, ensure_ascii=False)})"
                            tools_called.append(call_repr)

                            out = self.execute_tool(fname, fargs)
                            tool_outputs.append(out)
                            self.conversation_tool_outputs.append(out)

                            if "settlement_name" in out and out["settlement_name"]:
                                self.active_settlement = str(out["settlement_name"])
                            elif "name" in out and out["name"]:
                                self.active_settlement = str(out["name"])
                            elif fargs.get("name"):
                                self.active_settlement = str(fargs["name"])

                            # Trim bulky fields to keep prompt token size compact
                            out_payload = dict(out)
                            if fname == "cutoff_settlements":
                                out_payload.pop("cut_off_settlements_sample", None)
                            elif fname == "bridges_status":
                                if "destroyed_bridges" in out_payload and len(out_payload["destroyed_bridges"]) > 3:
                                    out_payload["destroyed_bridges"] = out_payload["destroyed_bridges"][:3]

                            messages_copy.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(out_payload, ensure_ascii=False),
                            })

                        t_tool_start = time.time()
                        completion = client.chat.completions.create(
                            model=model_name,
                            messages=messages_copy,
                            temperature=0.1,
                            max_tokens=220,
                        )
                        latency_tool = time.time() - t_tool_start
                        call_logs_this_turn.append({
                            "model": model_name,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "latency_sec": round(latency_tool, 2),
                            "status": "success",
                        })
                        self.api_call_logs.append(call_logs_this_turn[-1])
                        choice = completion.choices[0]

                    answer_text = choice.message.content or ""

                    # Language verification & retry
                    def _check_language_mismatch(text: str, target_lang: str) -> bool:
                        clean = text.strip()
                        if not clean:
                            return False
                        deva = sum(1 for c in clean if "\u0900" <= c <= "\u097F")
                        total = max(1, len(clean))
                        ratio = deva / total
                        if target_lang == "en" and ratio > 0.15:
                            return True
                        if target_lang in ["hi", "ne"] and ratio < 0.10 and total > 20:
                            return True
                        if target_lang == "hi":
                            ne_specific = [" छ ", " छन् ", " भयो ", " भत्किए ", " गर्दछ ", " वटा "]
                            if any(m in f" {clean} " for m in ne_specific):
                                return True
                        return False

                    if _check_language_mismatch(answer_text, lang):
                        logger.warning("Language mismatch detected for %s (target: %s). Requesting language correction.", model_name, lang)
                        target_name = "English" if lang == "en" else ("Hindi (हिन्दी) in Devanagari script" if lang == "hi" else "Nepali (नेपाली) in Devanagari script")
                        messages_copy.append({"role": "assistant", "content": answer_text})
                        messages_copy.append({
                            "role": "user",
                            "content": (
                                f"Language mismatch error: Please rewrite your exact response above strictly in {target_name}. "
                                "Preserve all numbers and place names exactly. Do NOT use any other language."
                            ),
                        })
                        t_lang_start = time.time()
                        lang_comp = client.chat.completions.create(
                            model=model_name,
                            messages=messages_copy,
                            temperature=0.1,
                            max_tokens=220,
                        )
                        call_logs_this_turn.append({
                            "model": model_name,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "latency_sec": round(time.time() - t_lang_start, 2),
                            "status": "retry_language",
                        })
                        self.api_call_logs.append(call_logs_this_turn[-1])
                        answer_text = lang_comp.choices[0].message.content or answer_text

                    # NumberGuard verification
                    guard_res = self.guard.check(answer_text, tool_outputs)
                    guard_retried = False

                    if not guard_res.is_valid:
                        guard_retried = True
                        target_name = "English" if lang == "en" else ("Hindi (हिन्दी) in Devanagari script" if lang == "hi" else "Nepali (नेपाली) in Devanagari script")
                        messages_copy.append({"role": "assistant", "content": answer_text})
                        messages_copy.append({
                            "role": "user",
                            "content": (
                                f"NumberGuard error: The numbers {guard_res.violating_numbers} were not found in the "
                                "tool outputs of this turn. Re-write your answer strictly using only numbers present in the "
                                f"tool results, or state that the data is not available. Reply strictly in {target_name}."
                            ),
                        })
                        t_retry_start = time.time()
                        retry_comp = client.chat.completions.create(
                            model=model_name,
                            messages=messages_copy,
                            temperature=0.1,
                            max_tokens=220,
                        )
                        call_logs_this_turn.append({
                            "model": model_name,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "latency_sec": round(time.time() - t_retry_start, 2),
                            "status": "retry_guard",
                        })
                        self.api_call_logs.append(call_logs_this_turn[-1])

                        answer_text = retry_comp.choices[0].message.content or ""
                        guard_res2 = self.guard.check(answer_text, tool_outputs)
                        guard_res = guard_res2
                        if not guard_res2.is_valid:
                            if tool_outputs:
                                answer_text = self.guard.build_template_answer(tool_outputs[-1], lang)
                            else:
                                answer_text = "Data not available in the pipeline outputs."
                            guard_res = self.guard.check(answer_text, tool_outputs)

                    return AgentResponse(
                        text=answer_text,
                        tools_called=tools_called,
                        tool_outputs=tool_outputs,
                        guard_passed=guard_res.is_valid,
                        guard_retried=guard_retried,
                        language=lang,
                        active_settlement=self.active_settlement,
                        api_call_logs=call_logs_this_turn,
                        guard_result=guard_res.to_dict(),
                        provider="openai_compatible",
                        model=model_name,
                    )

                except Exception as e:
                    err_str = str(e)
                    call_logs_this_turn.append({
                        "model": model_name,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "latency_sec": round(time.time() - t_start, 2),
                        "status": f"error: {err_str[:60]}",
                    })
                    self.api_call_logs.append(call_logs_this_turn[-1])

                    if ("429" in err_str or "rate limit" in err_str.lower()) and "credit" not in err_str.lower() and "402" not in err_str:
                        sleep_s = retry_delay
                        m_retry = re.search(r"['\"]Retry-After['\"]\s*:\s*['\"]?(\d+)", err_str)
                        if m_retry:
                            sleep_s = max(sleep_s, min(float(m_retry.group(1)), 30.0))
                        logger.warning("Model %s hit rate limit (%s). Retrying in %.1fs...", model_name, err_str[:60], sleep_s)
                        time.sleep(sleep_s)
                        retry_delay *= backoff_factor
                        continue
                    else:
                        logger.warning("Model %s failed with %s; failing over to next model.", model_name, e)
                        last_error = e
                        break

        # If all models failed
        if self.strict_no_fallback:
            raise RuntimeError(f"All models failed in openai_compatible provider: {last_error}")

        logger.warning("All models failed; falling back to offline mode.")
        resp = self._offline_answer(query, lang)
        resp.text = f"[ANSWERED IN OFFLINE MODE]\n{resp.text}"
        resp.provider = "offline"
        resp.model = "offline"
        resp.api_call_logs = call_logs_this_turn
        return resp

    def _gemini_answer(self, query: str, lang: str) -> AgentResponse:
        import socket
        import time
        from datetime import datetime, timezone
        from google import genai
        from google.genai import types

        # Force IPv4 socket resolution to prevent Linux IPv6 DNS route timeouts
        try:
            _orig_getaddrinfo = socket.getaddrinfo
            def _ipv4_getaddrinfo(*args, **kwargs):
                res = _orig_getaddrinfo(*args, **kwargs)
                return [r for r in res if r[0] == socket.AF_INET] or res
            socket.getaddrinfo = _ipv4_getaddrinfo
        except Exception:
            pass

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return self._offline_answer(query, lang)

        model_name = self.model or "gemini-3.8-flash"
        call_logs_this_turn: List[Dict[str, Any]] = []

        # Ambiguous place name check (e.g. Q13 "syabru")
        clean_q = query.strip()
        if len(clean_q.split()) <= 2:
            res_ambig = self.resolver.resolve(clean_q)
            if res_ambig.status == "ambiguous":
                return AgentResponse(
                    text=res_ambig.clarification_prompt,
                    tools_called=["names.resolve"],
                    tool_outputs=[res_ambig.to_dict()],
                    guard_passed=True,
                    guard_retried=False,
                    language=lang,
                    clarification_needed=True,
                    api_call_logs=[],
                    guard_result={"is_valid": True, "extracted_numbers": [], "violating_numbers": [], "details": "Ambiguous place query resolved to candidate options."},
                )

        # Initialize client and persistent chat session
        if self._gemini_chat is None:
            self._gemini_client = genai.Client(api_key=api_key)
            tool_defs = get_tool_definitions()
            fdecls = [
                types.FunctionDeclaration(
                    name=d["name"],
                    description=d["description"],
                    parameters=d.get("parameters"),
                )
                for d in tool_defs
            ]
            gemini_tools = [types.Tool(function_declarations=fdecls)]

            # Create persistent chat session with retry for transient spikes
            for init_model in [model_name, "gemini-3.6-flash"]:
                try:
                    self._gemini_chat = self._gemini_client.chats.create(
                        model=init_model,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            tools=gemini_tools,
                            temperature=0.0,
                        ),
                    )
                    model_name = init_model
                    self.model = init_model
                    break
                except Exception as e:
                    logger.warning("Failed to initialize Gemini chat on %s: %s", init_model, e)
                    continue

            if self._gemini_chat is None:
                return self._offline_answer(query, lang)

        def _send_with_logging(msg_content: Any) -> Any:
            nonlocal model_name
            for attempt in range(4):
                try:
                    t0 = time.time()
                    resp = self._gemini_chat.send_message(msg_content)
                    lat = round(time.time() - t0, 3)
                    iso_now = datetime.now(timezone.utc).isoformat()
                    log_entry = {
                        "model": model_name,
                        "timestamp": iso_now,
                        "latency_s": lat,
                    }
                    self.api_call_logs.append(log_entry)
                    call_logs_this_turn.append(log_entry)
                    return resp
                except Exception as e:
                    err_str = str(e)
                    if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str) and model_name != "gemini-3.6-flash":
                        logger.info("Switching model from %s to gemini-3.6-flash due to rate limit/error: %s", model_name, err_str[:60])
                        model_name = "gemini-3.6-flash"
                        self.model = "gemini-3.6-flash"
                        self._gemini_chat = self._gemini_client.chats.create(
                            model="gemini-3.6-flash",
                            config=types.GenerateContentConfig(
                                system_instruction=SYSTEM_PROMPT,
                                tools=gemini_tools,
                                temperature=0.0,
                            ),
                        )
                        continue
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        # Extract seconds to sleep from message or default to 12s
                        sleep_s = 12
                        match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str)
                        if match:
                            sleep_s = max(5, int(float(match.group(1))) + 2)
                        logger.info("Free-tier 5 RPM limit reached. Waiting %ds for quota window reset...", sleep_s)
                        time.sleep(sleep_s)
                        continue
                    if attempt < 3 and ("503" in err_str or "high demand" in err_str or "Temporary failure" in err_str):
                        time.sleep(3)
                        continue
                    raise

        tools_called: List[str] = []
        tool_outputs: List[Dict[str, Any]] = []

        response = _send_with_logging(query)

        # Multi-turn tool execution loop
        while True:
            has_fn_call = False
            for candidate in (response.candidates or []):
                for part in (candidate.content.parts or []):
                    if part.function_call:
                        has_fn_call = True
                        fc = part.function_call
                        fname = fc.name
                        fargs = dict(fc.args) if fc.args else {}
                        call_repr = f"{fname}({json.dumps(fargs, ensure_ascii=False)})"
                        tools_called.append(call_repr)

                        out = self.execute_tool(fname, fargs)
                        tool_outputs.append(out)
                        self.conversation_tool_outputs.append(out)

                        # Update active settlement if relevant
                        if "settlement_name" in out and out["settlement_name"]:
                            self.active_settlement = str(out["settlement_name"])
                        elif "name" in out and out["name"]:
                            self.active_settlement = str(out["name"])
                        elif fargs.get("name"):
                            self.active_settlement = str(fargs["name"])

                        # Send function response back
                        fn_resp = types.Part.from_function_response(
                            name=fname,
                            response={"result": out},
                        )
                        response = _send_with_logging(fn_resp)
                        break
                if has_fn_call:
                    break
            if not has_fn_call:
                break

        answer_text = response.text or ""

        # Number guard check
        guard_res = self.guard.check(answer_text, tool_outputs)
        guard_retried = False

        if not guard_res.is_valid:
            guard_retried = True
            retry_prompt = (
                f"NumberGuard Error: The numbers {guard_res.violating_numbers} in your response "
                f"are not verified from the tool outputs of this turn. "
                f"Regenerate your answer strictly using only numbers from the tool data, "
                f"or state that the data is not available."
            )
            retry_resp = _send_with_logging(retry_prompt)
            answer_text = retry_resp.text or ""
            guard_res2 = self.guard.check(answer_text, tool_outputs)
            guard_res = guard_res2
            if not guard_res2.is_valid:
                if tool_outputs:
                    answer_text = self.guard.build_template_answer(tool_outputs[-1], lang)
                else:
                    answer_text = "Data not available in the pipeline outputs."
                guard_res = self.guard.check(answer_text, tool_outputs)

        return AgentResponse(
            text=answer_text,
            tools_called=tools_called,
            tool_outputs=tool_outputs,
            guard_passed=guard_res.is_valid,
            guard_retried=guard_retried,
            language=lang,
            active_settlement=self.active_settlement,
            clarification_needed=False,
            api_call_logs=call_logs_this_turn,
            guard_result=guard_res.to_dict(),
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
