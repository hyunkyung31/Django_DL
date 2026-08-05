import re


def keyword_in_text(keyword: str, text: str) -> bool:
    """Substring match with guards for short Korean/English tokens.

    Prevents false positives like medicine keyword '약' matching inside '예약'.
    """
    if not keyword or not text:
        return False

    kw = keyword.lower()
    msg = text.lower()

    # Very short tokens need boundaries (Korean syllable / alnum).
    if len(kw) <= 2:
        pattern = rf"(?<![가-힣a-z0-9]){re.escape(kw)}(?![가-힣a-z0-9])"
        return re.search(pattern, msg) is not None

    return kw in msg
