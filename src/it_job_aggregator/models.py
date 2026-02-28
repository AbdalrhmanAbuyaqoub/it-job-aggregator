from pydantic import BaseModel, HttpUrl


class Job(BaseModel):
    """
    Standardized model for a job posting.
    All scrapers must return instances of this model.
    """

    title: str
    company: str | None = None
    link: HttpUrl
    description: str
    source: str
    position_level: str | None = None
    location: str | None = None
    deadline: str | None = None
    experience: str | None = None
    posted_date: str | None = None
