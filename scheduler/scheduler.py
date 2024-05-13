import asyncio
from datetime import datetime
from time import time
from models.machine import MediaMachine, JsonSections, FileStates
from models.api_collections import TaskCurrent
from system_works import files
from api_requests import api_requests


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
        #try:
        print("Новый цикл планировщика", time())

        for task in machine.scheduler:
            if (task['state'] in (FileStates.SCHEDULED.value,
                                FileStates.CURRENT.value)
                and datetime.strptime(
                    task['from_date'],
                    machine.from_date_format) <= datetime.today()):
                #print(task)

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
                print(data)
                print(f'{machine.srv_url}')
                await api_requests.send_response(data=data, url=f"{machine.srv_url}/device/{machine.info['serial']}/schedule")
            else:
                print("Нет подходящих задач")
    #except Exception as exception:
        #    print(f'Глобальная ошибка в цикле планировщика(scheduler.start_scheduler) {exception=}')
        await asyncio.sleep(interval*60)
