from fastapi import FastAPI, HTTPException, Header, Request, Response, status
from fastapi import responses
import aiofiles
import json
from models.endpoints import MediaMachine
import os

app = FastAPI()

@app.get("/test/{sn}")
async def test_request(request: Request, sn):
    print(request.headers, sn)
    return  sn

@app.get("/device/{sn}")
async def task_response(sn):
    schedule_json = os.path.abspath(f'./datafiles/devices/{sn}/schedule.json')
    if not os.path.exists(f'./datafiles/devices/{sn}'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Device not found')
    elif not os.path.exists(schedule_json):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='No info found')
    else:
        async with aiofiles.open(schedule_json) as schedule:
            return await schedule.read()


@app.post("/device/{sn}")
async def task_response(sn: str, machine: MediaMachine):
    info_json = os.path.abspath(f'./datafiles/devices/{sn}/info.json')
    if not os.path.exists(f'./datafiles/devices/{sn}'):
        raise HTTPException(status_code=404, detail='Device not found')
    else:
        async with aiofiles.open(info_json, mode="w") as info:
            await info_json.write(json.dumps(machine))
        return Response(status_code=status.HTTP_200_OK, content="Thanks")


@app.get("/files/{md5hash}")
async def files_response(request: Request, md5hash):
    file = os.path.abspath(f'./datafiles/{md5hash}.mp4')
    if not os.path.exists(file):
        raise HTTPException(status_code=404, detail='No file found')

    if request.headers.get('Range') is not None:
        start_bytes =  int(request.headers.get('Range').strip('bytes=').split("-",1)[0])
        async def iter(file):
            async with aiofiles.open(file, mode='rb') as videofile:
                await videofile.seek(start_bytes)
                return await videofile.read()
        return responses.Response(content=await iter(file), status_code=status.HTTP_206_PARTIAL_CONTENT, media_type="video/mp4")

    return responses.FileResponse(file, filename = f'{md5hash}.mp4')

#test