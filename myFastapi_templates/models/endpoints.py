from pydantic import BaseModel
from models.api_collections import CurrentInfo, ScheduledFile


class MediaMachine(BaseModel):

    # necessary

    displays: list[str] | None = None # list of video interfaces
    current: list[dict] # list of current playing files
    files: list[dict]

    # optional
    serial: str | None = None   # SN for API requests
    name: str = 'testp6' # Hostname # optional
    description: str = 'FirstInitMachine' # optional
    model: str = 'raspberry Pi 3B' # optional
    wlan_mac: str | None = None # optional
    ether_mac: str | None = None # optional
    working_dir: str = './scripts/tmp' # common operating dir
    json_file: str = f'{working_dir}/db.json' # local database
