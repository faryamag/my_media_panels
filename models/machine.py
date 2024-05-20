
import json
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


def async_log_exception_wrapper(func):

    @wraps(func)
    async def log_exception_wrapper(*args, **kwargs):
        __name__ = getattr(func, '__name__')
        try:
            return await func(*args, **kwargs)
        except Exception as exception:
            logger.exception(f"function {func.__name__=} got {exception=} with: {args=},{kwargs=}")

    return log_exception_wrapper


class JsonSections(Enum):
    # Описание секции джейсона для обмена

    SCHEDULE = 'schedule'
    INFO = 'info'
    CURRENT = 'current'
    FILES = 'files'

    def __str__(self):
        return self.value


class FileStates(Enum):
    # state in (None, 'scheduled', 'downloading', 'error')

    DOWNLOADING = 'downloading'
    ERROR = 'error'
    CURRENT = 'current'
    SCHEDULED = 'scheduled'
    ARCHIVED = 'archived'

    def __str__(self):
        return self.value

@dataclass
class MediaMachine:

    working_dir: str = field(compare=False, default='./media')
    downloading_dir: str = field(init=False)
    from_date_format: str = field(compare=False, default='%d.%m.%Y')
    service_name: str | None = field(default=None)  # Наименование активного сервиса воспроизведения медиа
    db_json: str = field(compare=False, default='db.json')
    scheduler: list[dict] = field(default_factory=list)  # [{'display':str, 'from_date': datetime, 'filename':str, 'md5hash':str, 'state':str}]
    current: list[dict] = field(default_factory=list)  # {'display':str, 'filename':str, 'md5hash':str}
    files: list = field(default_factory=list)
    srv_url: str = field(compare=False, default='http://localhost:8000')
    renew: bool = field(compare=False, default=False)
    info: dict = field(compare=False, init=False, default_factory=dict)
    async_events: dict = field(compare=False, init=False, default_factory=dict[asyncio.Event])

    def __post_init__(self):

        self.working_dir: str = os.path.abspath(self.working_dir)
        self.downloading_dir = os.path.abspath(
                    f'{self.working_dir}/{"downloading"}'
                    )
        if not os.path.exists(self.downloading_dir):
            os.makedirs(self.downloading_dir)
        try:
            with open(
                    f'{self.working_dir}/{self.db_json}',
                    encoding='utf-8'
                    ) as db_json:
                self.scheduler = json.load(db_json).get('schedule', [])
        except Exception as e:
            print(self.scheduler, e)
        self.info = self.get_info()
        # self.scheduler.sort(key=lambda x: datetime.strptime(x['from_date'], self.from_date_format))

    @async_log_exception_wrapper
    def get_info(self) -> dict:
        # Получаем инфо с raspberry в виде
        # {'displays':[], 'Revision':str, 'Model':str, 'Serial':str}
        # только для  raspberry!
        logger.info('Получаем инфо машины')
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

        logger.debug(f"Инфо машины:{sys_info}")
        return sys_info

    def get_event(self, eventname: str) -> asyncio.Event:
        '''Проверяет или заводит событие для контроля доступа к объекту(файлу)
        инициирует и возвращает его'''

        if self.async_events.get(eventname, None) is None:
            self.async_events[eventname] = asyncio.Event()
            self.async_events[eventname].set()
        return self.async_events[eventname]
