
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from time import time


class JsonSections(Enum):
    Schedule = 'schedule'
    Info = 'info'
    Current = 'current'
    Files = 'files'



class FileStatus(Enum):
    # state in (None, 'scheduled', 'downloading', 'error')

    downloading = 1
    error = 2
    current = 3
    scheduled = 4
    archived = 5


@dataclass
class MediaMachine:

    working_dir: str = field(compare=False, default='./media')
    downloading_dir: str = field(init=False)
    from_date_format: str = field(compare=False, default='%d.%m.%Y')
    service_name: str | None = field(default=None)  # Наименование активного сервиса воспроизведения медиа
    db_json: str = field(compare=False, default='db.json')
    scheduler: list[dict] = field(default_factory=list)  # [{'display':str, 'from': datetime, 'filename':str, 'md5hash':str, 'state':str}]
    current: list[dict] = field(default_factory=list)  # {'display':str, 'filename':str, 'md5hash':str}
    files: list = field(default_factory=list)
    srv_url: str = field(compare=False, default='https://opcmedia.teleka.ru')
    renew: bool = field(compare=False, default=False)
    info: dict = field(compare=False, init=False, default_factory=dict)

    def __post_init__(self):

        self.working_dir: str = os.path.abspath(self.working_dir)
        self.downloading_dir = os.path.abspath(f'{self.working_dir}/{"downloading"}')
        if not os.path.exists(self.downloading_dir):
            os.makedirs(self.downloading_dir)
        try:
            # self.scheduler = json.load(f := open(os.path.abspath(f'{self.working_dir}/{self.db_json}'))).get('schedule', [])
            with open(f'{self.working_dir}/{self.db_json}', encoding='utf-8') as db_json:
                self.scheduler = json.load(db_json).get('schedule', [])
        except Exception as e:
            print(self.scheduler, e)
        self.info = self.get_info()

        # self.scheduler.sort(key=lambda x: datetime.strptime(x['from'], self.from_date_format))


    def get_info(self) -> dict:
        # Получаем инфо с raspberry в виде {'displays':[], 'Revision':str, 'Model':str, 'Serial':str}
        # только для  raspberry!

        disp = subprocess.run(
                            "kmsprint | grep Connector | awk '{print $4}'",
                            shell=True, capture_output=True, text=True
                            )
        displays = disp.stdout.split()
        syst = subprocess.run(
                            "cat /proc/cpuinfo | grep -E 'Revision|Serial|Model'",
                            shell=True,
                            capture_output=True,
                            text=True
                            )

        sys_info = dict(
            (x.strip().split('\t:', 1)[0].strip().lower(), x.strip().split('\t:', 1)[0].strip())
            for x in syst.stdout.split('\n') if x
            )

        sys_info.update({'displays': displays})
        sys_info.update({'service': self.service_name})
        sys_info.update({'working_dir': self.working_dir})
        sys_info.update({'downloading_dir': self.downloading_dir})

        return sys_info



if __name__ == '__main__':
    machine = MediaMachine()
    print(machine)