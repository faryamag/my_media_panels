import asyncio
import json
import hashlib
import os
from datetime import datetime
import aiofiles
from api_requests import api_requests
from models.machine import MediaMachine


def move_to_working_dir(filename: str | asyncio.Task,
                        machine: MediaMachine):
    # Перенос файла в рабочую директорию с проверкой

    md5hash = None
    if isinstance(filename, asyncio.Task):
        if not filename.result()[0]:
            print("Hash not compared, aborting")
            return False
        else:
            md5hash = filename.result()[2]
            filename = filename.result()[1]

    file_handling_event = machine.get_event(filename)
    print('Я переносчик файла', filename, file_handling_event.is_set())
    if not file_handling_event.is_set():
        print('Я переносчик файла', filename, "Файл уже кто-то качает.Выхожу",file_handling_event._waiters())
        return

    dst = os.path.abspath(f'{machine.working_dir}/{filename}')
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(
        src=os.path.abspath(f'{machine.downloading_dir}/{filename}'),
        dst=dst
        )

    record = next((rec for rec in machine.files
                   if rec.get('filename') == filename
                   and rec.get('md5hash') == md5hash), None)
    if record is None:
        machine.files.append({'filename': filename, 'md5hash': md5hash})
    return True


async def get_files_list_from_dir(
                                machine: MediaMachine,
                                path: str = None,
                                extensions: str | list | tuple = None
                                ):

    if extensions is None:
        extension = 'mp4'
    if path is None:
        path = machine.working_dir
    if isinstance(extension, str):
        extension = list(ex.strip() for ex in extension.split(','))
    names = [os.path.abspath(file)
             for file in os.listdir(path)
             if (file.split('.')[-1] in extension)
             and not os.path.islink(f'{path}/{file}')]

    hash_tasks = [asyncio.create_task(
                                    get_md5(
                                        machine,
                                        os.path.split(name)[-1],
                                        dir_path=machine.working_dir
                                        )
                                    ) for name in names]

    await asyncio.gather(*hash_tasks)
    files = [{'filename': task.result()[1], 'md5hash': task.result()[2]} for task in hash_tasks]

    return files


async def delete_file(machine: MediaMachine,
                      filename=None,
                      md5hash=None
                      ) -> tuple[bool | Exception]:
    ''' При удалении считаем, что приоритет имеет значение хэша, если оно есть.
    Если его нет, то ориентируемся на имя файла и ищем хэш в имеющихся
    записях файлов по его имени. Удаляем найденные записи и файлы,
    если только файл не проигрывается '''

    err = None
    if filename is None and md5hash is None:
        err = ValueError("Ничего не передано для удаления")
        return (False, err)

    if md5hash is None:
        record = next((file
                       for file in machine.files
                       if file['filename'] == filename), {})
        md5hash = record.get('md5hash', None)
    else:
        record = next((file
                       for file in machine.files
                       if file['md5hash'] == md5hash), {})
        filename = record.get('filename', md5hash)

    # ниже механизм  предотвращения одновременного доступа к файлу
    # функций: загрузки (get_file), расчета хэша (get_md5hash) и удаления
    file_handling_event = machine.get_event(filename)
    print('Я хочу удалить файл', filename, 'Жду события. Событие - ', file_handling_event)
    await file_handling_event.wait()
    file_handling_event.clear()
    # --------------

    if md5hash in (file['md5hash'] for file in machine.current):
        err = f'''{ValueError(
            "Удалить невозможно: Указанный файл проигрывается в данный момент."
            )}'''
        return (False, err)

    downloading_file_path = os.path.abspath(
                            f'{machine.downloading_dir}/{filename}')
    file_path = os.path.abspath(f'{machine.working_dir}/{filename}')

    try:
        if record in machine.files:
            machine.files.remove(record)
        if os.path.exists(downloading_file_path):
            os.remove(downloading_file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        print(f'{filename} удален')
    except Exception as e:
        err = f'{type(e).__name__}, {e}'
        print('удаляю', err)

    file_handling_event.set()
    await save_json(machine)

    return (True, err) if err is None else (False, err)


async def get_md5(machine: MediaMachine,
                  filename,
                  chunk_size=1,
                  md5hash=None,
                  dir_path=None
                  ) -> tuple[bool | str]:
    '''Функция для асинхронного подсчета хэша мд5 кусками
    (chunk_size) значения в МБ). Вернет кортеж результата
    сравнения с переданным хэшем, имя файла, и его хэш}'''

    await asyncio.sleep(0)
    if dir_path is None:
        dir_path = machine.downloading_dir
    file_handling_event = machine.get_event(filename)
    await file_handling_event.wait()
    file_handling_event.clear()

    chunk_size *= 1024*1024
    filehash = hashlib.md5()
    full_path = os.path.abspath(f'{dir_path}/{filename}')
    if not os.path.exists(full_path):
        file_handling_event.set()
        return (False, filename, 'broken_link')

    async with aiofiles.open(full_path, 'rb') as afile:

        while True:
            task = asyncio.create_task(afile.read(chunk_size))
            chunk = await task
            if not chunk:
                break
            await asyncio.to_thread(filehash.update, chunk)

    file_handling_event.set()

    md5hash = filename.split('.', 1)[0] if md5hash is None else md5hash

    print((md5hash == filehash.hexdigest(), filename, filehash.hexdigest()))
    return (md5hash == filehash.hexdigest(), filename, filehash.hexdigest())


async def save_json(machine: MediaMachine):
    async with aiofiles.open(
        os.path.abspath(
            f'{machine.working_dir}/{machine.db_json}'),
            mode='w') as db_json:
        full_json = json.dumps({
            'info': machine.info,
            'current': machine.current,
            'files': machine.files,
            'schedule': machine.scheduler
            }, indent=2)
        await db_json.write(full_json)
    return


async def set_current(machine: MediaMachine,
                      filename: str,
                      display=None,
                      *,
                      md5hash: str = None, url=None) -> tuple[bool | str]:
    ''' Установка файла с именем file в качестве актуального, в случае передачи
    хэша и урл считаем за получение задания с сервера на немедленную проверку,
    закачку и установку файла в текущую задачу текущий файл должен иметь на
    себя ссылку в рабочем каталоги вида {display_name}_media.mp4 '''

    link = os.path.abspath(f'{machine.working_dir}/{display}_media.mp4')
    file_path = os.path.abspath(f'{machine.working_dir}/{filename}')
    err = None

    # Проверка наличия файла в рабочей директории
    if not os.path.exists(file_path):
        if url is None:
            url = f'{machine.srv_url}/files/{md5hash}'
        # Получаем файл
        print("Установщик текущего качает ", filename)
        await api_requests.get_file(machine,
                                    url=url,
                                    filename=filename)
        # Проверяем хэш
        hash_task = asyncio.create_task(get_md5(machine,
                                                filename,
                                                md5hash=md5hash))
        # Перемещаем в рабочую директорию
        hash_task.add_done_callback(
            lambda task: move_to_working_dir(task, machine))
        await hash_task

        # Должен быть ответ серверу, что хэш не есошелся
        if not hash_task.result()[0]:
            err = f'{ValueError("Hash invalid or None")}'

    # проверка наличия и корректности ссылки на файл
    if not os.path.exists(link) or os.readlink(link) != file_path:
        # Остановка сервиса проигрывания
        try:
            await asyncio.create_subprocess_exec('sudo', 'systemctl', 'stop',
                                                 machine.service_name)
            print(f"Служба {machine.service_name} успешно остановлена.")
        except Exception as e:
            err = f"Service stop error: {machine.service_name}: {type(e).__name__}"
            print(f"Ошибка при остановке службы {machine.service_name}: {e}")

        # Замена ссылки. Начало ---------------
        if display is None and machine.info['displays'] is None:
            print(False, 'ValueError: No display set')
            return (False, 'ValueError: No display set')
            # raise KeyError("No display set")
        elif display is None:
            tasks = []
            for d in machine.info['displays']:
                tasks.append(
                    asyncio.create_task(
                        set_current(machine=machine,
                                    filename=filename,
                                    display=d,
                                    md5hash=md5hash,
                                    url=url)
                        ))

            await asyncio.gather(*tasks)
        elif display not in machine.info['displays']:
            print(False, 'ValueError: No such display {display}')
            return (False, 'ValueError: No such display {display}')
        else:
            if os.path.islink(link) or os.path.exists(link):
                os.remove(link)
            os.symlink(file_path, link)

            # Обновление ссылки в бд файлов:
            current = next((task
                            for task in machine.current
                            if task.get('display', None) == display), None)
            if md5hash is None:
                md5hash = next((el['md5hash']
                                for el in machine.files
                                if el['filename'] == filename), None)
            if current:
                # Помечаем в планировщике что файл уже игрался
                machine.scheduler.sort(
                    key=lambda x: datetime.strptime(x['from'],
                                                    machine.from_date_format))
                scheduled_task = [task
                                  for task in machine.scheduler
                                  if set(current.items()).issubset(task.items())
                                  and datetime.strptime(task['from'],
                                                        machine.from_date_format
                                                        ) < datetime.today()]
                if scheduled_task:
                    scheduled_task[-1]['state'] = 'archived'
                # ------
                machine.current.remove(current)
            machine.current.append({'display': display,
                                    'filename': filename,
                                    'md5hash': md5hash})

            link_record = next((rec
                                for rec in machine.files
                                if rec['filename'] == f"{display}_media.mp4"), None)
            if link_record:
                machine.files.remove(link_record)
            machine.files.append({'filename': f"{display}_media.mp4",
                                  'md5hash': md5hash})
        # Замена ссылки. Конец ---------------------
        # Запуск сервиса проигрывания
        try:
            await asyncio.create_subprocess_exec('sudo',
                                                 'systemctl',
                                                 'start',
                                                 machine.service_name)
            print(f"Служба {machine.service_name} успешно запущена.")
        except Exception as e:
            err = f"Service start error: {machine.service_name}: {type(e).__name__}"
            print(f"Ошибка при запуске службы {machine.service_name}: {e}")

        # Обновление БД
        await save_json(machine)

    # Отправка серверу отчета об успешной замене

    result = (True, err) if err else (False, err)
    return result


if __name__ == '__main__':
    async def main():

        machine = MediaMachine()
        filename = 'f3c6e05ef707d9b2354c81fde7fe67c7.mp4'
        res = await get_md5(machine, filename, dir_path='./tmp')

        print(res)

    asyncio.run(main())
