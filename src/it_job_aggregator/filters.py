import re
import unicodedata


class JobFilter:
    """
    Filters job postings to identify IT/Software Engineering related jobs
    using English and Arabic keyword matching.

    Handles Unicode stylized text (e.g. mathematical bold 𝗗𝗲𝘃𝗲𝗹𝗼𝗽𝗲𝗿)
    by normalizing to NFKD form before matching.
    """

    ENGLISH_KEYWORDS = [
        "developer",
        "engineer",
        "qa",
        "sdet",
        "programmer",
        "data",
        "frontend",
        "backend",
        "fullstack",
        "full stack",
        "devops",
        "software",
        "react",
        "python",
        "java",
        "ios",
        "android",
        "ui/ux",
        "sysadmin",
        "cybersecurity",
        "security",
        "network",
        "cloud",
        "aws",
        "azure",
        "docker",
        "kubernetes",
        "machine learning",
        "sql",
        "database",
        "linux",
        "information technology",
    ]

    ARABIC_KEYWORDS = [
        "مطور",
        "مبرمج",
        "برمجيات",
        "هندسة",
        "تكنولوجيا",
        "بيانات",
        "سيبراني",
        "جودة",
        "فحص",
        "تقنية",
        "حاسوب",
        "شبكات",
        "تطبيقات",
    ]

    def __init__(self):
        # Compile a regex pattern that matches any of the keywords as whole words
        # For English, we use \b for word boundaries.
        eng_pattern = r"\b(?:" + "|".join(re.escape(kw) for kw in self.ENGLISH_KEYWORDS) + r")\b"

        # For Arabic, \b might not work perfectly due to prefix/suffix
        # attachments in Arabic grammar,
        # but we'll use a standard search for the base words.
        ar_pattern = r"(?:" + "|".join(re.escape(kw) for kw in self.ARABIC_KEYWORDS) + r")"

        # Combine patterns, ignore case
        combined_pattern = f"{eng_pattern}|{ar_pattern}"
        self.regex = re.compile(combined_pattern, re.IGNORECASE)

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize Unicode text to NFKD form to convert stylized characters
        (e.g. mathematical bold 𝗗𝗲𝘃𝗲𝗹𝗼𝗽𝗲𝗿) to their ASCII equivalents.
        """
        return unicodedata.normalize("NFKD", text)

    def is_it_job(self, text: str) -> bool:
        """
        Check if the text contains IT-related keywords.
        Normalizes Unicode text before matching to handle stylized characters.
        """
        if not text:
            return False

        normalized = self.normalize_text(text)
        return bool(self.regex.search(normalized))
