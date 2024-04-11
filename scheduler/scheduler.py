import asyncio
from datetime import datetime
from time import time
from models.machine import MediaMachine, JsonSections, FileStates
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
    tsk['state'] = FileStates.SCHEDULED


async def start_scheduler(machine: MediaMachine, interval=1):

    while True:
        print("Новый цикл планировщика", time())
        for task in machine.scheduler:
            if task['state'] in (FileStates.SCHEDULED, FileStates.CURRENT) and datetime.strptime(
                                                    task['from'],
                                                    machine.from_date_format
                                                    ) <= datetime.today():
                res = await files.set_current(
                                    machine=machine,
                                    filename=task['filename'],
                                    display=task['display'],
                                    md5hash=task['md5hash'],
                                    url=task.get('url', None)
                                    )

                # Замена инфо о текущем файле в списке текущих

                if res[0]:
                    task['state'] = FileStates.CURRENT
                    await files.save_json(machine)

                # отправка отчета серверу?
                data = task.copy()
                data.update({'status': res[0], 'error': res[1]})
                print(data)
                await api_requests.send_response(data=data, url='json')

        await asyncio.sleep(interval*60)
