from pydantic import BaseModel
from typing import Optional


class TaskCurrent(BaseModel):
    display: str | int
    md5hash: str
    url: str

class CurrentInfo(BaseModel):

    # necessary

    display: str  # list of video interfaces
    filename: str # list of current playing files
    md5hash: str
    error: Optional[str]

class ScheduledFile(BaseModel):

    # necessary

    display: str  # list of video interfaces
    from_date: str # dd.mm.yyyy
    filename: str # list of current playing files
    md5hash: str
    url: str
    state: str
    # optional
    status: Optional[bool]
    error: Optional[str]