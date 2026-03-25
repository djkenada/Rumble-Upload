import re


# Clickbait filler phrases to remove (applied with word boundaries)
CLICKBAIT_PHRASES = [
    r"\byou won'?t believe\b",
    r"\bwait (?:for|till|until) (?:you see|the end)\b",
    r"\bwatch before (?:it'?s )?(?:deleted|removed|banned)\b",
    r"\bmust watch\b",
    r"\bmust see\b",
    r"\bnot clickbait\b",
    r"\bgone wrong\b",
    r"\bgone sexual\b",
    r"\bi'?m not kidding\b",
    r"\bthis is not a (?:drill|joke)\b",
    r"\byou need to see this\b",
    r"\bwhat happens next\b",
    r"\bnobody expected this\b",
    r"\bno one expected this\b",
    r"\bthey don'?t want you to (?:see|know)\b",
    r"\bwhat they'?re hiding\b",
    r"\bthis changes everything\b",
]

# Parenthetical/bracket clickbait markers to remove
BRACKET_CLICKBAIT = [
    r"\((?:shocking|insane|must watch|not clickbait|emotional|gone wrong|"
    r"you won'?t believe|hilarious|epic|unbelievable|crazy|wow|omg|real|legit|100%)\)",
    r"\[(?:shocking|insane|must watch|not clickbait|emotional|gone wrong|"
    r"you won'?t believe|hilarious|epic|unbelievable|crazy|wow|omg|real|legit|100%)\]",
]

# Exaggerated verbs -> measured replacements
EXAGGERATED_VERBS = {
    r"\bdestroys\b": "challenges",
    r"\bdestroyed\b": "challenged",
    r"\bobliterates\b": "defeats",
    r"\bobliterated\b": "defeated",
    r"\bexposes\b": "reveals",
    r"\bexposed\b": "revealed",
    r"\bannihilates\b": "beats",
    r"\bannihilated\b": "beaten",
    r"\bslams\b": "criticizes",
    r"\bslammed\b": "criticized",
    r"\bwrecks\b": "outperforms",
    r"\bwrecked\b": "outperformed",
}

# All-caps words that are acceptable (acronyms, common abbreviations)
ACCEPTABLE_CAPS = {
    "USA", "US", "UK", "EU", "UN", "NATO", "FBI", "CIA", "NSA", "DOJ",
    "NASA", "NFL", "NBA", "MLB", "NHL", "UFC", "WWE", "MMA",
    "CEO", "CFO", "CTO", "AI", "PC", "TV", "DIY", "LED", "USB",
    "BMW", "AMD", "GPU", "CPU", "RAM", "SSD", "HDD", "RGB",
    "MAGA", "GOP", "DNC", "RNC", "IRS", "SEC", "FCC", "FDA",
    "CEO", "DNA", "RNA", "PhD", "ADHD", "PTSD", "COVID",
    "MP3", "MP4", "4K", "HD", "FHD", "UHD", "VR", "AR",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
    "OK", "ASMR", "LGBTQ", "BTS", "PS5", "PS4", "XBOX",
}

# Emoji regex pattern
EMOJI_RE = re.compile(
    "[\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f1e0-\U0001f1ff"
    "\U00002702-\U000027b0"
    "\U000024c2-\U0001f251"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U00002600-\U000026ff"
    "\U0000fe00-\U0000fe0f"
    "\U0000200d"
    "]+", flags=re.UNICODE
)


def rewrite_title(youtube_title: str) -> str:
    """Rewrite a YouTube title to be Rumble-friendly.

    Rules:
    1. Remove bracket clickbait markers like (SHOCKING), (NOT CLICKBAIT)
    2. Remove clickbait filler phrases
    3. Convert ALL CAPS words to title case (preserve known acronyms)
    4. Replace exaggerated verbs with measured alternatives
    5. Remove all emojis
    6. Clean up pipe/separator keyword chains
    7. Remove excessive punctuation
    8. Soft limit to ~60 characters
    """
    title = youtube_title.strip()
    if not title:
        return title

    # 1. Remove bracket/paren clickbait markers
    for pattern in BRACKET_CLICKBAIT:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)

    # 2. Remove clickbait filler phrases (but don't over-strip)
    title_before_phrases = title
    for pattern in CLICKBAIT_PHRASES:
        candidate = re.sub(pattern, "", title, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", candidate)
        if len(cleaned) >= 15:
            title = candidate
    # Safety check: if we stripped too much overall, only remove bracket markers
    final_cleaned = re.sub(r"[^a-zA-Z0-9]", "", title)
    if len(final_cleaned) < 15:
        title = title_before_phrases

    # 3. Remove "BREAKING:" prefix
    title = re.sub(r"^breaking\s*[:!]\s*", "", title, flags=re.IGNORECASE)

    # 4. Remove all emojis
    title = EMOJI_RE.sub("", title)

    # 5. Handle ALL CAPS words - convert to title case, preserving acronyms
    words = title.split()
    fixed_words = []
    for word in words:
        # Strip punctuation to check the core word
        stripped = re.sub(r"[^a-zA-Z0-9']", "", word)
        if stripped.isupper() and len(stripped) > 2 and stripped not in ACCEPTABLE_CAPS:
            # Convert to title case, preserving surrounding punctuation
            fixed_words.append(_capitalize_word(word))
        else:
            fixed_words.append(word)
    title = " ".join(fixed_words)

    # 6. Replace exaggerated verbs
    for pattern, replacement in EXAGGERATED_VERBS.items():
        title = re.sub(pattern, replacement, title, flags=re.IGNORECASE)

    # 7. Clean up pipe/separator keyword chains
    if "|" in title:
        parts = [p.strip() for p in title.split("|")]
        if len(parts) > 2:
            # Keyword stuffing - keep just the first meaningful part
            title = parts[0]
        else:
            title = " - ".join(parts)

    # 8. Clean up punctuation and whitespace
    title = re.sub(r"[!]{2,}", "!", title)         # !! -> !
    title = re.sub(r"[?]{2,}", "?", title)         # ?? -> ?
    title = re.sub(r"\.{4,}", "...", title)         # .... -> ...
    title = re.sub(r"\s{2,}", " ", title)           # Multiple spaces
    title = re.sub(r"^\s*[-:,|!?]\s*", "", title)   # Leading orphan punctuation
    title = re.sub(r"\s*[-:,|]\s*$", "", title)     # Trailing separators
    title = re.sub(r"\(\s*\)", "", title)            # Empty parens
    title = re.sub(r"\[\s*\]", "", title)            # Empty brackets
    title = re.sub(r"\s+([,!?.])", r"\1", title)    # Space before punctuation
    title = title.strip(" -:,|")

    # 9. Soft limit ~60 chars - truncate at word boundary if needed
    if len(title) > 65:
        # Try to find a natural break point
        truncated = title[:63]
        # Don't break inside parentheses
        open_parens = truncated.count("(") - truncated.count(")")
        if open_parens > 0:
            # Find the last opening paren and cut before it
            last_open = truncated.rfind("(")
            if last_open > 20:
                title = truncated[:last_open].strip()
            else:
                last_space = truncated.rfind(" ")
                if last_space > 30:
                    title = truncated[:last_space].rstrip(" -:,|")
        else:
            last_space = truncated.rfind(" ")
            if last_space > 30:
                title = truncated[:last_space].rstrip(" -:,|")

    return title.strip()


def _capitalize_word(word: str) -> str:
    """Convert an ALL CAPS word to title case while preserving punctuation."""
    result = []
    first_alpha = True
    for ch in word:
        if ch.isalpha():
            if first_alpha:
                result.append(ch.upper())
                first_alpha = False
            else:
                result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)
