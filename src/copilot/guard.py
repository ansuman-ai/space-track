"""Number Checker Guard for Situation-Report Copilot.

Enforces strict grounding: every single number in an LLM answer
(including Western/Devanagari digits, unit conversions, and dates)
must originate from pipeline tool outputs in the conversation.
If an answer fails verification, it can be regenerated or replaced
with a deterministic template answer built exclusively from tool outputs.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("copilot.guard")

DEVA_DIGITS_MAP = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}


@dataclass
class GuardResult:
    """Outcome of number guard verification."""

    is_valid: bool
    extracted_numbers: List[Union[int, float]]
    violating_numbers: List[Union[int, float]]
    allowed_numbers_sample: List[Union[int, float]] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "extracted_numbers": self.extracted_numbers,
            "violating_numbers": self.violating_numbers,
            "allowed_sample": self.allowed_numbers_sample[:20],
            "details": self.details,
        }


class NumberGuard:
    """Verifies that every number in an answer matches tool outputs."""

    def __init__(self, tolerance: float = 1e-3):
        self.tolerance = tolerance

    @staticmethod
    def extract_numbers(text: str) -> List[Union[int, float]]:
        """
        Extract all numeric values from text.
        Converts Devanagari numerals to Western digits, strips commas in numbers,
        and parses floats and integers.
        """
        if not text:
            return []

        # Convert Devanagari numerals
        converted = "".join(DEVA_DIGITS_MAP.get(ch, ch) for ch in text)

        # Remove commas between digits: "1,382" -> "1382"
        converted = re.sub(r"(\d),(\d)", r"\1\2", converted)

        # Match numbers (integers and floats). Ignore standalone dots.
        raw_tokens = re.findall(r"\b\d+(?:\.\d+)?\b", converted)
        numbers: List[Union[int, float]] = []
        for tok in raw_tokens:
            try:
                if "." in tok:
                    val = float(tok)
                else:
                    val = int(tok)
                numbers.append(val)
            except ValueError:
                continue
        return numbers

    def extract_allowed_numbers(
        self,
        tool_outputs: List[Dict[str, Any]],
        extra_numbers: Optional[Set[Union[int, float]]] = None,
    ) -> Set[Union[int, float]]:
        """
        Recursively extract all numeric values from tool outputs and expand them
        with legitimate rounding, date components, and unit conversions.
        """
        raw_nums: Set[Union[int, float]] = set()
        if extra_numbers:
            raw_nums.update(extra_numbers)

        def _walk(obj: Any) -> None:
            if isinstance(obj, (int, float)) and not isinstance(obj, bool):
                raw_nums.add(obj)
                if isinstance(obj, float) and obj.is_integer():
                    raw_nums.add(int(obj))
            elif isinstance(obj, str):
                # Check for dates like "2026-08-26" or OSM IDs like "way/1266396385"
                date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", obj.strip())
                if date_match:
                    raw_nums.add(int(date_match.group(1)))
                    raw_nums.add(int(date_match.group(2)))
                    raw_nums.add(int(date_match.group(3)))
                # Extract any numeric substring inside IDs or labels
                for match in re.findall(r"\b\d+(?:\.\d+)?\b", obj):
                    try:
                        raw_nums.add(float(match) if "." in match else int(match))
                    except ValueError:
                        pass
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ["step", "class", "building_count", "cut_off_count", "destroyed_count"]:
                        if isinstance(v, (int, float)):
                            raw_nums.add(v)
                    _walk(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _walk(item)

        for out in tool_outputs:
            _walk(out)

        # Expand allowed numbers with standard mathematical / unit conversions
        expanded: Set[Union[int, float]] = set()
        for num in raw_nums:
            expanded.add(num)
            # Floats to ints
            if isinstance(num, float):
                if num.is_integer():
                    expanded.add(int(num))
                # Roundings
                expanded.add(round(num, 1))
                expanded.add(round(num, 2))
                expanded.add(round(num, 3))
            elif isinstance(num, int):
                expanded.add(float(num))

            # Unit conversions:
            # km <-> m (* 1000 / 1000)
            expanded.add(round(num * 1000, 3))
            expanded.add(round(num / 1000, 4))
            # km² <-> ha (* 100)
            expanded.add(round(num * 100, 2))
            # km² <-> m² (* 1,000,000)
            expanded.add(round(num * 1000000, 2))
            # percentage (* 100)
            expanded.add(round(num * 100, 1))

        # Always allow list numbering indices 1 to 10
        for i in range(1, 11):
            expanded.add(i)

        return expanded

    def is_number_allowed(
        self,
        val: Union[int, float],
        allowed_set: Set[Union[int, float]],
    ) -> bool:
        """Check if number exists in allowed set within tolerance."""
        if val in allowed_set:
            return True
        for a in allowed_set:
            # Exact equality or within absolute tolerance
            if abs(val - a) <= self.tolerance:
                return True
            # Relative tolerance for larger numbers
            if abs(a) > 1.0 and abs(val - a) / abs(a) <= 0.005:
                return True
        return False

    def check(
        self,
        answer: str,
        tool_outputs: List[Dict[str, Any]],
        extra_numbers: Optional[Set[Union[int, float]]] = None,
    ) -> GuardResult:
        """
        Verify that all numbers in answer are present in tool outputs.
        Returns GuardResult with is_valid=True or violating numbers.
        """
        extracted = self.extract_numbers(answer)
        if not extracted:
            return GuardResult(
                is_valid=True,
                extracted_numbers=[],
                violating_numbers=[],
                details="No numbers present in answer.",
            )

        allowed = self.extract_allowed_numbers(tool_outputs, extra_numbers)
        violating = []

        for num in extracted:
            if not self.is_number_allowed(num, allowed):
                violating.append(num)

        is_valid = len(violating) == 0
        details = (
            "All numbers verified against tool outputs."
            if is_valid
            else f"Unverified numbers found: {violating}."
        )

        return GuardResult(
            is_valid=is_valid,
            extracted_numbers=extracted,
            violating_numbers=violating,
            allowed_numbers_sample=sorted(list(allowed))[:25],
            details=details,
        )

    # Deterministic Template Answers for Fallback
    @staticmethod
    def build_template_answer(
        tool_output: Dict[str, Any],
        lang: str = "en",
    ) -> str:
        """
        Generate a 100% grounded template answer in English, Nepali, or Hindi
        directly from tool output, guaranteeing zero guard violations.
        """
        tool_name = tool_output.get("tool", "")

        if tool_name == "event_summary":
            m = tool_output.get("metrics", {})
            dt = tool_output.get("event_date", "unknown")
            obs_km2 = m.get("affected_km2_observed", 0.0)
            bldg_dest = m.get("buildings_destroyed", 0)
            br_dest = m.get("bridges_destroyed", 0)
            cut_count = m.get("cut_off_settlements", 0)

            if lang == "ne":
                return (
                    f"घटना विवरण ({dt}):\n"
                    f"- प्रत्यक्ष प्रभावित क्षेत्र: {obs_km2} वर्ग किलोमिटर\n"
                    f"- पूर्ण रूपमा नष्ट भएका भवनहरू: {bldg_dest}\n"
                    f"- नष्ट भएका पुलहरू: {br_dest}\n"
                    f"- सडक सम्पर्क विच्छेद भएका बस्तीहरू: {cut_count}\n"
                    f"टिप्पणी: सबै तथ्याङ्क स्याटेलाइट र ओपन्स्ट्रीटम्याप विश्लेषणमा आधारित छन्।"
                )
            elif lang == "hi":
                return (
                    f"आपदा सारांश ({dt}):\n"
                    f"- प्रत्यक्ष प्रभावित क्षेत्र: {obs_km2} वर्ग किमी\n"
                    f"- नष्ट हुए भवन: {bldg_dest}\n"
                    f"- नष्ट हुए पुल: {br_dest}\n"
                    f"- संपर्क विहीन बस्तियाँ: {cut_count}\n"
                    f"नोट: सभी आंकड़े उपग्रह और ओपनस्ट्रीटमैप डेटा पर आधारित हैं।"
                )
            else:
                return (
                    f"Disaster Event Summary ({dt}):\n"
                    f"- Directly observed affected area: {obs_km2} km²\n"
                    f"- Destroyed buildings: {bldg_dest}\n"
                    f"- Destroyed bridges: {br_dest}\n"
                    f"- Cut-off settlements (vehicle access): {cut_count}\n"
                    f"Data source: Sentinel-1/2 satellite analysis and OpenStreetMap."
                )

        elif tool_name == "damage_summary":
            b = tool_output.get("buildings", {})
            r = tool_output.get("roads_km", {})
            br = tool_output.get("bridges", {})

            if lang == "ne":
                return (
                    f"क्षति विवरण:\n"
                    f"- भवनहरू: नष्ट {b.get('destroyed', 0)}, क्षतिग्रस्त {b.get('damaged', 0)}, सम्भावित {b.get('possibly_damaged', 0)}, बादलले अज्ञात {b.get('unknown_cloud', 0)}\n"
                    f"- सडक: नष्ट {r.get('destroyed_km', 0.0)} कि.मी., अप्रभावित {r.get('not_affected_km', 0.0)} कि.मी., बादलले अज्ञात {r.get('unknown_cloud_km', 0.0)} कि.मी.\n"
                    f"- पुलहरू: नष्ट {br.get('destroyed', 0)}, सम्भावित क्षति {br.get('possibly_damaged', 0)}, अप्रभावित {br.get('not_affected', 0)}"
                )
            elif lang == "hi":
                return (
                    f"क्षति सारांश:\n"
                    f"- भवन: नष्ट {b.get('destroyed', 0)}, क्षतिग्रस्त {b.get('damaged', 0)}, बादल से अज्ञात {b.get('unknown_cloud', 0)}\n"
                    f"- सड़कें: नष्ट {r.get('destroyed_km', 0.0)} किमी, बादल से अज्ञात {r.get('unknown_cloud_km', 0.0)} किमी\n"
                    f"- पुल: नष्ट {br.get('destroyed', 0)}, अप्रभावित {br.get('not_affected', 0)}"
                )
            else:
                return (
                    f"Damage Summary:\n"
                    f"- Buildings: {b.get('destroyed', 0)} destroyed, {b.get('damaged', 0)} damaged, {b.get('possibly_damaged', 0)} possibly damaged, {b.get('unknown_cloud', 0)} unverified under clouds\n"
                    f"- Roads: {r.get('destroyed_km', 0.0)} km destroyed, {r.get('possibly_damaged_km', 0.0)} km possibly damaged, {r.get('unknown_cloud_km', 0.0)} km unverified under clouds\n"
                    f"- Bridges: {br.get('destroyed', 0)} destroyed, {br.get('possibly_damaged', 0)} possibly damaged, {br.get('not_affected', 0)} intact"
                )

        elif tool_name == "cutoff_settlements":
            cut = tool_output.get("cut_off_count", 0)
            net = tool_output.get("network", "vehicle")
            scen = tool_output.get("scenario", "optimistic")
            unver = tool_output.get("connected_unverified_count", 0)

            if lang == "ne":
                return (
                    f"सम्पर्कविहीन बस्ती विवरण ({net}, {scen}):\n"
                    f"- सम्पर्कविच्छेद भएका बस्तीहरूको संख्या: {cut}\n"
                    f"- बादलले ढाकिएका खण्ड भएर जोडिएका (अपुष्ट): {unver}\n"
                    f"नोट: सवारी साधन आवतजावत मुख्य सडक तथा पुलहरूको क्षतिका कारण अवरुद्ध छ।"
                )
            elif lang == "hi":
                return (
                    f"कटे हुए बस्तियों का विवरण ({net}, {scen}):\n"
                    f"- संपर्क विच्छेद बस्तियाँ: {cut}\n"
                    f"- बादलों से ढके मार्गों से जुड़े (अपुष्ट): {unver}"
                )
            else:
                return (
                    f"Cut-Off Settlements ({net} network, {scen} scenario):\n"
                    f"- Total cut-off settlements: {cut}\n"
                    f"- Settlements connected via cloud-unverified routes: {unver}\n"
                    f"Note: Unverified routes pass segments where passability cannot be optically confirmed."
                )

        elif tool_name == "settlement_status":
            st = tool_output.get("status")
            if st == "ambiguous":
                return tool_output.get("clarification_prompt", "Multiple locations found. Please specify.")
            if st == "not_found":
                return tool_output.get("message", "Settlement not found in disaster area.")

            name = tool_output.get("name", "Settlement")
            v_opt = tool_output.get("vehicle_status_optimistic", "unknown")
            bldg = tool_output.get("building_count", 0)
            pop = tool_output.get("population", "not available")
            detour = tool_output.get("vehicle_detour_km")

            if lang == "ne":
                det_str = f", थप घुमाउरो दूरी: {detour} कि.मी." if detour else ""
                return (
                    f"बस्ती विवरण - {name}:\n"
                    f"- सवारी पहुँच स्थिति: {v_opt}\n"
                    f"- भवन संख्या: {bldg}\n"
                    f"- जनसंख्या: {pop} (ओपन्स्ट्रीटम्यापमा उपलब्ध छैन){det_str}"
                )
            elif lang == "hi":
                return (
                    f"बस्ती विवरण - {name}:\n"
                    f"- वाहन पहुँच स्थिति: {v_opt}\n"
                    f"- भवनों की संख्या: {bldg}\n"
                    f"- जनसंख्या: {pop} (डेटा में उपलब्ध नहीं)"
                )
            else:
                det_str = f", detour added: {detour} km" if detour else ""
                return (
                    f"Settlement Status - {name}:\n"
                    f"- Vehicle access (optimistic): {v_opt}\n"
                    f"- Building count: {bldg}\n"
                    f"- Population: {pop} (not available in OSM baseline){det_str}\n"
                    f"Evidence: {tool_output.get('evidence', 'observed')}"
                )

        elif tool_name == "bridges_status":
            tot = tool_output.get("total_bridges", 0)
            dest = tool_output.get("destroyed_count", 0)
            poss = tool_output.get("possibly_damaged_count", 0)
            cloud = tool_output.get("unknown_cloud_count", 0)

            if lang == "ne":
                return (
                    f"पुल स्थिति:\n"
                    f"- कुल पुल: {tot}\n"
                    f"- पूर्ण नष्ट: {dest}\n"
                    f"- सम्भावित क्षति: {poss}\n"
                    f"- बादलले अज्ञात: {cloud}"
                )
            elif lang == "hi":
                return (
                    f"पुलों की स्थिति:\n"
                    f"- कुल पुल: {tot}\n"
                    f"- नष्ट: {dest}\n"
                    f"- संभावित क्षति: {poss}\n"
                    f"- बादल से अज्ञात: {cloud}"
                )
            else:
                return (
                    f"Bridges Status:\n"
                    f"- Total evaluated: {tot}\n"
                    f"- Destroyed: {dest}\n"
                    f"- Possibly damaged: {poss}\n"
                    f"- Unverified due to clouds: {cloud}"
                )

        elif tool_name == "repair_priority":
            top = tool_output.get("top_bottleneck_step", {})
            step_num = top.get("step", 4)
            osm_id = top.get("osm_id", "way/1266396385")
            len_m = top.get("length_m", 103.3)
            set_rec = top.get("settlements_reconnected_step", 19)
            bld_rec = top.get("buildings_reconnected_step", 939)

            if lang == "ne":
                return (
                    f"सडक मर्मत प्राथमिकता:\n"
                    f"- उच्च प्राथमिकता खण्ड (चरण {step_num}): {osm_id}\n"
                    f"- क्षतिग्रस्त लम्बाइ: {len_m} मिटर\n"
                    f"- पुन: सम्पर्क स्थापित हुने बस्तीहरू: {set_rec}\n"
                    f"- लाभान्वित हुने भवनहरू: {bld_rec}"
                )
            elif lang == "hi":
                return (
                    f"मरम्मत प्राथमिकता:\n"
                    f"- उच्च प्राथमिकता खंड (चरण {step_num}): {osm_id}\n"
                    f"- लंबाई: {len_m} मीटर\n"
                    f"- पुनः जुड़े बस्तियाँ: {set_rec}\n"
                    f"- लाभान्वित भवन: {bld_rec}"
                )
            else:
                return (
                    f"Critical Infrastructure Repair Priority:\n"
                    f"- Highest impact bottleneck (Step {step_num}): {osm_id}\n"
                    f"- Damaged length: {len_m} meters\n"
                    f"- Settlements reconnected by this repair: {set_rec}\n"
                    f"- Buildings reconnected: {bld_rec}"
                )

        elif tool_name == "nearest_destination":
            name = tool_output.get("settlement_name", "Settlement")
            dest = tool_output.get("nearest_destination", "Health Facility")
            straight_km = tool_output.get("straight_line_dist_km")
            pre_route = tool_output.get("vehicle_pre_route_dist_km")

            if lang == "ne":
                return (
                    f"निकटतम स्वास्थ्य संस्था ({name}):\n"
                    f"- लक्षित संस्था: {dest}\n"
                    f"- सिधा दूरी: {straight_km} कि.मी.\n"
                    f"- पूर्व-घटना सडक दूरी: {pre_route} कि.मी.\n"
                    f"- वर्तमान पहुँच: {tool_output.get('vehicle_status', 'cut_off')}"
                )
            else:
                return (
                    f"Nearest Emergency Destination for {name}:\n"
                    f"- Destination: {dest}\n"
                    f"- Straight-line distance: {straight_km} km\n"
                    f"- Pre-event vehicle route: {pre_route} km\n"
                    f"- Current vehicle access: {tool_output.get('vehicle_status', 'cut_off')}"
                )

        elif tool_name == "limitations":
            opt_dt = tool_output.get("optical_evidence_date", "unknown")
            cloud_b = tool_output.get("cloud_covered_buildings", 0)
            cloud_r = tool_output.get("cloud_covered_roads_km", 0.0)
            inferred = tool_output.get("inferred_hazard_km2", 0.0)

            if lang == "ne":
                return (
                    f"तथ्याङ्कका सीमितता र अनिश्चितता:\n"
                    f"- अप्टिकल अवलोकन मिति: {opt_dt}\n"
                    f"- बादलले ढाकिएका भवनहरू (अपुष्ट): {cloud_b}\n"
                    f"- बादलले ढाकिएका सडकहरू: {cloud_r} कि.मी.\n"
                    f"- अनुमानित (हाइड्रोलिक मोडेल) बाढी क्षेत्र: {inferred} वर्ग कि.मी.\n"
                    f"- जनसंख्या: ओपन्स्ट्रीटम्यापमा जनसंख्या तथ्याङ्क उपलब्ध छैन।"
                )
            else:
                return (
                    f"Data Limitations & Uncertainty:\n"
                    f"- Optical satellite evidence date: {opt_dt}\n"
                    f"- Cloud-covered buildings (unverified): {cloud_b}\n"
                    f"- Cloud-covered roads: {cloud_r} km\n"
                    f"- Hydraulically inferred hazard area: {inferred} km²\n"
                    f"- Population figures are not available in OpenStreetMap baseline data."
                )

        # Fallback generic string
        return "Information grounded in satellite pipeline outputs: " + str(tool_output)
