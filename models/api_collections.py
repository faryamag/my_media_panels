from pydantic import BaseModel


class TaskCurrent(BaseModel):
    display: str | int
    md5hash: str
    url: str
