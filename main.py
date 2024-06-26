import asyncio
import json
import os
from datetime import datetime
from time import time
import aiofiles
from models.machine import MediaMachine, JsonSections
from models.api_collections import TaskCurrent
from api_requests import api_requests
from system_works import files
from scheduler import scheduler
import configparser
import logging

logger = logging.getLogger(__name__)

async def server_polling(machine: MediaMachine,
                         interval=30,
                         url=None):

    while True:
        logger.info("Новый цикл Загрузчика")
        # Процедура запроса заднных к серверу
        # Запрос данных серверу:
        if url and 'json' in url:
            async with aiofiles.open(
                    os.path.abspath(f'{machine.working_dir}/{machine.db_json}'),
                    mode='r'
                    ) as j_file:
                response = json.loads(await j_file.read()).get(
                    JsonSections.SCHEDULE.value)
        else:
            url = url if url else f"{machine.srv_url}/device/{machine.info.get('serial')}"
            response = await api_requests.request_tasks(url=url)

        if not isinstance(response, dict):
            logger.warning(f"RESPONSE=, {response}")
            response = {}

        # Проверка данных в списках json ('schedule', 'current', 'delete'):
        # Запуск задач удаления
        to_delete_list = response.get('delete')
        if to_delete_list is not None:
            delete_tasks = [asyncio.create_task(files.delete_file(
                machine=machine,
                filename=task.get('filename'),
                md5hash=task.get('md5hash')
                )) for task in to_delete_list]

            await asyncio.gather(*delete_tasks)
            await files.save_json(machine)

        # Запуск задачи немедленной постановки файла проигрывания
        make_current_list = response.get(JsonSections.CURRENT.value, ())
        if make_current_list is not None:
            current_tasks = [asyncio.create_task(
                files.set_current(
                    machine=machine,
                    current_task=TaskCurrent(**task)
                    )
                ) for task in make_current_list]

            await asyncio.gather(*current_tasks)
            await files.save_json(machine)

        # Запуск задач загрузки, сверки и планировки файла проигрывания
        scheduled_tasks = []
        new_schedule = response.get(JsonSections.SCHEDULE.value)

        if new_schedule is not None:
            new_schedule.sort(key=lambda rec: datetime.strptime(
                            rec.get('from_date'),
                            machine.from_date_format
                            ))

            for sch_task in new_schedule:

                logger.info(f"Загрузчик качает, {sch_task['filename']=}")
                # Качаем, сверяем, переносим
                if {
                        'filename': sch_task.get('filename'),
                        'md5hash': sch_task.get('md5hash')
                        } not in machine.files:

                    get_file_task = asyncio.create_task(api_requests.get_file(
                                        machine=machine,
                                        url=sch_task.get('url'),
                                        filename=sch_task['filename'])
                                        )

                    check_hash_task = asyncio.create_task(files.get_md5(
                                        machine=machine,
                                        filename=sch_task['filename'],
                                        md5hash=sch_task['md5hash'])
                                        )

                    check_hash_task.add_done_callback(
                        lambda task: files.move_to_working_dir(
                            task, machine
                            ))

                    scheduled_tasks.extend([get_file_task, check_hash_task])

                # Сверяем наличие полученно задачи во внутреннем планировщике
                # и обновляем ее
                await scheduler.set_schedule(machine, sch_task)
        try:
            await asyncio.gather(*scheduled_tasks)
            await files.save_json(machine)
        except Exception as exception:
            logger.exception(f'Глобальная ошибка в main.server_pooling {exception=}')
        await asyncio.sleep(interval*60)


async def timer():
    while True:
        print(datetime.now().strftime("%H:%M:%S"))
        await asyncio.sleep(1)


async def main():
    config = configparser.ConfigParser()
    config.read('config.cfg')


    logging.basicConfig(filename=config['local']['log_file'], level=config['local']['loglevel'], encoding='utf-8', format='%(asctime)s %(levelname)s Loggername:%(name)s Function:%(module)s.%(funcName)s.%(lineno)d Message: %(message)s')
    logger.info('Started')

    machine = MediaMachine(
        working_dir=config['local']['working_dir'],
        srv_url=config['server']['url']
        )

    machine.files = await files.get_files_list_from_dir(machine=machine)

    logger.info(f'{machine.__dict__=}')
    # Добавляем фиктивные данные для теста
    machine.info['serial'] = '123test'
    machine.info['displays'].append('7')
    machine.service_name = config['local']['service']

    scheduler_instant = scheduler.start_scheduler(
                            machine, interval=1
                            )
    poller = server_polling(
                            machine,
                            interval=1
                            )
    await asyncio.gather(scheduler_instant, poller, timer())
    await files.save_json(machine)
    logger.info('Finish')


asyncio.run(main())
#print(logging.INFO)