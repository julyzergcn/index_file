from pathlib import Path
from time import strftime, localtime
from asyncio import to_thread
from shutil import rmtree
from urllib.parse import quote

from indexpy import (
    Index, request, HttpResponse, RedirectResponse,
    HTMLResponse, HTTPException, FileResponse)
from jinja2 import Template


USE_NGINX = False

ROOT = Path('./www')
ROOT.mkdir(exist_ok=True)

PASSWORD = 'passwd'

TPL = Template(open('./template.html').read())

app = Index()


def login_required(endpoint):
    async def wrapper():
        password = request.cookies.get('password')
        if password != PASSWORD:
            raise HTTPException(400)
        return await endpoint()
    return wrapper


def write_file(path, file):
    with open(path, 'wb') as f:
        f.write(file)


def parse_path(path):
    if path is None or '..' in path or '~' in path:
        raise HTTPException(400)
    if path == 'Home':
        path = ''
    return path


# https://stackoverflow.com/questions/1094841/get-human-readable-version-of-file-size
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


@app.router.http.post("/api/login/", name="login")
async def login():
    form = await request.form
    password = form.get('password')
    if password == PASSWORD:
        res = RedirectResponse('/', 302)
        res.set_cookie('password', password)
        return res
    raise HTTPException(400)


@app.router.http.post("/api/logout/", name="logout")
async def logout():
    res = RedirectResponse('/', 302)
    res.delete_cookie('password')
    return res


@app.router.http.post("/api/directory/", name="new_directory", middlewares=[login_required])
async def new_directory():
    form = await request.form

    path = parse_path(form.get('path'))
    dir_name = parse_path(form.get('directory'))
    if len(dir_name) > 128:
        raise HTTPException(400)
    real_path = ROOT / path / dir_name
    real_path.mkdir(parents=True, exist_ok=True)

    return RedirectResponse('/'+path, 302)


@app.router.http.post("/api/file/", name="new_file", middlewares=[login_required])
async def new_file():
    form = await request.form

    path = parse_path(form.get('path'))

    file = form.get('file')
    if file is None:
        raise HTTPException(400)

    real_path = ROOT / path / file.filename
    contents = form["file"].read()

    await to_thread(write_file, path=real_path, file=contents)
    return RedirectResponse('/'+path, 302)


@app.router.http.post("/api/delete/", name="del_file", middlewares=[login_required])
async def del_file():
    form = await request.form

    path = parse_path(form.get('path'))

    file = form.get('file')
    if file is None:
        raise HTTPException(400)

    real_path = ROOT / path / file
    if real_path.is_file():
        real_path.unlink(True)
    else:
        rmtree(real_path)

    return RedirectResponse('/'+path, 302)


@app.router.http.get("/", name="home")
@app.router.http.get("/{path:any}", name="index")
async def index():
    path = parse_path(request.path_params.get("path") or '')

    filepath = Path(path)
    real_path = ROOT / filepath

    if not real_path.exists():
        raise HTTPException(400)

    if real_path.is_file():
        if USE_NGINX:
            return HttpResponse(
                headers={
                    'X-Accel-Redirect': quote(f'/path_/{path}'),
                }
            )
        return FileResponse(real_path)    

    file_list = []
    dir_list = []
    for file in real_path.iterdir():
        file_stat = file.stat()
        if file.is_dir():
            dir_list.append({
                'name': file.name,
                'path': str(file.relative_to(ROOT)),
                'size': 0,
                'modified': strftime('%Y-%m-%d %H:%M:%S', localtime(file_stat.st_mtime)),
            })
        else:
            file_list.append({
                'name': file.name,
                'path': str(file.relative_to(ROOT)),
                'size': sizeof_fmt(file_stat.st_size),
                'modified': strftime('%Y-%m-%d %H:%M:%S', localtime(file_stat.st_mtime)),
            })

    dir_list.extend(file_list)

    url = ''
    parts = []
    for part in filepath.parts:
        url += '/'+part
        parts.append({
            'url': url,
            'name': part
        })

    context = {
        'current': path,
        'file_list': dir_list,
        'parts': parts
    }

    password = request.cookies.get('password')
    if password == PASSWORD:
        context.update({'is_login': True})

    return HTMLResponse(TPL.render(**context))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, interface="asgi3", port=5000, debug=True)
