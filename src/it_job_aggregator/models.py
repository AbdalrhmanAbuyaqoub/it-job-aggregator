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
