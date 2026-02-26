import pytest
from it_job_aggregator.filters import JobFilter


@pytest.fixture
def job_filter():
    return JobFilter()


@pytest.mark.parametrize(
    "text, expected",
    [
        # English Positive Cases
        ("We are hiring a Senior Software Engineer for our team.", True),
        ("Looking for an SDET with Python experience.", True),
        ("Frontend Developer needed - React.js.", True),
        ("Information Technology Support Specialist position open.", True),
        ("DevOps role available immediately.", True),
        ("Seeking a Data Analyst.", True),
        # Arabic Positive Cases
        ("مطلوب مطور برمجيات للعمل في رام الله", True),
        ("شاغر مهندس بيانات بخبرة 3 سنوات", True),
        ("نبحث عن مبرمج تطبيقات أندرويد", True),
        ("وظيفة في مجال الأمن السيبراني", True),
        ("مطلوب مهندس فحص جودة (QA)", True),
        ("شركة تكنولوجيا تبحث عن خريجين جدد", True),
        # Mixed Language Positive Cases
        ("مطلوب Fullstack Developer لشركة رائدة", True),
        ("نبحث عن خبراء React و Node.js", True),
        # Negative Cases
        ("مطلوب محاسب للعمل في شركة تجارية", False),
        ("We are looking for a Marketing Manager.", False),
        ("مطلوب سائق توصيل", False),
        ("Welcome to our new Telegram channel!", False),
        ("مطلوب معلمة لغة إنجليزية", False),
        ("Looking for a construction worker.", False),
        ("Cashier needed urgently.", False),
        # Unicode stylized text (mathematical bold, italic, etc.)
        (
            "وظيفة شاغرة لدى شركة عيون ميديا\n𝗙𝘂𝗹𝗹 𝗦𝘁𝗮𝗰𝗸 𝗗𝗲𝘃𝗲𝗹𝗼𝗽𝗲𝗿\nللتقديم عبر جوبس",
            True,
        ),
        (
            "شاغر لدى شركة 𝗘𝗥𝗣 𝗘𝗮𝘀𝘆 𝗦𝗼𝗹𝘂𝘁𝗶𝗼𝗻𝘀\nمبرمج VB.NET",
            True,
        ),
        ("𝗦𝗼𝗳𝘁𝘄𝗮𝗿𝗲 𝗘𝗻𝗴𝗶𝗻𝗲𝗲𝗿 needed", True),
        ("𝘋𝘦𝘷𝘖𝘱𝘴 position available", True),
        ("𝙌𝘼 𝙏𝙚𝙨𝙩𝙚𝙧 role", True),
        # Stylized non-IT text should still be rejected
        ("𝗠𝗮𝗿𝗸𝗲𝘁𝗶𝗻𝗴 𝗠𝗮𝗻𝗮𝗴𝗲𝗿 needed", False),
        # Verify "it" (the English word) does NOT trigger a false positive
        ("Take it from me, this is not a tech job.", False),
        ("We need it done by Friday.", False),
        # New keywords
        ("Looking for a Cloud Architect with AWS experience.", True),
        ("Database Administrator needed for SQL Server.", True),
        ("Docker and Kubernetes experience required.", True),
        ("Machine Learning Engineer wanted.", True),
        ("Linux System Administrator role.", True),
        # Edge cases
        ("", False),
        (None, False),
    ],
)
def test_is_it_job(job_filter, text, expected):
    """Test the IT job filter against various positive and negative cases."""
    assert job_filter.is_it_job(text) == expected
