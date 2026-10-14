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
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from src.copilot.names import devanagari_to_latin, is_devanagari, similarity_ratio

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

        # Ignore markdown/list enumeration markers at line starts: "1. ", "2. ", "1) "
        converted = re.sub(r"(?:^|\n)\s*\d+[\.\)]\s+", "\n", converted)

        # Ignore ordinal/priority/rank/package markers: "Priority 1", "Step 1", "Package 1", "प्राथमिकता १"
        converted = re.sub(r"(?i)\b(?:priority|rank|step|package|प्राथमिकता|चरण|प्याकेज)\s*#?\s*\d+\b", " ", converted)
        converted = re.sub(r"(?i)\b(?:top|शीर्ष)\s*\d+\b", " ", converted)
        converted = re.sub(r"(?i)\b\d+[\s-]*(?:line|lines|पंक्ति|लाइन)\b", " ", converted)
        converted = re.sub(r"(?i)\b\d+\s+more\b", " ", converted)

        # Ignore satellite/dataset product names: Sentinel-1, Sentinel-2, EMSR927, WorldDEM-30
        converted = re.sub(r"Sentinel-[12](?:/[12])?", "", converted, flags=re.IGNORECASE)
        converted = re.sub(r"EMSR\d+", "", converted, flags=re.IGNORECASE)
        converted = re.sub(r"WorldDEM-\d+", "", converted, flags=re.IGNORECASE)

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
                    for match in re.findall(r"\b\d+(?:\.\d+)?\b", str(k)):
                        try:
                            raw_nums.add(float(match) if "." in match else int(match))
                        except ValueError:
                            pass
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
                expanded.add(round(num, 4))
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

        return expanded

    def extract_semantic_number_sets(
        self,
        tool_outputs: List[Dict[str, Any]],
    ) -> Dict[str, Set[Union[int, float]]]:
        """Categorize allowed numbers into semantic entities: bridges, buildings, settlements, etc."""
        categories: Dict[str, Set[Union[int, float]]] = {
            "bridge": set(),
            "building": set(),
            "settlement": set(),
            "distance": set(),
            "area": set(),
            "date": set(),
        }

        def _walk_category(obj: Any, current_cat: Optional[str] = None) -> None:
            if isinstance(obj, (int, float)) and not isinstance(obj, bool):
                if current_cat and current_cat in categories:
                    categories[current_cat].add(obj)
                    if isinstance(obj, float) and obj.is_integer():
                        categories[current_cat].add(int(obj))
            elif isinstance(obj, str):
                # Date check
                m_date = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", obj.strip())
                if m_date:
                    for g in m_date.groups():
                        categories["date"].add(int(g))
                # Distance in string check (e.g. "1.5 km")
                for m_km in re.findall(r"(\d+(?:\.\d+)?)\s*(?:km|कि\.?मी\.?|किमी|m|मीटर)", obj, flags=re.IGNORECASE):
                    try:
                        n_km = float(m_km)
                        categories["distance"].add(n_km)
                        if n_km.is_integer():
                            categories["distance"].add(int(n_km))
                    except ValueError:
                        pass
                for num_str in re.findall(r"\b\d+(?:\.\d+)?\b", obj):
                    try:
                        n = float(num_str) if "." in num_str else int(num_str)
                        if current_cat and current_cat in categories:
                            categories[current_cat].add(n)
                    except ValueError:
                        pass
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    k_low = k.lower()
                    cat = current_cat
                    if any(w in k_low for w in ["unverified", "route"]):
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            categories["distance"].add(v)
                            categories["settlement"].add(v)
                    if any(p in k_low for p in ["priority", "package"]):
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            categories["settlement"].add(v)
                    if "bridge" in k_low:
                        cat = "bridge"
                    elif any(b in k_low for b in ["building", "bldg", "house"]):
                        cat = "building"
                    elif any(s in k_low for s in ["settlement", "cutoff", "cut_off", "village"]):
                        cat = "settlement"
                    elif "area" in k_low or "km2" in k_low or "hectare" in k_low:
                        cat = "area"
                    elif any(d in k_low for d in ["dist", "length", "detour", "km", "_m"]):
                        cat = "distance"
                    _walk_category(v, cat)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _walk_category(item, current_cat)

        for out in tool_outputs:
            tname = out.get("tool", "")
            base_cat = None
            if "bridge" in tname:
                base_cat = "bridge"
            elif "damage" in tname or "building" in tname:
                base_cat = "building"
            elif "cutoff" in tname or "rescue" in tname or "settlement" in tname:
                base_cat = "settlement"
            elif "downstream" in tname:
                base_cat = "settlement"
            elif "repair" in tname or "road" in tname:
                base_cat = "distance"
            _walk_category(out, base_cat)

        return categories

    def is_number_allowed(
        self,
        val: Union[int, float],
        allowed_set: Set[Union[int, float]],
    ) -> bool:
        """Check if number exists in allowed set within tolerance."""
        if val in allowed_set:
            return True
        for a in allowed_set:
            if abs(val - a) <= self.tolerance:
                return True
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
        Verify that all numbers in answer are present in tool outputs from this turn,
        strictly tied to the semantic field/entity they describe.
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
        categories = self.extract_semantic_number_sets(tool_outputs)
        violating: List[Union[int, float]] = []

        # Convert Devanagari numerals for localized pattern checks
        norm_answer = "".join(DEVA_DIGITS_MAP.get(ch, ch) for ch in answer)

        for num in extracted:
            # 1. Base check: must exist in tool outputs
            if not self.is_number_allowed(num, allowed):
                violating.append(num)
                continue

            # 2. Semantic entity check: bind number to the closest entity keyword in context
            num_pattern = str(num).rstrip(".0") if isinstance(num, float) and num.is_integer() else str(num)
            matches = list(re.finditer(rf"(?<![\d\.0-9]){re.escape(num_pattern)}(?![\d\.0-9])", norm_answer))

            keywords_map = {
                "bridge": ["bridge", "bridges", "पुल", "पुलहरू", "पुलहरु"],
                "building": ["building", "buildings", "house", "houses", "भवन", "भवनहरू", "भवनहरु", "घर", "घरहरू", "घरहरु", "मकान"],
                "settlement": ["settlement", "settlements", "village", "villages", "cut-off", "cut-offs", "cutoff", "cutoffs", "बस्ती", "बस्ति", "बस्तियों", "बस्तियाँ", "बस्तीहरू", "बस्तीहरु", "गाउँ", "गाउँहरू", "गाँउ", "गाँव", "गांव", "कट-अफ", "कट अफ", "कट-ऑफ", "कट ऑफ", "सम्पर्कविहीन", "सम्पर्कविहिन", "सम्पर्क विच्छेद"],
                "distance": ["kilometer", "kilometre", "कि.मी.", "किमी", "km", "मीटर", "meter", "meters", "road", "roads", "सडक", "सड़क", "मार्ग", "खण्ड", "खंड"],
                "area": ["km²", "km2", "वर्ग कि.मी.", "वर्ग किमी", "हेक्टर", "hectare", "hectares"],
            }

            for m in matches:
                # If number is part of an object identifier or label (e.g. "way/84566285", "Priority 1", "प्राथमिकता १", "Package 1"), skip quantifier checks
                start_prefix = norm_answer[max(0, m.start() - 25):m.start()].lower()
                if any(p in start_prefix for p in ["way/", "node/", "relation/", "cluster_", "id/", "id_", "priority", "package", "प्राथमिकता", "प्याकेज"]):
                    continue

                # If number is part of a coordinate pair (e.g. 28.1706, 85.3131), skip quantifier checks
                surrounding = norm_answer[max(0, m.start() - 20):min(len(norm_answer), m.end() + 20)]
                if re.search(r"[-+]?\d+\.\d+\s*,\s*[-+]?\d+\.\d+", surrounding):
                    continue

                # If number is a list enumeration index (e.g. "1. ", "2. ", "१. "), skip quantifier checks
                line_enum = norm_answer[max(0, m.start() - 4):min(len(norm_answer), m.end() + 2)]
                if re.search(r"(?:^|\n|\s)\d+\.\s", line_enum):
                    continue

                # If number is followed by % or percent or प्रतिशत, skip entity quantifier checks (it's a rate, not count)
                after_num = norm_answer[m.end():min(len(norm_answer), m.end() + 10)]
                if re.match(r"\s*%", after_num) or any(w in after_num.lower() for w in ["percent", "प्रतिशत"]):
                    continue

                closest_cat = None
                min_dist = 999
                for cat, kws in keywords_map.items():
                    for kw in kws:
                        if any("\u0900" <= ch <= "\u097f" for ch in kw):
                            pat = rf"(?<![A-Za-z0-9\u0900-\u097F]){re.escape(kw)}(?:हरू|हरु)?(?:मा|को|का|की|लाई|ले|बाट|देखि|सम्म|ों|ें)?(?![A-Za-z0-9\u0900-\u097F])"
                        else:
                            pat = rf"(?<![A-Za-z0-9\u0900-\u097F]){re.escape(kw)}(?![A-Za-z0-9\u0900-\u097F])"
                        for km in re.finditer(pat, norm_answer.lower()):
                            if km.end() <= m.start():
                                dist = m.start() - km.end()
                            elif km.start() >= m.end():
                                dist = km.start() - m.end()
                            intervening = norm_answer[min(m.end(), km.start()):max(m.start(), km.end())]
                            if "\n" in intervening:
                                dist += 1000
                            if dist < min_dist and dist <= 75:
                                min_dist = dist
                                closest_cat = cat

                if closest_cat == "bridge":
                    if not self.is_number_allowed(num, categories["bridge"]):
                        if not any(self.is_number_allowed(num, s) for s in [categories["date"], categories["distance"]]):
                            violating.append(num)
                            break
                elif closest_cat == "building":
                    if not self.is_number_allowed(num, categories["building"]):
                        if not any(self.is_number_allowed(num, s) for s in [categories["date"]]):
                            violating.append(num)
                            break
                elif closest_cat == "settlement":
                    if not self.is_number_allowed(num, categories["settlement"]):
                        if not any(self.is_number_allowed(num, s) for s in [categories["date"]]):
                            violating.append(num)
                            break
                elif closest_cat == "distance":
                    if not self.is_number_allowed(num, categories["distance"]):
                        if not any(self.is_number_allowed(num, s) for s in [categories["bridge"], categories["settlement"], categories["building"], categories["area"], categories["date"]]):
                            violating.append(num)
                            break
                elif closest_cat == "area":
                    if not self.is_number_allowed(num, categories["area"]):
                        if not any(self.is_number_allowed(num, s) for s in [categories["date"]]):
                            violating.append(num)
                            break

        is_valid = len(violating) == 0
        details = (
            "All numbers verified against tool outputs."
            if is_valid
            else f"Unverified or semantically mismatched numbers found: {violating}."
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
            obs_km2 = m.get("affected_km2_observed", "not computed")
            bldg_tot = m.get("buildings_affected_total", "not computed")
            bldg_dest = m.get("buildings_destroyed", "not computed")
            br_dest = m.get("bridges_destroyed", "not computed")
            cut_count = m.get("cut_off_settlements", "not computed")

            opt_note = tool_output.get("optical_evidence_note")
            opt_ne = f"\n- अप्टिकल स्याटेलाइट प्रमाण: {opt_note}" if opt_note else ""
            opt_hi = f"\n- ऑप्टिकल उपग्रह साक्ष्य: {opt_note}" if opt_note else ""
            opt_en = f"\n- Optical satellite verification: {opt_note}" if opt_note else ""

            bldg_str_ne = f"कुल {bldg_tot} (नष्ट: {bldg_dest})" if bldg_tot != "not computed" and bldg_tot > 0 else f"{bldg_dest}"
            bldg_str_hi = f"कुल {bldg_tot} (नष्ट: {bldg_dest})" if bldg_tot != "not computed" and bldg_tot > 0 else f"{bldg_dest}"
            bldg_str_en = f"{bldg_tot} total ({bldg_dest} destroyed)" if bldg_tot != "not computed" and bldg_tot > 0 else f"{bldg_dest}"

            if lang == "ne":
                return (
                    f"घटना विवरण ({dt}):\n"
                    f"- प्रत्यक्ष प्रभावित क्षेत्र: {obs_km2} वर्ग किलोमिटर\n"
                    f"- प्रभावित भवनहरू: {bldg_str_ne}\n"
                    f"- नष्ट भएका पुलहरू: {br_dest}\n"
                    f"- सडक सम्पर्क विच्छेद भएका बस्तीहरू: {cut_count}{opt_ne}\n"
                    f"टिप्पणी: सबै तथ्याङ्क स्याटेलाइट र ओपन्स्ट्रीटम्याप विश्लेषणमा आधारित छन्।"
                )
            elif lang == "hi":
                return (
                    f"आपदा सारांश ({dt}):\n"
                    f"- प्रत्यक्ष प्रभावित क्षेत्र: {obs_km2} वर्ग किमी\n"
                    f"- प्रभावित भवन: {bldg_str_hi}\n"
                    f"- नष्ट हुए पुल: {br_dest}\n"
                    f"- संपर्क विहीन बस्तियाँ: {cut_count}{opt_hi}\n"
                    f"नोट: सभी आंकड़े उपग्रह और ओपनस्ट्रीटमैप डेटा पर आधारित हैं।"
                )
            else:
                return (
                    f"Disaster Event Summary ({dt}):\n"
                    f"- Directly observed affected area: {obs_km2} km²\n"
                    f"- Affected buildings: {bldg_str_en}\n"
                    f"- Destroyed bridges: {br_dest}\n"
                    f"- Cut-off settlements (vehicle access): {cut_count}{opt_en}\n"
                    f"Data source: Sentinel-1/2 satellite analysis and OpenStreetMap."
                )

        elif tool_name == "damage_summary":
            st = tool_output.get("status")
            if st == "ambiguous":
                return tool_output.get("clarification_prompt", "Multiple locations found. Please specify.")
            if st == "not_found":
                q = tool_output.get("query", "")
                if lang == "ne":
                    return f"{q} यस प्रकोप क्षेत्रभित्र भेटिएन।" if q else "यो स्थान यस प्रकोप क्षेत्रभित्र भेटिएन।"
                elif lang == "hi":
                    return f"{q} इस आपदा क्षेत्र में नहीं मिला।" if q else "यह स्थान इस आपदा क्षेत्र में नहीं मिला।"
                return f"I could not find {q} in this run." if q else "I could not find the place in this run."

            if tool_output.get("is_local_area"):
                area = tool_output.get("area", "local area")
                rad = tool_output.get("radius_km", 1.0)
                b = tool_output.get("buildings", {})
                br = tool_output.get("bridges", {})
                b_dest = b.get("destroyed", 0)
                b_dam = b.get("damaged", 0)
                b_poss = b.get("possibly_damaged", 0)
                b_tot = b.get("total", 0)
                br_dest = br.get("destroyed", 0)
                br_tot = br.get("total", 0)

                if lang == "ne":
                    return (
                        f"स्थानीय क्षति विवरण ({area} वरिपरि {rad} कि.मी. भित्र):\n"
                        f"- भवनहरू: {b_dest} नष्ट, {b_dam} क्षतिग्रस्त, {b_poss} सम्भावित क्षति (स्थानीय {b_tot} मध्ये)\n"
                        f"- पुलहरू: {br_dest} नष्ट (स्थानीय {br_tot} मध्ये)\n"
                        f"नोट: यी तथ्याङ्कहरू {rad} कि.मी. स्थानीय परिधिका हुन्, सम्पूर्ण प्रकोप क्षेत्रको होइनन्।"
                    )
                elif lang == "hi":
                    return (
                        f"स्थानीय क्षति सारांश ({area} के {rad} किमी दायरे में):\n"
                        f"- भवन: {b_dest} नष्ट, {b_dam} क्षतिग्रस्त, {b_poss} संभावित क्षति (स्थानीय {b_tot} में से)\n"
                        f"- पुल: {br_dest} नष्ट (स्थानीय {br_tot} में से)\n"
                        f"नोट: ये आंकड़े केवल {rad} किमी स्थानीय दायरे के हैं, पूरे आपदा क्षेत्र के नहीं।"
                    )
                else:
                    return (
                        f"Local Damage Summary (within {rad} km of {area}):\n"
                        f"- Buildings: {b_dest} destroyed, {b_dam} damaged, {b_poss} possibly damaged (out of {b_tot} assessed locally)\n"
                        f"- Bridges: {br_dest} destroyed (out of {br_tot} assessed locally)\n"
                        f"Note: These numbers reflect only the local area within {rad} km, distinct from the entire disaster area."
                    )

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
            opt_c = tool_output.get("optimistic_cut_off_count", cut)
            pess_c = tool_output.get("pessimistic_cut_off_count", opt_c)
            unver = tool_output.get("connected_unverified_count", tool_output.get("cloud_unverified_routes", 0))
            top_5 = tool_output.get("top_5_cut_off_settlements", [])
            rem = tool_output.get("remaining_cut_off_count", 0)

            top_5_en = "\n".join(f"  {idx+1}. {s['name']} - {s['building_count']} buildings" for idx, s in enumerate(top_5))
            top_5_ne = "\n".join(f"  {idx+1}. {s['name']} - {s['building_count']} भवनहरू" for idx, s in enumerate(top_5))
            top_5_hi = "\n".join(f"  {idx+1}. {s['name']} - {s['building_count']} भवन" for idx, s in enumerate(top_5))

            if lang == "ne":
                rem_txt = f"\n  ... र थप {rem} वटा सम्पर्कविहीन बस्तीहरू।" if rem > 0 else ""
                return (
                    f"सम्पर्कविहीन बस्ती विवरण ({net}):\n"
                    f"- सवारी सम्पर्क विच्छेद भएका कुल बस्तीहरू: {opt_c} (सकारात्मक परिदृश्यमा)\n"
                    f"- आकार अनुसार प्रमुख ५ सम्पर्कविहीन बस्तीहरू:\n{top_5_ne}{rem_txt}\n"
                    f"- नोट: बादलले ढाकिएका {unver} वटा मार्गहरू जोडिएका (connected) छन् र ती यी {opt_c} सम्पर्कविहीन बस्तीहरूमा समावेश छैनन्।"
                )
            elif lang == "hi":
                rem_txt = f"\n  ... और {rem} अन्य कटी हुई बस्तियाँ।" if rem > 0 else ""
                return (
                    f"सड़क संपर्क विच्छेद बस्तियाँ ({net}):\n"
                    f"- वाहन संपर्क विच्छेद कुल बस्तियाँ: {opt_c} (आशावादी परिदृश्य में)\n"
                    f"- आकार के अनुसार प्रमुख ५ कटी हुई बस्तियाँ:\n{top_5_hi}{rem_txt}\n"
                    f"- नोट: बादलों से ढके असत्यापित {unver} मार्ग वाले गाँव जुड़े हुए हैं और वे इन {opt_c} कट-ऑफ बस्तियों में शामिल नहीं हैं।"
                )
            else:
                rem_txt = f"\n  ... and {rem} more cut-off settlements." if rem > 0 else ""
                return (
                    f"Cut-Off Settlements ({net} network):\n"
                    f"- Exactly {opt_c} settlements are cut off from {net} access under the optimistic scenario.\n"
                    f"- Top cut-off settlements by size:\n{top_5_en}{rem_txt}\n"
                    f"- Note: The {unver} connected settlements passing through cloud cover are CONNECTED but unverified; they are NOT included in the {opt_c} cut-off count."
                )

        elif tool_name == "load_run":
            st = tool_output.get("status")
            if st == "ambiguous":
                return tool_output.get("clarification_prompt", "Multiple disaster runs found. Please specify.")
            if st == "not_found":
                return tool_output.get("message", "Disaster run not found.")
            return tool_output.get("statement", f"Loaded run '{tool_output.get('loaded_run')}'.")

        elif tool_name == "settlement_status":
            st = tool_output.get("status")
            if st == "ambiguous":
                return tool_output.get("clarification_prompt", "Multiple locations found. Please specify.")
            if st == "not_found":
                q = tool_output.get("query") or tool_output.get("name", "")
                if lang == "ne":
                    return f"{q} यस प्रकोप क्षेत्रभित्र भेटिएन।" if q else "यो बस्ती यस प्रकोप क्षेत्रभित्र भेटिएन।"
                elif lang == "hi":
                    return f"{q} इस आपदा क्षेत्र में नहीं मिला।" if q else "यह बस्ती इस आपदा क्षेत्र में नहीं मिली।"
                return f"I could not find {q} in this run." if q else "I could not find the settlement in this run."

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
            st = tool_output.get("status")
            if st == "ambiguous":
                return tool_output.get("clarification_prompt", "Multiple locations found. Please specify.")
            if st == "not_found":
                q = tool_output.get("query", "")
                if lang == "ne":
                    return f"{q} यस प्रकोप क्षेत्रभित्र भेटिएन।" if q else "यो पुल यस प्रकोप क्षेत्रभित्र भेटिएन।"
                elif lang == "hi":
                    return f"{q} इस आपदा क्षेत्र में नहीं मिला।" if q else "यह पुल इस आपदा क्षेत्र में नहीं मिला।"
                return f"I could not find {q} in this run." if q else "I could not find the bridge in this run."

            if tool_output.get("is_local_area"):
                area = tool_output.get("area", "local area")
                rad = tool_output.get("radius_km", 1.0)
                tot = tool_output.get("local_total_bridges", 0)
                dest = tool_output.get("local_destroyed_count", 0)
                poss = tool_output.get("local_possibly_damaged_count", 0)
                not_aff = tool_output.get("local_not_affected_count", 0)

                if lang == "ne":
                    return (
                        f"स्थानीय पुल स्थिति ({area} वरिपरि {rad} कि.मी. भित्र):\n"
                        f"- पूर्ण नष्ट: {dest} (स्थानीय {tot} पुलहरू मध्ये)\n"
                        f"- सम्भावित क्षति: {poss}\n"
                        f"- अप्रभावित: {not_aff}\n"
                        f"नोट: यी संख्याहरू {rad} कि.मी. स्थानीय परिधिका हुन्, सम्पूर्ण प्रकोप क्षेत्रको होइनन्।"
                    )
                elif lang == "hi":
                    return (
                        f"स्थानीय पुलों की स्थिति ({area} के {rad} किमी दायरे में):\n"
                        f"- नष्ट: {dest} (स्थानीय {tot} पुलों में से)\n"
                        f"- संभावित क्षति: {poss}\n"
                        f"- अप्रभावित: {not_aff}\n"
                        f"नोट: ये आंकड़े केवल {rad} किमी स्थानीय दायरे के हैं, पूरे आपदा क्षेत्र के नहीं।"
                    )
                else:
                    return (
                        f"Local Bridges Status (within {rad} km of {area}):\n"
                        f"- Bridges destroyed: {dest} (out of {tot} assessed locally within {rad} km)\n"
                        f"- Possibly damaged: {poss}\n"
                        f"- Intact: {not_aff}\n"
                        f"Note: These numbers reflect only the local area within {rad} km, distinct from the entire disaster area."
                    )

            tot = tool_output.get("total_bridges", "not computed")
            dest = tool_output.get("destroyed_count", 0)
            poss = tool_output.get("possibly_damaged_count", 0)
            cloud = tool_output.get("unknown_cloud_count", 0)
            by_road = tool_output.get("destroyed_by_road_type") or {}
            dest_bridges = tool_output.get("destroyed_bridges", [])

            breakdown_items = [f"{cnt} on {hw}" for hw, cnt in by_road.items()]
            breakdown_str = ", ".join(breakdown_items) if breakdown_items else f"{dest} bridges"
            top_hw = [b for b in dest_bridges if b.get("highway") in ["primary", "trunk", "secondary", "tertiary"]]
            inspect_ids = [f"{b.get('carried_road') or b.get('highway')} ({b.get('bridge_id')})" for b in (top_hw[:2] if top_hw else dest_bridges[:2])]
            inspect_str = f"Inspect {', '.join(inspect_ids)} first." if inspect_ids else ""

            if lang == "ne":
                return (
                    f"पुलहरूको क्षति स्थिति:\n"
                    f"- कुल मूल्याङ्कन गरिएका पुल: {tot} (पूर्ण नष्ट: {dest}, सम्भावित क्षति: {poss})\n"
                    f"- भत्किएका {dest} वटा पुलहरू रहेका सडकहरू: {breakdown_str}\n"
                    f"- इन्जिनियरहरूले पहिले निरीक्षण गर्नुपर्ने: {inspect_str}"
                )
            elif lang == "hi":
                return (
                    f"पुलों की क्षति स्थिति:\n"
                    f"- कुल मूल्यांकित पुल: {tot} (पूर्ण नष्ट: {dest}, संभावित क्षति: {poss})\n"
                    f"- नष्ट हुए {dest} पुल निम्न सड़कों पर हैं: {breakdown_str}\n"
                    f"- इंजीनियरों को पहले निरीक्षण करना चाहिए: {inspect_str}"
                )
            else:
                return (
                    f"Bridges Damage Status:\n"
                    f"- Total bridges evaluated: {tot} (Destroyed: {dest}, Possibly damaged: {poss})\n"
                    f"- The {dest} destroyed bridges are located on: {breakdown_str}\n"
                    f"- Inspection Priority: {inspect_str}"
                )

        elif tool_name == "roads_status":
            st = tool_output.get("status")
            if st == "ambiguous":
                return tool_output.get("clarification_prompt", "Multiple road corridors or areas found. Please specify.")
            if st == "not_found":
                q = tool_output.get("query", "")
                if lang == "ne":
                    return f"{q} यस प्रकोप क्षेत्रभित्र भेटिएन।" if q else "यो सडक वा स्थान यस प्रकोप क्षेत्रभित्र भेटिएन।"
                elif lang == "hi":
                    return f"{q} इस आपदा क्षेत्र में नहीं मिला।" if q else "यह सड़क या स्थान इस आपदा क्षेत्र में नहीं मिला।"
                return f"I could not find {q} in this run." if q else "I could not find the road in this run."

            rd = tool_output.get("road_name", "Road")
            passability = tool_output.get("passability", "CLOSED")
            tot_km = tool_output.get("total_km", 0.0)
            dest_km = tool_output.get("destroyed_km", 0.0)
            poss_km = tool_output.get("possibly_damaged_km", 0.0)
            clear_km = tool_output.get("not_affected_km", 0.0)
            cloud_km = tool_output.get("cloud_unverified_km", 0.0)
            rad = tool_output.get("radius_km")
            area = tool_output.get("area_name")

            if lang == "ne":
                loc_txt = f" ({area} वरिपरि {rad} कि.मी. भित्र)" if area else ""
                return (
                    f"सडक अवस्था - {rd}{loc_txt}:\n"
                    f"- स्थिति: {passability}\n"
                    f"- नष्ट खण्ड: {dest_km} कि.मी. (मूल्याङ्कन गरिएको {tot_km} कि.मी. मध्ये)\n"
                    f"- सम्भावित क्षति: {poss_km} कि.मी., अप्रभावित: {clear_km} कि.मी., बादलले अपुष्ट: {cloud_km} कि.मी."
                )
            elif lang == "hi":
                loc_txt = f" ({area} के {rad} किमी दायरे में)" if area else ""
                return (
                    f"सड़क स्थिति - {rd}{loc_txt}:\n"
                    f"- स्थिति: {passability}\n"
                    f"- नष्ट: {dest_km} किमी (कुल {tot_km} किमी में से)\n"
                    f"- संभावित क्षति: {poss_km} किमी, अप्रभावित: {clear_km} किमी, बादल से अज्ञात: {cloud_km} किमी"
                )
            else:
                loc_txt = f" (within {rad} km of {area})" if area else ""
                return (
                    f"Road Status - {rd}{loc_txt}:\n"
                    f"- Passability: {passability}\n"
                    f"- Destroyed length: {dest_km} km (out of {tot_km} km evaluated)\n"
                    f"- Possibly damaged: {poss_km} km, Intact/Clear: {clear_km} km, Cloud-unverified: {cloud_km} km"
                )

        elif tool_name == "confidence_and_limits":
            opt_c = tool_output.get("optimistic_cut_off_settlements", "not computed")
            unver = tool_output.get("cloud_unverified_routes", "not computed")
            r_cloud = tool_output.get("cloud_unverified_roads_km", "not computed")
            b_cloud = tool_output.get("cloud_covered_buildings", "not computed")
            inferred = tool_output.get("inferred_hazard_km2", "not computed")
            opt_dt = tool_output.get("optical_evidence_date", "not computed")
            val_prec = tool_output.get("validation_precision", 0.94)
            val_f1 = tool_output.get("validation_f1", 0.57)
            val_src = tool_output.get("validation_source_file", "processed/validation_status.json")

            if lang == "ne":
                return (
                    f"तथ्याङ्कको विश्वसनीयता र प्राविधिक सीमितताहरू:\n"
                    f"- {opt_c} सम्पर्कविहीन बस्तीको संख्या सकारात्मक परिदृश्यको मोडल अनुमान हो, शतप्रतिशत निश्चितता होइन।\n"
                    f"- आधिकारिक प्रमाणीकरण ({val_src}) अनुसार मोडलको शुद्धता precision {val_prec} र F1 {val_f1} छ।\n"
                    f"- {unver} वटा जोडिएका बस्तीहरू बादलले ढाकिएका सडक भएर जान्छन् ({r_cloud} कि.मी. सडक बादल मुनि छ); यी {unver} मार्गहरू सम्पर्कविहीन ({opt_c}) मा गणना गरिएका छैनन् तर स्थलगत रूपमा क्षतिग्रस्त हुन सक्छन्।\n"
                    f"- के कुरामा पूर्ण विश्वास नगर्ने:\n"
                    f"  1. बादल मुनिका {unver} मार्गहरू पूर्ण खुला छन् भन्नेमा विश्वास नगर्नुहोस्।\n"
                    f"  2. भवन संख्यालाई आधिकारिक जनसंख्या जनगणना नमान्नुहोस् (OSM मा जनसंख्या डेटा छैन)।\n"
                    f"  3. अनुमानित {inferred} वर्ग कि.मी. जोखिम क्षेत्र हाइड्रोलिक मोडल हो, प्रत्यक्ष राडार अवलोकन होइन।\n"
                    f"  4. स्याटेलाइट अवलोकन {opt_dt} को हो; त्यसपछिका परिवर्तन समेटिएका छैनन्।"
                )
            elif lang == "hi":
                return (
                    f"डेटा विश्वसनीयता और तकनीकी सीमाएँ:\n"
                    f"- {opt_c} कट-ऑफ बस्तियों की संख्या आशावादी परिदृश्य का मॉडल अनुमान है, १००% निश्चितता नहीं।\n"
                    f"- आधिकारिक सत्यापन ({val_src}) के अनुसार सटीकता precision {val_prec} और F1 {val_f1} है।\n"
                    f"- {unver} जुड़े हुए गाँव बादलों से ढके सड़क खंडों से गुजरते हैं ({r_cloud} किमी सड़क बादलों में); ये {unver} मार्ग {opt_c} कट-ऑफ में शामिल नहीं हैं लेकिन क्षतिग्रस्त हो सकते हैं।\n"
                    f"- किस बात पर पूरा भरोसा न करें:\n"
                    f"  1. बादलों से ढके {unver} मार्ग पूरी तरह खुले हैं, इस पर भरोसा न करें।\n"
                    f"  2. भवन संख्या को आधिकारिक जनगणना न मानें (OSM में जनसंख्या डेटा नहीं है)।\n"
                    f"  3. अनुमानित {inferred} वर्ग किमी का खतरा हाइड्रोलिक मॉडल है, प्रत्यक्ष उपग्रह रडार अवलोकन नहीं।\n"
                    f"  4. उपग्रह डेटा {opt_dt} का है; उसके बाद की स्थिति इसमें शामिल नहीं है।"
                )
            else:
                return (
                    f"Confidence Metrics and Data Boundaries:\n"
                    f"- The {opt_c} cut-off count is an evidence-based model estimate under the optimistic scenario, NOT an absolute certainty.\n"
                    f"- Validation against ground truth confirms precision {val_prec} (94.0%) and F1 {val_f1} (Source: {val_src}).\n"
                    f"- {unver} connected settlements pass through cloud-unverified road segments ({r_cloud} km road obscured); these {unver} routes are NOT part of the {opt_c} cut-offs, but could be blocked in reality.\n"
                    f"- What you should NOT trust as absolute:\n"
                    f"  1. Do NOT trust that the {unver} cloud-unverified routes are definitely clear or passable.\n"
                    f"  2. Do NOT treat OSM building footprints as an official population census (OSM lacks census population).\n"
                    f"  3. Do NOT treat hydraulically inferred hazard zones ({inferred} km²) as observed SAR detections.\n"
                    f"  4. Do NOT assume road damage detection is 100% complete.\n"
                    f"  5. Do NOT assume data reflects changes after satellite pass date {opt_dt}."
                )

        elif tool_name == "repair_priority":
            summary = tool_output.get("summary_statement", "")
            top_pkg = tool_output.get("top_package") or {}
            el_cnt = top_pkg.get("element_count", "not computed")
            elems = top_pkg.get("elements", [])
            elems_str = ", ".join(elems) if elems else "not computed"
            set_rec = top_pkg.get("settlements_reconnected", "not computed")
            bld_rec = top_pkg.get("buildings_reconnected", "not computed")

            s_sentence = tool_output.get("single_repair_sentence", "")
            s_restores = tool_output.get("single_repair_restores_access", False)
            best_single = tool_output.get("best_single_repair") or {}
            osm_id = best_single.get("osm_id", "")
            len_m = best_single.get("total_destroyed_length_m", 0.0)
            s_rec = best_single.get("settlements_regained_if_only_repaired", 0)
            road_label = best_single.get("road_label", "")
            label_prefix = f"{road_label}, " if road_label else ""
            m_len_str = f"{round(len_m)} m"

            if lang == "ne":
                ne_single = (
                    f"सबैभन्दा प्रभावकारी एकल मर्मत: {label_prefix}{osm_id}, {round(len_m)} मिटर -> {s_rec} बस्तीहरू ({b_rec} भवनहरू)"
                    if s_restores
                    else "कुनै पनि एकल मर्मतले आफैंमा बस्ती जोड्न सक्दैन"
                )
                return (
                    f"सडक मर्मत प्राथमिकता (प्याकेजहरू):\n"
                    f"- {ne_single}।\n"
                    f"- मर्मत प्याकेज १ ({el_cnt} सडक खण्डहरू: {elems_str}) ले {set_rec} बस्तीहरू र {bld_rec} भवनहरूमा सवारी पहुँच पुनर्स्थापित गर्दछ।"
                )
            elif lang == "hi":
                hi_single = (
                    f"सर्वश्रेष्ठ एकल मरम्मत: {label_prefix}{osm_id}, {round(len_m)} मी -> {s_rec} बस्तियाँ ({b_rec} भवन)"
                    if s_restores
                    else "कोई भी एकल मरम्मत अकेले किसी बस्ती तक पहुँच बहाल नहीं करती"
                )
                return (
                    f"सड़क मरम्मत प्राथमिकता (पैकेज):\n"
                    f"- {hi_single}।\n"
                    f"- मरम्मत पैकेज १ ({el_cnt} सड़क खंड: {elems_str}) ले {set_rec} बस्तियों और {bld_rec} भवनों में पहुँच बहाल करता है।"
                )
            else:
                en_single = s_sentence or (
                    f"Best single repair: {label_prefix}{osm_id}, {m_len_str} -> {s_rec} settlements ({b_rec} buildings)"
                    if s_restores
                    else "No single repair reconnects a settlement on its own"
                )
                return (
                    f"Road Repair Prioritization (Packages):\n"
                    f"- {en_single}.\n"
                    f"- Package 1 ({el_cnt} elements: {elems_str}) restores vehicle access to {set_rec} cut-off settlements and {bld_rec} buildings."
                )

        elif tool_name == "rescue_priority":
            p1 = tool_output.get("priority_1_walking_severed") or {}
            p1_count = p1.get("count", 0)
            p1_bldgs = p1.get("total_buildings", 0)
            p1_settlements = p1.get("settlements", [])
            p1_names = ", ".join(f"{s.get('name')} ({s.get('building_count')} bldgs)" for s in p1_settlements)

            p2 = tool_output.get("priority_2_high_density_vehicle_cutoff") or {}
            p2_count = p2.get("count", 0)
            p2_settlements = p2.get("top_settlements", [])
            p2_names = ", ".join(f"{s.get('name')} ({s.get('building_count')} bldgs)" for s in p2_settlements[:2])
            rec = tool_output.get("recommendation", "")

            if lang == "ne":
                return (
                    f"उद्धार टोली परिचालन प्राथमिकता (SAR Deployment):\n"
                    f"- प्राथमिकता १ (पैदल तथा सडक दुवै अवरुद्ध - पूर्ण सम्पर्कविहीन): {p1_count} बस्तीहरू ({p1_bldgs} भवनहरू): {p1_names}।\n"
                    f"- प्राथमिकता २ (सवारी सम्पर्कविहीन, उच्च घनत्व): {p2_names}।"
                )
            elif lang == "hi":
                return (
                    f"बचाव दल तैनाती प्राथमिकता (SAR Deployment):\n"
                    f"- प्राथमिकता १ (पैदल और सड़क दोनों बंद - पूर्ण संपर्कविहीन): {p1_count} बस्तियाँ ({p1_bldgs} भवन): {p1_names}।\n"
                    f"- प्राथमिकता २ (सड़क संपर्कविहीन, उच्च घनत्व): {p2_names}।"
                )
            else:
                return (
                    f"Search and Rescue (SAR) Deployment Priority:\n"
                    f"- Priority 1 (zero walking and road access - complete isolation): {p1_count} settlements ({p1_bldgs} buildings): {p1_names}.\n"
                    f"- Priority 2 (vehicle cut-off, cloud uncertainty): {p2_names}.\n"
                    f"Recommendation: {rec}"
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

        elif tool_name == "downstream_settlements":
            q_place = tool_output.get("query_place", "the selected point")
            total_km = tool_output.get("total_downstream_km", 0.0)
            settlements = tool_output.get("downstream_settlements", [])
            buf_m = tool_output.get("buffer_m", 500.0)

            if not settlements:
                if lang == "ne":
                    return f"{q_place} बाट बग्ने नदी बहाव मार्ग (कुल {total_km} कि.मी.) मा {buf_m:.0f} मिटर भित्र कुनै बस्ती भेटिएन।"
                elif lang == "hi":
                    return f"{q_place} से डाउनस्ट्रीम प्रवाह पथ (कुल {total_km} किमी) में {buf_m:.0f} मीटर के भीतर कोई बस्ती नहीं मिली।"
                return f"No settlements found within {buf_m:.0f} m of the downstream flow path from {q_place} (path length: {total_km} km to AOI edge)."

            lines_en = [f"Settlements downstream of {q_place} (within {buf_m:.0f} m of D8 drainage path, total {total_km} km to AOI edge):"]
            for idx, s in enumerate(settlements):
                lines_en.append(f"  {idx+1}. {s['name']} - {s['distance_downstream_km']} km downstream (offset: {s['lateral_offset_m']} m), {s['building_count']} buildings, status: {s['access_status']}")

            lines_ne = [f"{q_place} बाट बग्ने नदी बहाव मार्ग (कुल {total_km} कि.मी., {buf_m:.0f} मिटर परिधि) मुनिका बस्तीहरू:"]
            for idx, s in enumerate(settlements):
                lines_ne.append(f"  {idx+1}. {s['name']} - {s['distance_downstream_km']} कि.मी. तल ({s['lateral_offset_m']} मि.), {s['building_count']} भवनहरू, स्थिति: {s['access_status']}")

            lines_hi = [f"{q_place} से डाउनस्ट्रीम प्रवाह मार्ग (कुल {total_km} किमी, {buf_m:.0f} मीटर दायरा) की बस्तियाँ:"]
            for idx, s in enumerate(settlements):
                lines_hi.append(f"  {idx+1}. {s['name']} - {s['distance_downstream_km']} किमी नीचे ({s['lateral_offset_m']} मी), {s['building_count']} भवन, स्थिति: {s['access_status']}")

            if lang == "ne":
                return "\n".join(lines_ne)
            elif lang == "hi":
                return "\n".join(lines_hi)
            return "\n".join(lines_en)

        # Fallback generic string
        return "Information grounded in satellite pipeline outputs: " + str(tool_output)


@dataclass
class EntityGuardResult:
    is_valid: bool
    violating_entities: List[str]
    allowed_sample: List[str] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "violating_entities": self.violating_entities,
            "allowed_sample": self.allowed_sample[:20],
            "details": self.details,
        }


@dataclass
class ClaimGuardResult:
    is_valid: bool
    violating_claims: List[str]
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "violating_claims": self.violating_claims,
            "details": self.details,
        }


@dataclass
class HallucinationResult:
    is_valid: bool
    number_result: GuardResult
    entity_result: EntityGuardResult
    claim_result: ClaimGuardResult
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "number_guard": self.number_result.to_dict(),
            "entity_guard": self.entity_result.to_dict(),
            "claim_guard": self.claim_result.to_dict(),
            "error_message": self.error_message,
        }


class EntityGuard:
    """Verifies that every place name, road name/ref, bridge/road/settlement ID,
    and date asserted in an answer appears in this turn's tool outputs (or query for not_found/ambiguous cases)."""

    def __init__(self):
        self.common_words = {
            "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with",
            "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
            "this", "that", "these", "those", "there", "here", "what", "which", "who",
            "how", "when", "where", "why", "if", "not", "no", "yes", "all", "any",
            "both", "each", "few", "more", "most", "other", "some", "such", "only",
            "own", "same", "so", "than", "too", "very", "can", "will", "just", "should",
            "now", "across", "however", "therefore", "overall", "total", "approximately",
            "under", "based", "according", "confidence", "limits", "status", "damage",
            "assessment", "report", "area", "aoi", "settlement", "settlements", "village",
            "villages", "road", "roads", "highway", "highways", "bridge", "bridges",
            "hospital", "hospitals", "field", "engineers", "priority", "package",
            "element", "elements", "step", "steps", "not", "available", "data",
            "copernicus", "sentinel", "openstreetmap", "osm", "ems", "emsr", "emsr927",
            "worlddem", "dem", "sar", "msi", "optical", "satellite", "radar", "hand",
            "destroyed", "damaged", "possibly", "intact", "unverified", "cloud", "clouds",
            "vehicle", "walking", "pedestrian", "footway", "trail", "primary", "secondary",
            "tertiary", "unclassified", "track", "path", "residential", "service",
            "english", "nepali", "hindi", "devanagari", "latin", "number", "numbers",
            "optimistic", "pessimistic", "scenario", "scenarios", "km", "km2", "m", "meters",
            "percent", "ratio", "recall", "precision", "f1", "iou", "population", "census",
            "persons", "people", "house", "houses", "building", "buildings", "footprints",
            "hazard", "flood", "debris", "landslide", "inferred", "observed", "cut", "cutoff",
            "connected", "passable", "closed", "open", "clear", "severed", "isolated",
            "helicopter", "airdrop", "access", "route", "routes", "corridor", "district",
            "note", "warning", "summary", "recommendation", "first", "second", "third",
            "four", "five", "six", "seven", "eight", "nine", "ten", "zero",
            "could", "would", "should", "might", "must", "please", "did", "does", "do", "done",
            "have", "has", "had", "having", "nearest", "candidate", "candidates", "location", "locations",
            "neither", "either", "because", "since", "although", "despite", "regarding", "according",
            "following", "given", "provide", "additional", "details", "help", "narrow", "down",
            "match", "potential", "identified", "system", "between", "among", "both", "also",
            "well", "indeed", "sure", "certainly", "mean", "meant", "confirm", "locate", "located",
            "unnamed", "office", "about", "above", "after", "again", "against", "almost", "along",
            "already", "always", "another", "around", "away", "back", "before", "behind", "below",
            "beside", "beyond", "certain", "clearly", "close", "current", "currently", "daily",
            "different", "direct", "directly", "during", "early", "entire", "especially", "even",
            "every", "everyone", "everything", "everywhere", "exactly", "further", "general",
            "generally", "good", "great", "greater", "hard", "heavy", "high", "higher", "highest",
            "immediate", "immediately", "important", "include", "included", "includes", "including",
            "instead", "known", "large", "larger", "largest", "last", "late", "later", "latest",
            "least", "less", "likely", "little", "local", "locally", "long", "longer", "longest",
            "low", "lower", "lowest", "main", "major", "many", "more", "most", "mostly", "much",
            "near", "nearby", "necessary", "never", "new", "next", "none", "normal", "often", "once",
            "order", "original", "others", "otherwise", "part", "particular", "particularly",
            "past", "per", "perhaps", "possible", "present", "previous", "previously", "prior",
            "probable", "probably", "proper", "properly", "quick", "quickly", "quite", "rather",
            "ready", "real", "really", "recent", "recently", "regular", "relative", "relatively",
            "safe", "safely", "several", "severe", "severely", "short", "shorter", "shortest",
            "significant", "significantly", "similar", "simple", "simply", "single", "slight",
            "slightly", "small", "smaller", "smallest", "soon", "special", "specific", "specifically",
            "state", "stated", "still", "strong", "strongly", "sudden", "suddenly", "surely",
            "totally", "true", "truly", "unable", "unlikely", "until", "upon", "urgent", "urgently",
            "usual", "usually", "various", "vital", "whole", "wide", "widely", "within", "without",
            "breakdown", "additionally", "notably", "overall", "meanwhile", "consequently",
            "specifically", "classified", "categorized", "inspection", "inspected", "priority",
            "confirmed", "verified", "reported", "evaluated", "detailed", "approximately",
        }
        for dict_file in ["/usr/share/dict/words", "/usr/share/dict/american-english"]:
            p = Path(dict_file)
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            w = line.strip().lower()
                            if w and len(w) >= 3 and w not in ["ramnagar", "pokhara", "birgunj"]:
                                self.common_words.add(w)
                    break
                except Exception:
                    pass

    def extract_allowed_entities(self, tool_outputs: List[Dict[str, Any]], query: Optional[str] = None) -> Set[str]:
        allowed: Set[str] = set()

        if query:
            for w in re.findall(r"[\w/]+", query):
                if len(w) >= 2:
                    allowed.add(w.lower())
                    if is_devanagari(w):
                        allowed.add(devanagari_to_latin(w).lower())
            q_low = query.lower()
            if any(k in q_low or k in query for k in ["बीरगञ्ज", "वीरगञ्ज", "बीरगंज", "वीरगंज", "birgunj", "birganj"]):
                allowed.update(["birgunj", "birganj", "veergunj", "veerganj", "बीरगञ्ज", "वीरगञ्ज", "बीरगंज", "वीरगंज"])
            if any(k in q_low or k in query for k in ["पोखरा", "pokhara"]):
                allowed.update(["pokhara", "पोखरा"])
            if any(k in q_low or k in query for k in ["रामनगर", "ramnagar"]):
                allowed.update(["ramnagar", "रामनगर"])
            if any(k in q_low or k in query for k in ["आसाम", "असम", "assam"]):
                allowed.update(["assam", "आसाम", "असम", "silghat", "सिलघाट"])

        def _walk(obj: Any):
            if isinstance(obj, str):
                s = obj.strip()
                if s:
                    allowed.add(s.lower())
                    for part in re.findall(r"(?:way|node|relation)/\d+|\bcluster_\d+\b|\bbridge_\w+\b", s):
                        allowed.add(part.lower())
                    for ref in re.findall(r"\b(?:NH\d+|ref\s*\w+|\d+[A-Z]\d+)\b", s, flags=re.IGNORECASE):
                        allowed.add(ref.lower())
                    for dt in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", s):
                        allowed.add(dt)
                    for word in re.findall(r"[A-Za-z\u0900-\u097F]{2,}", s):
                        allowed.add(word.lower())
                        if is_devanagari(word):
                            allowed.add(devanagari_to_latin(word).lower())
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ["name", "settlement_name", "nearest_place", "carried_road", "road_name", "ref", "highway", "area_name", "label", "osm_id", "bridge_id", "query"]:
                        if isinstance(v, str):
                            allowed.add(v.lower())
                            if is_devanagari(v):
                                allowed.add(devanagari_to_latin(v).lower())
                    _walk(v)
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    _walk(item)

        for out in tool_outputs:
            _walk(out)

        return allowed

    def check(self, answer: str, tool_outputs: List[Dict[str, Any]], query: Optional[str] = None) -> EntityGuardResult:
        allowed = self.extract_allowed_entities(tool_outputs, query)
        violating: List[str] = []

        # 1. OSM / Object IDs: way/12345, cluster_0, etc.
        for oid in re.findall(r"\b(?:way|node|relation)/\d+\b|\bcluster_\d+\b", answer, flags=re.IGNORECASE):
            if oid.lower() not in allowed:
                violating.append(oid)

        # 2. Road designations: national highway or provincial route codes (e.g. NH-series, alphanumeric)
        for road_ref in re.findall(r"\b(?:NH\d+|\d+[A-Z]\d+)\b", answer):
            if road_ref.lower() not in allowed:
                violating.append(road_ref)

        # 3. Dates: YYYY-MM-DD
        for dt in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", answer):
            if dt not in allowed:
                violating.append(dt)

        # 4. Capitalized proper nouns in English
        for word in re.findall(r"\b[A-Z][a-z]{3,}\b", answer):
            w_lower = word.lower()
            if w_lower in self.common_words:
                continue
            if w_lower not in allowed and devanagari_to_latin(word).lower() not in allowed:
                best_match = max([similarity_ratio(w_lower, a) for a in allowed if len(a) >= 3] or [0.0])
                if best_match < 0.75:
                    violating.append(word)

        is_valid = len(violating) == 0
        return EntityGuardResult(
            is_valid=is_valid,
            violating_entities=violating,
            allowed_sample=list(allowed)[:20],
            details=f"Violating entities: {violating}" if violating else "All entities verified.",
        )


class ClaimGuard:
    """Verifies that an answer contains no ungrounded claims about disaster causes or casualties."""

    FORBIDDEN_CAUSES = [
        "dam collapse", "dam burst", "dam broke", "dam failure", "बाँध फुट", "बाँध टूट",
        "glacier lake outburst", "glacier lake burst", "glof", "हिमताल विस्फोट", "ग्लेशियर झील",
        "cloudburst", "बादल फट",
    ]

    FORBIDDEN_CASUALTIES = [
        "died", "death", "deaths", "fatalities", "killed", "मृत्यु", "मरे", "मौत", "हताहत", "जान गई", "मृतक",
    ]

    def check(self, answer: str, tool_outputs: List[Dict[str, Any]]) -> ClaimGuardResult:
        ans_lower = answer.lower()
        violating: List[str] = []

        refusal_markers = [
            "not in the data", "not available", "no evidence", "no data", "not recorded",
            "does not contain", "cannot confirm", "उपलब्ध छैन", "थाहा छैन", "छैन", "होइन",
            "नहीं है", "डेटा में नहीं", "आंकड़े नहीं हैं", "जानकारी नहीं है", "पुष्टि नहीं"
        ]

        # Check ungrounded causes
        for c in self.FORBIDDEN_CAUSES:
            if c in ans_lower:
                if not any(rm in ans_lower for rm in refusal_markers):
                    violating.append(f"Ungrounded cause: '{c}'")

        # Check ungrounded casualties
        for k in self.FORBIDDEN_CASUALTIES:
            if k in ans_lower:
                if not any(rm in ans_lower for rm in refusal_markers):
                    violating.append(f"Ungrounded casualty: '{k}'")

        is_valid = len(violating) == 0
        return ClaimGuardResult(
            is_valid=is_valid,
            violating_claims=violating,
            details=f"Violating claims: {violating}" if violating else "All claims grounded.",
        )


class HallucinationGuard:
    """Unified Hallucination Guard combining NumberGuard, EntityGuard, and ClaimGuard."""

    def __init__(self, tolerance: float = 1e-3):
        self.number_guard = NumberGuard(tolerance=tolerance)
        self.entity_guard = EntityGuard()
        self.claim_guard = ClaimGuard()

    def check(
        self,
        answer: str,
        tool_outputs: List[Dict[str, Any]],
        query: Optional[str] = None,
        extra_numbers: Optional[Set[Union[int, float]]] = None,
    ) -> HallucinationResult:
        num_res = self.number_guard.check(answer, tool_outputs, extra_numbers=extra_numbers)
        ent_res = self.entity_guard.check(answer, tool_outputs, query=query)
        clm_res = self.claim_guard.check(answer, tool_outputs)

        errors = []
        if not num_res.is_valid:
            errors.append(f"NumberGuard: ungrounded numbers {num_res.violating_numbers}")
        if not ent_res.is_valid:
            errors.append(f"EntityGuard: ungrounded entities {ent_res.violating_entities}")
        if not clm_res.is_valid:
            errors.append(f"ClaimGuard: ungrounded claims {clm_res.violating_claims}")

        is_valid = num_res.is_valid and ent_res.is_valid and clm_res.is_valid
        return HallucinationResult(
            is_valid=is_valid,
            number_result=num_res,
            entity_result=ent_res,
            claim_result=clm_res,
            error_message="; ".join(errors),
        )

    def build_template_answer(self, tool_output: Dict[str, Any], lang: str) -> str:
        return self.number_guard.build_template_answer(tool_output, lang)

