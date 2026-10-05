"""Place name resolution and fuzzy matching module.

Resolves place names across English, Nepali, Hindi, romanised spellings,
typos, and Devanagari <-> Latin transliteration.
Handles ambiguity by returning candidate matches.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# Devanagari Unicode maps
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
    "त": "t", "थ": "th", "द": "d", "dh": "dh", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "w", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "क्ष": "ksh", "त्र": "tr", "ज्ञ": "gy",
}

NEPALI_TOPONYM_AFFIXES = [
    "besi", "bensi", "danda", "daanda", "gaun", "gaon", "bazar", "bazaar",
    "chaur", "tar", "kot", "phedi", "khola", "pani", "thulo", "sano", "pur", "nagar"
]


def is_devanagari(text: str) -> bool:
    """Check if string contains Devanagari Unicode characters."""
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def devanagari_to_latin(text: str) -> str:
    """Phonetically transliterate Devanagari text to Latin."""
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
    """Normalize unicode and strip macrons/accents (e.g. ā -> a, ū -> u)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def indic_phonetic(tok: str) -> str:
    """Fold Indic phonemes: labials, dentals, velars, sibilants, vowels."""
    # Labials: ph, f, bh, p -> b
    tok = tok.replace("ph", "b").replace("bh", "b").replace("f", "b").replace("p", "b")
    # Sibilants: sh -> s
    tok = tok.replace("sh", "s")
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

    # Common English metadata words in settlements
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


GENERIC_STOPWORDS = {"place", "node", "near", "cluster", "unnamed", "id", "area", "village", "at"}


def extract_stems(norm_text: str) -> Set[str]:
    """Extract full tokens and affix-stripped stems from normalized text."""
    stems = set()
    tokens = norm_text.split()
    for tok in tokens:
        if tok in GENERIC_STOPWORDS:
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
    """Check overlap and similarity between stems."""
    best = 0.0
    for qs in query_stems:
        for es in entry_stems:
            if len(qs) < 3 or len(es) < 3:
                continue
            if qs == es:
                best = max(best, 0.95)
            elif qs in es or es in qs:
                shorter = min(len(qs), len(es))
                longer = max(len(qs), len(es))
                if shorter >= 4:
                    best = max(best, 0.85 + 0.10 * (shorter / longer))
            else:
                sim = similarity_ratio(qs, es)
                if sim >= 0.75:
                    best = max(best, sim)
    return best


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
    """

    def __init__(self, settlements: List[Dict[str, Any]]):
        self.entries: List[Dict[str, Any]] = []
        self._build_index(settlements)

    def _build_index(self, settlements: List[Dict[str, Any]]) -> None:
        for s in settlements:
            sid = s.get("settlement_id", "")
            raw_name = s.get("name", "")
            if not raw_name:
                continue

            variants: Set[str] = set()
            variants.add(raw_name)

            # Separate bracketed Devanagari or Latin: "Bahun Danda (बाहुनडाँडा)"
            parts = re.findall(r"([^()]+)", raw_name)
            for p in parts:
                p_clean = p.strip()
                if p_clean:
                    variants.add(p_clean)

            # If "nearest named place: X", extract X
            if "nearest named place:" in raw_name:
                match = re.search(r"nearest named place:\s*([^,)]+)", raw_name)
                if match:
                    variants.add(match.group(1).strip())

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
                "name": raw_name,
                "type": s.get("type", "settlement"),
                "raw_settlement": s,
                "variants": list(variants),
                "norm_keys": list(norm_keys),
                "stems": all_stems,
            })

    def resolve(self, query: str, threshold: float = 0.65) -> NameMatchResult:
        """
        Resolve a user's place query to a settlement.
        Returns single match if clear, candidates if ambiguous, or not_found.
        """
        clean_query = query.strip()
        if not clean_query:
            return NameMatchResult(query=query, status="not_found", clarification_prompt="Please specify a place name.")

        query_norm = phonetic_normalize(clean_query)
        if not query_norm:
            return NameMatchResult(query=query, status="not_found", clarification_prompt="Could not parse place name.")

        query_stems = extract_stems(query_norm)

        scored_entries: List[Tuple[float, Dict[str, Any]]] = []

        for entry in self.entries:
            best_entry_score = 0.0

            # 1. Stem matching
            stem_score = match_stems_score(query_stems, entry["stems"])
            best_entry_score = max(best_entry_score, stem_score)

            # 2. Token match on norm keys
            for nk in entry["norm_keys"]:
                score = token_match_score(query_norm, nk)
                if score > best_entry_score:
                    best_entry_score = score

            # 3. Direct string match on raw variants
            for v in entry["variants"]:
                if clean_query.lower() == v.lower():
                    best_entry_score = max(best_entry_score, 1.0)
                elif clean_query.lower() in v.lower():
                    best_entry_score = max(best_entry_score, 0.88)

            if best_entry_score >= threshold:
                scored_entries.append((best_entry_score, entry))

        # Sort descending by score
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        if not scored_entries:
            return NameMatchResult(
                query=query,
                status="not_found",
                score=0.0,
                clarification_prompt=f"No settlement matching '{query}' was found in the disaster area.",
            )

        top_score, top_entry = scored_entries[0]

        # Filter close contenders within 0.12 of top_score
        contenders = [e for s, e in scored_entries if s >= max(threshold, top_score - 0.12)]

        # Check if query specifically matches a distinct named place
        named_place_nodes = [e for e in contenders if e["type"] == "place_node"]

        # If there's an exact named place node and it clearly beats cluster variants
        if len(named_place_nodes) == 1 and top_score >= 0.82:
            return NameMatchResult(
                query=query,
                status="exact" if top_score >= 0.95 else "fuzzy",
                match=named_place_nodes[0]["raw_settlement"],
                score=top_score,
            )

        # If exactly one contender overall
        if len(contenders) == 1:
            return NameMatchResult(
                query=query,
                status="exact" if top_score >= 0.95 else "fuzzy",
                match=contenders[0]["raw_settlement"],
                score=top_score,
            )

        # Multiple candidates found -> Ambiguous!
        # Return deduplicated candidates for user clarification
        seen_names = set()
        candidate_list = []
        for c in contenders[:5]:
            c_name = c["name"]
            if c_name not in seen_names:
                seen_names.add(c_name)
                candidate_list.append({
                    "settlement_id": c["settlement_id"],
                    "name": c["name"],
                    "building_count": c["raw_settlement"].get("building_count", 0),
                    "vehicle_status": c["raw_settlement"].get("vehicle_status_opt", "unknown"),
                })

        if len(candidate_list) == 1:
            return NameMatchResult(
                query=query,
                status="fuzzy",
                match=contenders[0]["raw_settlement"],
                score=top_score,
            )

        options_text = "; ".join(f"{idx+1}. {c['name']}" for idx, c in enumerate(candidate_list))
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
