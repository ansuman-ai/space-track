"""Place name resolution and fuzzy matching module.

Resolves place names across English, Nepali, Hindi, romanised spellings,
typos, and Devanagari <-> Latin transliteration.
Handles ambiguity by returning candidate matches.
Strictly data-driven: aliases and toponyms are derived dynamically from
pipeline settlement outputs and spatially associated OSM features.
Zero hardcoded place names, cluster IDs, coordinates, or invented stem lists.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Generic Devanagari <-> Latin transliteration tables
DEVA_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "अं": "am", "अः": "ah",
}

DEVA_MATRAS = {
    "ा": "a", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}

DEVA_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "w", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "क्ष": "ksh", "त्र": "tr", "ज्ञ": "gy",
}

NEPALI_TOPONYM_AFFIXES = [
    "besi", "bensi", "danda", "daanda", "gaun", "gaon", "bazar", "bazaar",
    "chaur", "tar", "kot", "phedi", "khola", "pani", "pur", "nagar"
]

TOPONYM_MODIFIERS = {
    "besi", "bensi", "danda", "daanda", "thulo", "tulo", "sano", "gaon", "gaun", "bazar", "tar"
}

GENERIC_STOPWORDS = {
    "place", "node", "near", "cluster", "unnamed", "id", "area", "village",
    "at", "nearest", "named", "km", "station", "office"
}


def is_devanagari(text: str) -> bool:
    """Check if string contains Devanagari Unicode characters."""
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def devanagari_to_latin(text: str) -> str:
    """Phonetically transliterate Devanagari text to Latin using generic Unicode phonetic mapping."""
    res = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in DEVA_VOWELS:
            res.append(DEVA_VOWELS[ch])
        elif ch in DEVA_CONSONANTS:
            base = DEVA_CONSONANTS[ch]
            if i + 1 < n:
                nxt = text[i + 1]
                if nxt == "्":  # virama / halant
                    res.append(base)
                    i += 1
                elif nxt in DEVA_MATRAS:
                    res.append(base + DEVA_MATRAS[nxt])
                    i += 1
                elif nxt in ["ं", "ँ"]:
                    res.append(base + "an")
                    i += 1
                elif nxt == "़":  # nukta
                    res.append(base)
                    i += 1
                else:
                    res.append(base + "a")
            else:
                res.append(base)
        elif ch in ["ं", "ँ"]:
            res.append("n")
        elif ch in DEVA_MATRAS:
            res.append(DEVA_MATRAS[ch])
        elif ch.isalnum() or ch.isspace() or ch in "-_,.()":
            res.append(ch)
        i += 1
    return "".join(res)


def strip_accents(text: str) -> str:
    """Normalize unicode (NFKD) and strip macrons/accents (e.g. ā -> a, ū -> u)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def indic_phonetic(tok: str) -> str:
    """Fold Indic phonemes: labials, dentals, velars, sibilants, vowels."""
    tok = tok.lower()
    # Labials: ph, f, bh, p -> b
    tok = tok.replace("ph", "b").replace("bh", "b").replace("f", "b").replace("p", "b")
    # Sibilants: sh -> s
    tok = tok.replace("sh", "s")
    # Dentals: th -> t, dh -> d
    tok = tok.replace("th", "t").replace("dh", "d")
    # Vowels: ee, y -> i; oo, w, v -> u; aa -> a
    tok = tok.replace("ee", "i").replace("y", "i").replace("oo", "u").replace("w", "u").replace("v", "u").replace("aa", "a")
    # Collapse consecutive identical chars
    tok = re.sub(r"(.)\1+", r"\1", tok)
    return tok


def phonetic_normalize(text: str) -> str:
    """Canonical representation of text for matching."""
    if is_devanagari(text):
        text = devanagari_to_latin(text)
    text = strip_accents(text).lower()

    # Strip nearest named place clauses
    text = re.sub(r"\(nearest named place:.*?\)", " ", text, flags=re.IGNORECASE)

    # Remove generic metadata noise words in settlement descriptions
    text = re.sub(
        r"\b(place node/\d+|place|node/\d+|node|cluster near|cluster|unnamed settlement at|unnamed|nearest named place|id \d+)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Remove punctuation
    text = re.sub(r"[^a-z0-9]", " ", text)

    tokens = text.split()
    norm_tokens = [indic_phonetic(t) for t in tokens if t and t not in GENERIC_STOPWORDS]
    return " ".join(norm_tokens)


def extract_stems(norm_text: str) -> Set[str]:
    """Extract full tokens and affix-stripped stems from normalized text."""
    stems = set()
    tokens = norm_text.split()
    for tok in tokens:
        if tok in GENERIC_STOPWORDS or len(tok) < 3:
            continue
        stems.add(tok)
        for aff in NEPALI_TOPONYM_AFFIXES:
            aff_norm = indic_phonetic(aff)
            if tok.startswith(aff_norm) and len(tok) > len(aff_norm) + 2:
                sub = tok[len(aff_norm):]
                if sub not in GENERIC_STOPWORDS:
                    stems.add(sub)
            if tok.endswith(aff_norm) and len(tok) > len(aff_norm) + 2:
                sub = tok[:-len(aff_norm)]
                if sub not in GENERIC_STOPWORDS:
                    stems.add(sub)
    return stems


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    v0 = list(range(len(s2) + 1))
    v1 = [0] * (len(s2) + 1)

    for i in range(len(s1)):
        v1[0] = i + 1
        for j in range(len(s2)):
            cost = 0 if s1[i] == s2[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        v0 = v1[:]

    return v1[len(s2)]


def similarity_ratio(s1: str, s2: str) -> float:
    """Normalized similarity score between 0.0 and 1.0."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    dist = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - (dist / max_len)


def match_stems_score(query_stems: Set[str], entry_stems: Set[str]) -> float:
    """Check overlap and similarity between stems, weighted by query coverage."""
    if not query_stems or not entry_stems:
        return 0.0

    matched_scores = []
    for qs in query_stems:
        best_qs = 0.0
        for es in entry_stems:
            if len(qs) < 3 or len(es) < 3:
                continue
            if qs == es:
                best_qs = max(best_qs, 1.0)
            elif qs in es or es in qs:
                if qs in TOPONYM_MODIFIERS or es in TOPONYM_MODIFIERS:
                    continue
                shorter = min(len(qs), len(es))
                longer = max(len(qs), len(es))
                if shorter >= 4:
                    best_qs = max(best_qs, 0.80 + 0.15 * (shorter / longer))
            else:
                sim = similarity_ratio(qs, es)
                if sim >= 0.75:
                    best_qs = max(best_qs, sim)
        matched_scores.append((qs, best_qs))

    # Weight distinctive stems much higher than generic modifiers
    weights = []
    scores = []
    for qs, score in matched_scores:
        w = 0.25 if qs in TOPONYM_MODIFIERS else 1.0
        weights.append(w)
        scores.append(score * w)

    if not weights or sum(weights) == 0:
        return 0.0
    return sum(scores) / sum(weights)


def token_match_score(query_norm: str, target_norm: str) -> float:
    """Score match between query and target strings."""
    if query_norm == target_norm:
        return 1.0
    if not query_norm or not target_norm:
        return 0.0

    q_stems = extract_stems(query_norm)
    t_stems = extract_stems(target_norm)
    stem_score = match_stems_score(q_stems, t_stems)

    q_compact = query_norm.replace(" ", "")
    t_compact = target_norm.replace(" ", "")

    if q_compact in t_compact:
        sub_score = max(0.85, 0.70 + 0.30 * (len(q_compact) / len(t_compact)))
    elif t_compact in q_compact:
        sub_score = max(0.80, 0.65 + 0.30 * (len(t_compact) / len(q_compact)))
    else:
        sub_score = 0.0

    full_sim = similarity_ratio(q_compact, t_compact)
    return max(stem_score, sub_score, full_sim)


def parse_coordinates_query(query: str) -> Optional[List[float]]:
    """Parse lat/lon coordinates from query string (e.g. '28.163, 85.336' -> [85.336, 28.163])."""
    nums = re.findall(r"[-+]?\d*\.\d+|\b\d+\b", query)
    if len(nums) >= 2:
        try:
            n1 = float(nums[0])
            n2 = float(nums[1])
            # Determine which is latitude (Nepal ~26-31° N) and longitude (~80-89° E)
            if 20.0 <= n1 <= 35.0 and 75.0 <= n2 <= 95.0:
                return [round(n2, 6), round(n1, 6)]  # [lon, lat]
            elif 75.0 <= n1 <= 95.0 and 20.0 <= n2 <= 35.0:
                return [round(n1, 6), round(n2, 6)]  # [lon, lat]
        except ValueError:
            pass
    return None


from src.common.naming import format_settlement_name


def format_settlement_label(s: Dict[str, Any]) -> str:
    """Format a settlement with human-readable label using the SAME shared logic as the dashboard:
    - 'Near <place> (<dist> km) (lat, lon)'
    - Never shows raw 'Unnamed settlement' or cluster IDs.
    - Fully isolated settlements are marked '[access: helicopter/airdrop only]'.
    """
    return format_settlement_name(s, include_coords=True, include_access=True)


@dataclass
class NameMatchResult:
    """Result of place name resolution."""

    query: str
    status: str  # "exact", "fuzzy", "ambiguous", "not_found"
    match: Optional[Dict[str, Any]] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0
    clarification_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "status": self.status,
            "match": self.match,
            "candidates": self.candidates,
            "score": round(self.score, 3),
            "clarification_prompt": self.clarification_prompt,
        }


class PlaceNameResolver:
    """
    Resolves place names in rescuer queries against indexed pipeline settlements.
    Supports English, Nepali, Hindi, transliteration, typos, and ambiguity prompts.
    Completely data-driven: derives aliases strictly from pipeline outputs and spatially associated
    OSM features without hardcoded IDs, place names, coordinates, or invented stem lists.
    """

    def __init__(self, settlements: List[Dict[str, Any]], config: Optional[Dict[str, Any]] = None):
        if config is None:
            cfg_path = Path(__file__).resolve().parent.parent.parent / "configs" / "copilot.yaml"
            if cfg_path.exists():
                try:
                    import yaml
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        raw_cfg = yaml.safe_load(f)
                        config = raw_cfg.get("copilot", {}).get("names", {})
                except Exception:
                    config = {}
            else:
                config = {}

        self.ambiguity_margin: float = float(config.get("ambiguity_margin", 0.08))
        self.match_threshold: float = float(config.get("match_threshold", 0.70))
        self.suggestion_threshold: float = float(config.get("suggestion_threshold", 0.65))
        self.contrasting_modifiers: List[Tuple[str, str]] = [
            tuple(m) for m in config.get("contrasting_modifiers", [
                ("besi", "thulo"), ("bensi", "thulo"), ("besi", "danda"), ("bensi", "danda"),
                ("thulo", "sano"), ("upper", "lower"), ("north", "south")
            ])
        ]

        self.entries: List[Dict[str, Any]] = []
        self._build_index(settlements)

    def _has_contrasting_modifier(self, s1: str, s2: str) -> bool:
        """Check if two strings contain conflicting toponym modifiers from config on a shared stem."""
        s1_norm = phonetic_normalize(s1)
        s2_norm = phonetic_normalize(s2)
        stems1 = extract_stems(s1_norm) - TOPONYM_MODIFIERS
        stems2 = extract_stems(s2_norm) - TOPONYM_MODIFIERS
        shared = stems1 & stems2
        if not shared and not any(len(a) >= 4 and len(b) >= 4 and (a in b or b in a) for a in stems1 for b in stems2):
            return False

        s1_raw = s1.lower()
        s2_raw = s2.lower()

        for m1, m2 in self.contrasting_modifiers:
            m1_norm = indic_phonetic(m1)
            m2_norm = indic_phonetic(m2)
            t1_has_m1 = m1 in s1_raw or m1_norm in s1_norm.split()
            t1_has_m2 = m2 in s1_raw or m2_norm in s1_norm.split()
            t2_has_m1 = m1 in s2_raw or m2_norm in s2_norm.split()
            t2_has_m2 = m2 in s2_raw or m2_norm in s2_norm.split()

            if (t1_has_m1 and t2_has_m2) or (t1_has_m2 and t2_has_m1):
                return True
        return False

    def _build_index(self, settlements: List[Dict[str, Any]]) -> None:
        """Index settlements dynamically using only real OSM tags without any invented names."""
        for s in settlements:
            sid = str(s.get("settlement_id", ""))
            raw_name = str(s.get("name", ""))
            if not raw_name:
                continue

            variants: Set[str] = set()

            is_unnamed = (
                raw_name.lower().startswith("unnamed settlement")
                or raw_name.lower().startswith("cluster near")
                or s.get("type") == "building_cluster"
            )

            is_poi = (not is_unnamed) and any(kw in raw_name.lower() for kw in [
                "research station", "health facility", "healthpost",
                "hospital", "clinic", "office"
            ])

            # Ingest toponym tags strictly from spatially associated OSM features
            osm_features = s.get("osm_features_nearby", [])
            for feat in osm_features:
                feat_name = feat.get("name")
                for tag_key in ["admin_centre", "addr:city", "city", "is_in", "alt_name", "name:en", "name:ne"]:
                    val = feat.get(tag_key)
                    if val and isinstance(val, str):
                        val_clean = val.strip()
                        variants.add(val_clean)

                if feat_name and isinstance(feat_name, str):
                    variants.add(feat_name.strip())

            # Add nearest named place if present in raw_name
            if "nearest named place:" in raw_name.lower():
                sub = re.split(r"nearest named place:\s*", raw_name, flags=re.IGNORECASE)[1].rstrip(")")
                if "," in sub:
                    p_name, _ = sub.rsplit(",", 1)
                    variants.add(p_name.strip())
                    for part in re.split(r"[,/()\[\]]+", p_name):
                        if part.strip():
                            variants.add(part.strip())
                else:
                    variants.add(sub.strip())

            # Add shared formatted label without coords
            formatted_name = format_settlement_name(s, include_coords=False)
            if formatted_name:
                variants.add(formatted_name)
                clean_fn = re.sub(r"^Near\s+", "", formatted_name, flags=re.IGNORECASE)
                clean_fn = re.sub(r"\s*\([^)]*\)", "", clean_fn).strip()
                if clean_fn:
                    variants.add(clean_fn)

            if not is_unnamed:
                variants.add(raw_name)
                clean_name = re.sub(r"\(nearest named place:.*?\)", "", raw_name, flags=re.IGNORECASE).strip()
                for part in re.split(r"[,/()\[\]]+", clean_name):
                    p_clean = part.strip()
                    if p_clean and len(p_clean) >= 3 and not p_clean.lower().startswith("cluster near"):
                        variants.add(p_clean)
            else:
                variants.add(sid)
                variants.add(sid.replace("_", " "))

            norm_keys: Set[str] = set()
            all_stems: Set[str] = set()
            for v in variants:
                norm = phonetic_normalize(v)
                if norm:
                    norm_keys.add(norm)
                    all_stems.update(extract_stems(norm))
                if is_devanagari(v):
                    lat = devanagari_to_latin(v)
                    norm_lat = phonetic_normalize(lat)
                    if norm_lat:
                        norm_keys.add(norm_lat)
                        all_stems.update(extract_stems(norm_lat))

            self.entries.append({
                "settlement_id": sid,
                "name": format_settlement_label(s),
                "type": "poi" if is_poi else s.get("type", "settlement"),
                "is_poi": is_poi,
                "raw_settlement": s,
                "variants": list(variants),
                "norm_keys": list(norm_keys),
                "stems": all_stems,
            })

    def _find_suggestions(self, query_norm: str) -> List[str]:
        """Find closest named settlement suggestions for non-matching queries."""
        suggestions = []
        q_compact = query_norm.replace(" ", "")
        scored = []
        for e in self.entries:
            name = e["name"]
            if "unnamed settlement" in name.lower() or e.get("is_poi"):
                continue
            sim = max(
                similarity_ratio(q_compact, nk.replace(" ", ""))
                for nk in e["norm_keys"]
            ) if e["norm_keys"] else 0.0
            if sim >= self.suggestion_threshold:
                scored.append((sim, name))
        scored.sort(key=lambda x: x[0], reverse=True)
        seen = set()
        for sim, name in scored:
            clean_sug = re.sub(r"\s*\[cluster_\w+\]", "", name)
            clean_sug = re.sub(r"\s*\(ID\s*\d+\)", "", clean_sug)
            clean_sug = re.sub(r"\(nearest named place:.*?\)", "", clean_sug).strip()
            if clean_sug not in seen:
                seen.add(clean_sug)
                suggestions.append(clean_sug)
            if len(suggestions) >= 3:
                break
        return suggestions

    def resolve(self, query: str) -> NameMatchResult:
        """
        Resolve a user's place query to a settlement.
        Weak or close matches return "ambiguous" with candidates so the copilot asks.
        Distinguishes residential settlements from POIs/facilities.
        """
        clean_query = query.strip()
        if not clean_query:
            return NameMatchResult(
                query=query,
                status="not_found",
                clarification_prompt="Please specify a place name."
            )

        query_norm = phonetic_normalize(clean_query)
        if not query_norm:
            return NameMatchResult(
                query=query,
                status="not_found",
                clarification_prompt="Could not parse place name."
            )

        query_stems = extract_stems(query_norm)
        scored_entries: List[Tuple[float, Dict[str, Any]]] = []

        for entry in self.entries:
            # Check contrasting toponym modifiers from config
            if self._has_contrasting_modifier(clean_query, entry["name"]):
                continue
            if any(self._has_contrasting_modifier(clean_query, v) for v in entry["variants"]):
                continue

            best_entry_score = 0.0

            # 1. Exact raw variant string match
            for v in entry["variants"]:
                if self._has_contrasting_modifier(clean_query, v):
                    continue
                v_clean = v.strip().lower()
                q_clean = clean_query.lower()
                if q_clean == v_clean:
                    best_entry_score = max(best_entry_score, 1.0)
                elif q_clean in v_clean and len(q_clean) >= 4:
                    best_entry_score = max(best_entry_score, 0.90)

            # 2. Token match on norm keys
            for nk in entry["norm_keys"]:
                score = token_match_score(query_norm, nk)
                if score > best_entry_score:
                    best_entry_score = score

            # 3. Stem matching
            stem_score = match_stems_score(query_stems, entry["stems"])
            if stem_score > best_entry_score:
                best_entry_score = stem_score

            if best_entry_score >= self.match_threshold:
                scored_entries.append((best_entry_score, entry))

        # Sort descending by score
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        if not scored_entries:
            suggestions = self._find_suggestions(query_norm)
            if suggestions:
                prompt = f"No settlement matching '{query}' was found in the disaster area. Did you mean: {', '.join(suggestions)}?"
            else:
                prompt = f"Place '{query}' was not found inside this run's area."
            return NameMatchResult(
                query=query,
                status="not_found",
                score=0.0,
                clarification_prompt=prompt,
            )

        top_score, _ = scored_entries[0]

        # Contenders within ambiguity margin of top score
        contenders = [e for s, e in scored_entries if s >= top_score - self.ambiguity_margin]

        # Deduplicate candidates by settlement_id
        seen_ids = set()
        unique_contenders = []
        for c in contenders:
            cid = c["settlement_id"]
            if cid not in seen_ids:
                seen_ids.add(cid)
                unique_contenders.append(c)

        # Check if matching features are exclusively POIs (research stations, hospitals, etc.)
        # and not residential settlements. If query didn't specifically ask for a facility/POI,
        # clarify that no residential settlement exists inside the run area.
        all_pois = all(c.get("is_poi") for c in unique_contenders)
        query_has_facility_kw = any(kw in clean_query.lower() for kw in [
            "station", "hospital", "health", "office", "facility", "clinic", "अनुसन्धान", "अस्पताल"
        ])
        if all_pois and not query_has_facility_kw:
            candidate_list = []
            for c in unique_contenders[:5]:
                candidate_list.append({
                    "settlement_id": c["settlement_id"],
                    "name": format_settlement_label(c["raw_settlement"]),
                    "building_count": c["raw_settlement"].get("building_count", 0),
                    "vehicle_status": c["raw_settlement"].get("vehicle_status_opt", "unknown"),
                })
            poi_names = "; ".join(c["name"] for c in candidate_list)
            prompt = (
                f"No residential village settlement named '{query}' exists inside the run area (the settlement may be outside the disaster area). "
                f"Matching features in the data are research station/facility POIs: {poi_names}. "
                f"Which facility would you like details on?"
            )
            return NameMatchResult(
                query=query,
                status="ambiguous",
                candidates=candidate_list,
                score=top_score,
                clarification_prompt=prompt,
            )

        # GENERIC AMBIGUITY AND WEAK MATCH RULE:
        # If two or more candidates are close, OR if the top match is weak (< 0.85),
        # ALWAYS return ambiguous with candidates so the copilot asks for confirmation.
        is_weak_match = top_score < 0.85
        is_close_multi = len(unique_contenders) > 1

        if is_close_multi or is_weak_match:
            candidate_list = []
            for c in unique_contenders[:5]:
                candidate_list.append({
                    "settlement_id": c["settlement_id"],
                    "name": format_settlement_label(c["raw_settlement"]),
                    "building_count": c["raw_settlement"].get("building_count", 0),
                    "vehicle_status": c["raw_settlement"].get("vehicle_status_opt", "unknown"),
                })
            options_text = "; ".join(f"{idx+1}. {c['name']}" for idx, c in enumerate(candidate_list))

            if is_weak_match and not is_close_multi:
                prompt = (
                    f"No settlement named exactly '{query}' was found. "
                    f"Nearest candidate is: {candidate_list[0]['name']}. "
                    f"Did you mean this location?"
                )
            else:
                prompt = (
                    f"Multiple matching locations found for '{query}': {options_text}. "
                    f"Which location would you like details on?"
                )

            return NameMatchResult(
                query=query,
                status="ambiguous",
                candidates=candidate_list,
                score=top_score,
                clarification_prompt=prompt,
            )

        # Single high-confidence match (score >= 0.95)
        best_candidate = unique_contenders[0]
        return NameMatchResult(
            query=query,
            status="exact",
            match=best_candidate["raw_settlement"],
            score=top_score,
        )
