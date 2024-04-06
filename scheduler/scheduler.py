import aiohttp
import aiofiles
import asyncio
import json
import hashlib
import os
import subprocess
from datetime import datetime
from time import time
from models.machine import MediaMachine
from system_works import files
from api_requests import api_requests


async def set_schedule(machine: MediaMachine, task: dict):
    '''Ставим статус 'scheduled' заданию из списка задач'''

    tsk = next((x for x in machine.scheduler if all((
        x['md5hash'] == task.get('md5hash'),
        x['filename'] == task.get('filename'),
        x['from'] == task['from'],
        x['display'] == task['display']))), None)

    if tsk is None:
        machine.scheduler.append(task)
        tsk = machine.scheduler[-1]
    tsk['state'] = 'scheduled'


async def start_scheduler(machine: MediaMachine, interval=1, async_events:dict[asyncio.Event]=None):

    while True:
        print("Новый цикл планировщика", time())
        for task in machine.scheduler:
            if task['state'] in ('scheduled', 'current') and datetime.strptime(task['from'], machine.from_date_format) <= datetime.today():
                res = await files.set_current(
                                    machine=machine,
                                    filename=task['filename'],
                                    display=task['display'],
                                    md5hash=task['md5hash'],
                                    url=task.get('url', None),
                                    async_events=async_events
                                    )

                # Замена инфо о текущем файле в списке текущих

                if res[0]:
                    task['state'] = 'current'
                    await files.save_json(machine)

                # отправка отчета серверу?
                data = task.copy()
                data.update({'status': res[0], 'error': res[1]})
                await api_requests.send_response(data=data, url='json')

        await asyncio.sleep(interval*60)
