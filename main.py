import aiohttp
import aiofiles
import asyncio
import functools
import json
import hashlib
import os
import subprocess

from datetime import datetime
from time import time
#from api_requests import api_requests
from models.machine import MediaMachine, FileStatus, JsonSections
from api_requests import api_requests
from system_works import files
from scheduler import scheduler

async def server_polling(machine: MediaMachine, interval=30, url=None, async_events: dict[asyncio.Event]=None):

    async_events = {} if async_events is None else async_events

    while True:
        print("Новый цикл Загрузчика", time())
        # Процедура запроса заднных к серверу
        # Запрос данных серверу:
        if url is None:
            url = f"{machine.srv_url}/device/{machine.info.get('serial')}"
            response = await api_requests.request_tasks(url=url)
        elif 'json' in url:
            async with aiofiles.open(os.path.abspath(f'{machine.working_dir}/{machine.db_json}'), mode='r') as j_file:
                response = json.loads(await j_file.read()).get(JsonSections.Schedule.value)
        # Проверка данных в списках json ('schedule', 'current', 'delete'):
        # Запуск задач удаления
        to_delete_list = response.get('delete')
        if to_delete_list is not None:
            delete_tasks = [asyncio.create_task(files.delete_file(
                machine=machine,
                filename=task.get('filename'),
                md5hash=task.get('md5hash'),
                async_events=async_events
                )) for task in to_delete_list]

            await asyncio.gather(*delete_tasks)
            await files.save_json(machine)

        # Запуск задачи немедленной постановки файла проигрывания
        make_current_list = response.get(JsonSections.Current.value, ())
        if make_current_list is not None:
            current_tasks = [asyncio.create_task(
                files.set_current(
                    machine=machine,
                    filename=task.get('filename'),
                    display=task.get('display'),
                    md5hash=task.get('md5hash'),
                    url=task.get('url'),
                    async_events=async_events
                    )
                ) for task in make_current_list]

            await asyncio.gather(*current_tasks)
            await files.save_json(machine)

        # Запуск задач загрузки, сверки и планировки файла проигрывания
        scheduled_tasks = []
        new_schedule = list(response.get(JsonSections.Schedule.value))
        if new_schedule is not None:
            new_schedule.sort(key=lambda x: datetime.strptime(x.get('from'), machine.from_date_format))
            for sch_task in new_schedule:

                print("Загрузчик качает ", sch_task['filename'])
                # Качаем, сверяем, переносим
                if {'filename': sch_task.get('filename'), 'md5hash': sch_task.get('md5hash')} not in machine.files:

                    get_file_task = asyncio.create_task(api_requests.get_file(
                                        machine=machine,
                                        url=sch_task.get('url'),
                                        filename=sch_task['filename'],
                                        async_events=async_events)
                                        )

                    check_hash_task = asyncio.create_task(files.get_md5(
                                        machine=machine,
                                        filename=sch_task['filename'],
                                        md5hash=sch_task['md5hash'],
                                        async_events=async_events)
                                        )

                    check_hash_task.add_done_callback(
                        lambda task: files.move_to_working_dir(
                            task, machine, async_events
                            ))

                    scheduled_tasks.extend([get_file_task, check_hash_task])

                # Сверяем наличие полученно задачи во внутреннем планировщике и обновляем ее
                await scheduler.set_schedule(machine, sch_task)

            await asyncio.gather(*scheduled_tasks)
            await files.save_json(machine)

        await asyncio.sleep(interval*60)


async def timer():
    while True:
        print(datetime.now().strftime("%H:%M:%S"))
        await asyncio.sleep(1)


async def main():
    async_events = dict()

    machine = MediaMachine(working_dir='./media', srv_url='http://localhost:8000')
    machine.files = await files.get_files_list_from_dir(machine)
    machine.info['serial'] = '123test'
    print(machine.info.get('serial'))
    # file = 'test.mp4'

    machine.info['displays'].append('7')
    machine.service_name = 'notepad'

    #response = await api_requests.request_tasks(machine=machine, url='http://localhost:8000')
    #print(response)

    scheduler_instant = scheduler.start_scheduler(machine, interval=1, async_events=async_events)
    poller = server_polling(machine, interval=1, async_events=async_events)
    await asyncio.gather(scheduler_instant, poller, timer())
    await files.save_json(machine)

    print(machine.info)


start = time()
asyncio.run(main())
print(f'Выполнено за {time()-start}')