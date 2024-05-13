import json
import os
import aiofiles
import aiohttp
from models.machine import MediaMachine


async def get_file(
        machine: MediaMachine,
        url,
        filename,
        chunk_write_size=1024,):

    file_handling_event = machine.get_event(filename)
    await file_handling_event.wait()
    file_handling_event.clear()

    downloading_path = os.path.abspath(f'{machine.downloading_dir}/{filename}')
    resume_mode = os.path.exists(downloading_path)
    resume_byte_pos = os.path.getsize(downloading_path) if resume_mode else 0

    async with aiohttp.ClientSession() as session:
        async with session.get(
                            url,
                            headers={"Range": f"bytes={resume_byte_pos}-"}
                            ) as response:

            if response.status // 400:
                print(f"No such file: {filename}, status: {response.status}")
                file_handling_event.set()
                return

            elif response.status == 206 or not resume_mode:
                mode = 'ab' if resume_mode else 'wb'
                async with aiofiles.open(downloading_path, mode) as file:
                    async for chunk in response.content.iter_chunked(chunk_write_size):
                        await file.write(chunk)
                print("Download completed")
            else:
                print("Failed to resume download")

    file_handling_event.set()


async def request_tasks(url, *, headers=None, params=None) -> dict | str:

    _headers = {'Content-Type': 'application/json'}
    if headers:
        _headers.update(headers)

    async with aiohttp.ClientSession() as session:
        async with session.get(url,
                               headers=_headers,
                               params=params,
                               allow_redirects=True) as response:

            if response.status in (200, 201):
                tasks = json.loads(await response.json())
                return tasks.get('json', tasks)

    return f'Response status error: {response.status}'


async def send_response(data=None, *,  url=None, headers=None, params=None):



    if url is None or url == 'json':
        # url = f"{machine.srv_url}/device/{machine.info['serial']}"
        print("Эту ерунду я пошлю на сервер:")
        data = json.dumps(data, indent=2)
        print(data)
        return False

    _headers = {'Content-Type': 'application/json'}
    if headers:
        _headers.update(headers)

    async with aiohttp.ClientSession() as session:

        async with session.post(url,
                                json=data,
                                headers=_headers,
                                params=params,
                                allow_redirects=True) as response:

            print(response.url, await response.text())
            print("data=",data)
            #if response.status in (200, 201):
            ##    tasks = await response.json()
            #    return tasks.get('json', tasks)

    return f'Response status error: {response.status}'
