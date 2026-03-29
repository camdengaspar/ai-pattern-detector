import re
import unicodedata

# ---------------------------------------------------------------------------
# Location helper
# ---------------------------------------------------------------------------

def _build_location_index(text):
    """
    Returns a list of (para_start, para_end, sent_starts) tuples so that
    a character offset can be mapped to (paragraph_number, sentence_number).
    paragraph_number and sentence_number are 1-based.
    """
    index = []
    paragraphs = re.split(r'\n\n+', text)
    cursor = 0
    for para in paragraphs:
        para_start = cursor
        para_end = cursor + len(para)
        # Split into sentences on .  !  ?  — keep approximate positions
        sent_offsets = []
        for m in re.finditer(r'[^.!?]*[.!?]?', para):
            s = m.group().strip()
            if s:
                sent_offsets.append(para_start + m.start())
        if not sent_offsets:
            sent_offsets = [para_start]
        index.append((para_start, para_end, sent_offsets))
        cursor += len(para) + 2  # account for \n\n separator
    return index


def _offset_to_location(offset, index):
    for para_idx, (p_start, p_end, sent_starts) in enumerate(index):
        if p_start <= offset <= p_end:
            sent_num = 1
            for s_idx, s_start in enumerate(sent_starts):
                if offset >= s_start:
                    sent_num = s_idx + 1
            return f"Paragraph {para_idx + 1}, Sentence {sent_num}"
    return "End of document"


def _make_context(text, start, end, window=80):
    """Return a short excerpt around the match."""
    ctx_start = max(0, start - window // 2)
    ctx_end = min(len(text), end + window // 2)
    prefix = "…" if ctx_start > 0 else ""
    suffix = "…" if ctx_end < len(text) else ""
    return prefix + text[ctx_start:ctx_end].strip() + suffix


def _finding(pattern_type, category, location, matched_text, context):
    return {
        "pattern_type": pattern_type,
        "category": category,
        "location": location,
        "matched_text": matched_text,
        "context": context,
    }


# ---------------------------------------------------------------------------
# Pattern 1 — AI Vocabulary Density
# ---------------------------------------------------------------------------

AI_VOCAB = {
    # Core / cross-era
    "bolstered", "crucial", "emphasizing", "enduring", "enhance", "fostering",
    "highlighting", "pivotal", "showcasing", "underscore", "underscores",
    "underscored", "vibrant",
    # GPT-4 era
    "additionally", "boasts", "delve", "delves", "delved", "garner", "garnered",
    "intricate", "intricacies", "interplay", "meticulous", "meticulously",
    "tapestry", "testament", "valuable",
    # Shared descriptors
    "align", "aligns", "landscape", "nuanced", "multifaceted",
}


def detect_ai_vocab(text, index):
    findings = []
    for m in re.finditer(r'\b\w+\b', text):
        word = m.group().lower()
        if word in AI_VOCAB:
            loc = _offset_to_location(m.start(), index)
            findings.append(_finding(
                "AI Vocabulary Density",
                "Language & Grammar",
                loc,
                m.group(),
                _make_context(text, m.start(), m.end()),
            ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 2 — Copulative Avoidance
# ---------------------------------------------------------------------------

_COPULATIVE_RE = re.compile(
    r"\b(serves?\s+as|stands?\s+as|marks?|represents?|boasts?|features?|offers?)\b",
    re.IGNORECASE,
)


# Words that, when immediately preceding "feature(s)" or "offer(s)" or "mark(s)",
# signal noun usage rather than copulative verb usage.
_NOUN_SIGNAL_BEFORE = re.compile(
    r"\b(key|main|core|top|major|new|unique|special|important|premium|notable|"
    r"additional|advanced|standard|basic|its|their|our|your|all|these|those|"
    r"the|a|an|of|and|or|with|other|more|many|several|various|following|"
    r"include|including|such)\s+$",
    re.IGNORECASE,
)

# Verbs that are ambiguous as noun/verb and need extra filtering.
_AMBIGUOUS_VERBS = re.compile(r"^(features?|offers?|marks?)$", re.IGNORECASE)


def _is_noun_usage(m, text):
    """Return True if a copulative-avoidance match looks like noun usage, not a verb."""
    word = m.group()
    if not _AMBIGUOUS_VERBS.match(word):
        return False

    # Followed by a colon or line-end → label/heading ("Key features:")
    after = text[m.end():m.end() + 3].lstrip(" \t")
    if after.startswith(":") or after.startswith("\n") or after == "":
        return True

    # Preceded by a determiner, adjective, preposition, or possessive → noun phrase
    before = text[max(0, m.start() - 30):m.start()]
    if _NOUN_SIGNAL_BEFORE.search(before):
        return True

    # At the start of a line (after stripping bullets/heading markers) → heading/label
    line_start = text.rfind("\n", 0, m.start())
    line_prefix = text[line_start + 1:m.start()].strip()
    if not line_prefix or re.match(r"^[#\-\*\d\.\u2022\u2013]+\s*$", line_prefix):
        return True

    # "marks" as a verb almost always precedes an article (marks a turning point,
    # marks an era). Without one it's likely a noun (question marks, bench marks).
    if re.match(r"^marks?$", word, re.IGNORECASE):
        after_word = text[m.end():m.end() + 10].lstrip()
        if not re.match(r"^(a|an|the|this|that|one)\b", after_word, re.IGNORECASE):
            return True

    return False


def detect_copulative_avoidance(text, index):
    findings = []
    for m in _COPULATIVE_RE.finditer(text):
        if _is_noun_usage(m, text):
            continue
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Copulative Avoidance",
            "Language & Grammar",
            loc,
            m.group(),
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 3 — Negative Parallelism: "Not Just X, But Also Y"
# ---------------------------------------------------------------------------

_NOT_JUST_BUT_RE = re.compile(
    r"\bnot\s+(only|just|merely|simply).{1,120}?(but(\s+also)?|rather)\b",
    re.IGNORECASE | re.DOTALL,
)


def detect_not_just_but(text, index):
    findings = []
    for m in _NOT_JUST_BUT_RE.finditer(text):
        matched = m.group()
        if len(matched) > 120:
            continue
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            'Negative Parallelism ("Not Just…But")',
            "Language & Grammar",
            loc,
            matched,
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 4 — Negative Parallelism: "Not X, But Y"
# ---------------------------------------------------------------------------

_NOT_X_BUT_Y_RE = re.compile(
    # Same-sentence: "it's not X; it's Y" / "it's not X — it's Y" / "it's not X, it's Y"
    # Requires an affirmation marker in the same sentence to avoid "It's not his fault." alone.
    r"it'?s\s+not\b[^.!?\n]{1,120}[;,\u2014]\s*it'?s\b"
    r"|this\s+is\s+not\b[^.!?\n]{1,120}[;,\u2014]\s*(?:it'?s|this\s+is)\b"
    # Cross-sentence full verb: "X is not Y. It is Z."
    r"|\b\w+\s+is\s+not\s+\w[^.!?\n]{0,80}[.!?]\s+(?:it|this|that)\s+is\b"
    # Cross-sentence contraction: "isn't [in/about/the] X. It's Y."
    r"|\bisn'?t\b[^.!?\n]{1,120}[.!?]\s+(?:it'?s|this\s+is|that'?s)\b"
    # Inline comma-negation at end: "X, not the/a Y."
    r"|,\s+not\s+(?:the|a|an|this|that)\s+\w[\w\s\-']{0,40}[.!?]"
    # not a X — it's Y
    r"|not\s+a\s+\w[\w\s]{0,40}[,\u2014]\s*(it'?s|but|rather)"
    # no X, no Y
    r"|no\s+\w+,\s*no\s+\w+",
    re.IGNORECASE,
)


def detect_not_x_but_y(text, index):
    findings = []
    for m in _NOT_X_BUT_Y_RE.finditer(text):
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            'Negative Parallelism ("Not X…But Y")',
            "Language & Grammar",
            loc,
            m.group(),
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 5 — Rule of Three
# ---------------------------------------------------------------------------

_RULE_OF_THREE_RE = re.compile(
    r"[\w][\w\s\-'\"]{2,40},\s+[\w][\w\s\-'\"]{2,40},?\s+and\s+[\w][\w\s\-'\"]{2,40}",
    re.IGNORECASE,
)


def detect_rule_of_three(text, index):
    findings = []
    for m in _RULE_OF_THREE_RE.finditer(text):
        # If a comma appears in the two characters immediately before the match,
        # this is just the trailing end of a longer list (4+ items), not a true
        # rule-of-three construction. Skip it.
        before = text[max(0, m.start() - 2):m.start()]
        if "," in before:
            continue

        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Rule of Three",
            "Language & Grammar",
            loc,
            m.group().strip(),
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 6 — Elegant Variation
# ---------------------------------------------------------------------------

ELEGANT_VARIATION_TERMS = {
    # People
    "the entrepreneur", "the executive", "the founder", "the leader",
    "the pioneer", "the visionary", "the innovator", "the figure",
    "the individual", "the subject", "the protagonist", "the key player",
    # Objects / works
    "the system", "the tool", "the platform", "the solution",
    "the framework", "the model", "the approach", "the method",
    # Locations / orgs
    "the institution", "the organization", "the entity", "the body",
    "the group", "the collective",
}


def detect_elegant_variation(text, index):
    findings = []
    text_lower = text.lower()
    for term in ELEGANT_VARIATION_TERMS:
        start = 0
        while True:
            pos = text_lower.find(term, start)
            if pos == -1:
                break
            loc = _offset_to_location(pos, index)
            findings.append(_finding(
                "Elegant Variation",
                "Language & Grammar",
                loc,
                text[pos:pos + len(term)],
                _make_context(text, pos, pos + len(term)),
            ))
            start = pos + len(term)
    return findings


# ---------------------------------------------------------------------------
# Pattern 7 — Title Case Section Headings
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_SKIP_WORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "for",
               "and", "but", "or", "nor", "with", "by", "as", "vs"}


def _is_title_case(heading_text):
    words = heading_text.split()
    content_words = [w for w in words[1:] if w.lower() not in _SKIP_WORDS and w.isalpha()]
    if not content_words:
        return False
    capitalized = sum(1 for w in content_words if w[0].isupper())
    return capitalized / len(content_words) > 0.6


def detect_title_case_headings(text, index):
    findings = []
    for m in _HEADING_RE.finditer(text):
        heading_text = m.group(2)
        if _is_title_case(heading_text):
            loc = _offset_to_location(m.start(), index)
            findings.append(_finding(
                "Title Case Section Headings",
                "Style",
                loc,
                m.group(),
                m.group(),
            ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 8 — Mechanical Bolding
# ---------------------------------------------------------------------------

_BOLD_SPAN_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")


def detect_mechanical_bolding(text, index):
    findings = []
    words = text.split()
    total_words = max(len(words), 1)
    bold_matches = list(_BOLD_SPAN_RE.finditer(text))
    bold_word_count = sum(
        len((m.group(1) or m.group(2)).split()) for m in bold_matches
    )
    ratio = bold_word_count / total_words
    if ratio > 0.08:
        for m in bold_matches:
            loc = _offset_to_location(m.start(), index)
            findings.append(_finding(
                "Mechanical Bolding",
                "Style",
                loc,
                m.group(),
                _make_context(text, m.start(), m.end()),
            ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 9 — Inline-Header Vertical Lists (Bold-Label Bullets)
# ---------------------------------------------------------------------------

_BOLD_LABEL_BULLET_RE = re.compile(
    r"^[\s\-\*•\u2013\d\.]+\*\*[^*\n]+\*\*\s*:",
    re.MULTILINE,
)
_NONSTANDARD_BULLET_RE = re.compile(
    r"^[\s]*(•|\u2013|[0-9]+\.) ",
    re.MULTILINE,
)


def detect_inline_header_lists(text, index):
    findings = []
    for m in _BOLD_LABEL_BULLET_RE.finditer(text):
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Inline-Header Vertical Lists",
            "Style",
            loc,
            m.group().strip(),
            _make_context(text, m.start(), m.end()),
        ))
    for m in _NONSTANDARD_BULLET_RE.finditer(text):
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Inline-Header Vertical Lists (Non-standard Bullet)",
            "Style",
            loc,
            m.group().strip(),
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 10 — Emoji in Structural Elements
# ---------------------------------------------------------------------------

_EMOJI_HEADING_RE = re.compile(
    r"^[^\w\s]*[\U00010000-\U0010ffff\U00002600-\U000027BF][^\n]*$",
    re.MULTILINE,
)


def _has_emoji(char):
    return (
        unicodedata.category(char) in ('So', 'Sm')
        or ord(char) > 0x1F300
    )


def detect_emoji_structural(text, index):
    findings = []
    for m in _EMOJI_HEADING_RE.finditer(text):
        if any(_has_emoji(c) for c in m.group()):
            loc = _offset_to_location(m.start(), index)
            findings.append(_finding(
                "Emoji in Structural Elements",
                "Style",
                loc,
                m.group().strip(),
                m.group().strip(),
            ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 11 — Em Dash Overuse
# ---------------------------------------------------------------------------

_EM_DASH_RE = re.compile(r"\u2014")


def detect_em_dash_overuse(text, index):
    findings = []
    for m in _EM_DASH_RE.finditer(text):
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Em Dash Overuse",
            "Style",
            loc,
            "—",
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 12 — Unnecessary Tables
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"^\|.+\|", re.MULTILINE)


def detect_unnecessary_tables(text, index):
    findings = []
    blocks = re.split(r'\n\n+', text)
    char_offset = 0
    for block in blocks:
        rows = _TABLE_ROW_RE.findall(block)
        data_rows = [r for r in rows if not re.match(r'^\|[\s\-:]+\|', r)]
        if 1 <= len(data_rows) <= 4:
            # Find where this block starts in the original text
            block_pos = text.find(block, char_offset)
            loc = _offset_to_location(block_pos, index)
            findings.append(_finding(
                "Unnecessary Table",
                "Style",
                loc,
                block.strip()[:120] + ("…" if len(block.strip()) > 120 else ""),
                block.strip()[:200] + ("…" if len(block.strip()) > 200 else ""),
            ))
        char_offset += len(block) + 2
    return findings


# ---------------------------------------------------------------------------
# Pattern 13 — Curly Quotation Marks
# ---------------------------------------------------------------------------

_CURLY_DOUBLE_RE = re.compile(r'[\u201C\u201D]')
_CURLY_SINGLE_RE = re.compile(r'[\u2018\u2019]')


def detect_curly_quotes(text, index):
    findings = []
    for m in _CURLY_DOUBLE_RE.finditer(text):
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Curly Quotation Marks",
            "Style",
            loc,
            m.group(),
            _make_context(text, m.start(), m.end()),
        ))
    for m in _CURLY_SINGLE_RE.finditer(text):
        loc = _offset_to_location(m.start(), index)
        findings.append(_finding(
            "Curly Apostrophe/Quote",
            "Style",
            loc,
            m.group(),
            _make_context(text, m.start(), m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 14 — Sycophantic Opener
# ---------------------------------------------------------------------------

_SYCOPHANTIC_RE = re.compile(
    r"^(great\s+(question|point|idea|choice)|absolutely[!,]|certainly[!,]|"
    r"of\s+course[!,]|excellent\s+(question|point)|sure\s+thing|"
    r"i'?d\s+be\s+happy\s+to|what\s+a\s+(great|wonderful|fantastic))",
    re.IGNORECASE,
)


def detect_sycophantic_opener(text, index):
    findings = []
    stripped = text.strip()
    m = _SYCOPHANTIC_RE.match(stripped)
    if m:
        loc = _offset_to_location(0, index)
        findings.append(_finding(
            "Sycophantic Opener",
            "Additional",
            loc,
            m.group(),
            _make_context(text, 0, m.end()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Pattern 15 — Formulaic Conclusion
# ---------------------------------------------------------------------------

_FORMULAIC_CONCLUSION_RE = re.compile(
    r"\b(in\s+(summary|conclusion|closing)|to\s+(summarize|recap|conclude)|"
    r"overall[,\s]|ultimately[,\s]|taken\s+together[,\s]|"
    r"all\s+(things|factors)\s+considered)",
    re.IGNORECASE,
)


def detect_formulaic_conclusion(text, index):
    findings = []
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if not paragraphs:
        return findings
    last_para = paragraphs[-1]
    last_para_offset = text.rfind(last_para)
    for m in _FORMULAIC_CONCLUSION_RE.finditer(last_para):
        abs_offset = last_para_offset + m.start()
        loc = _offset_to_location(abs_offset, index)
        findings.append(_finding(
            "Formulaic Conclusion",
            "Additional",
            loc,
            m.group(),
            _make_context(text, abs_offset, abs_offset + m.end() - m.start()),
        ))
    return findings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

CATEGORY_ORDER = ["Language & Grammar", "Style", "Additional"]


def analyze(text):
    """
    Run all 15 detectors against text.
    Returns a list of Finding dicts sorted by category then location.
    """
    if not text or not text.strip():
        return []

    index = _build_location_index(text)

    all_findings = []
    all_findings.extend(detect_ai_vocab(text, index))
    all_findings.extend(detect_copulative_avoidance(text, index))
    all_findings.extend(detect_not_just_but(text, index))
    all_findings.extend(detect_not_x_but_y(text, index))
    all_findings.extend(detect_rule_of_three(text, index))
    all_findings.extend(detect_elegant_variation(text, index))
    all_findings.extend(detect_title_case_headings(text, index))
    all_findings.extend(detect_mechanical_bolding(text, index))
    all_findings.extend(detect_emoji_structural(text, index))
    all_findings.extend(detect_em_dash_overuse(text, index))
    all_findings.extend(detect_unnecessary_tables(text, index))
    all_findings.extend(detect_sycophantic_opener(text, index))
    all_findings.extend(detect_formulaic_conclusion(text, index))

    def sort_key(f):
        cat_order = CATEGORY_ORDER.index(f["category"]) if f["category"] in CATEGORY_ORDER else 99
        # Parse paragraph/sentence for numeric sort
        loc = f["location"]
        para_num = 0
        sent_num = 0
        pm = re.search(r'Paragraph\s+(\d+)', loc)
        sm = re.search(r'Sentence\s+(\d+)', loc)
        if pm:
            para_num = int(pm.group(1))
        if sm:
            sent_num = int(sm.group(1))
        return (cat_order, f["pattern_type"], para_num, sent_num)

    all_findings.sort(key=sort_key)
    return all_findings
