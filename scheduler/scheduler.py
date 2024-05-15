import asyncio
from datetime import datetime
from time import time
from models.machine import MediaMachine, JsonSections, FileStates
from models.api_collections import TaskCurrent
from system_works import files
from api_requests import api_requests
import logging

logger = logging.getLogger(__name__)

async def set_schedule(machine: MediaMachine, task: dict):
    '''Ставим статус 'scheduled' заданию из списка задач'''

    tsk = next((x for x in machine.scheduler if all((
        x['md5hash'] == task.get('md5hash'),
        x['filename'] == task.get('filename'),
        x['from_date'] == task['from_date'],
        x['display'] == task['display']))), None)

    if tsk is None:
        machine.scheduler.append(task)
        tsk = machine.scheduler[-1]
        tsk['state'] = FileStates.SCHEDULED.value


async def start_scheduler(machine: MediaMachine, interval=1):

    while True:
        logger.info("Новый цикл планировщика")

        for task in machine.scheduler:
            if (task['state'] in (FileStates.SCHEDULED.value,
                                FileStates.CURRENT.value)
                and datetime.strptime(
                    task['from_date'],
                    machine.from_date_format) <= datetime.today()):


                res = await files.set_current(
                                    machine=machine,
                                    current_task=TaskCurrent(**task)
                                    )

                # Замена инфо о текущем файле в списке текущих

                if res[0]:
                    task['state'] = FileStates.CURRENT.value
                    await files.save_json(machine)

                # отправка отчета серверу?
                data = task.copy()
                data.update({'status': res[0], 'error': res[1]})
                logger.info(f'{task=} {data=}')
                await api_requests.send_response(data=data, url=f"{machine.srv_url}/device/{machine.info['serial']}/schedule")
            else:
                logger.info("Нет подходящих задач")

        await asyncio.sleep(interval*60)
