
## command

    pip install index.py Jinja2 gunicorn uvicorn
    gunicorn -k uvicorn.workers.UvicornWorker index_file:app


## systemd service

    adduser index_file_user

    [Unit]
    Description=index_file daemon
    After=network.target

    [Service]
    Type=notify
    User=index_file_user
    Group=index_file_user
    RuntimeDirectory=/home/index_file_user
    WorkingDirectory=/home/index_file_user
    ExecStart=/usr/local/bin/gunicorn -k uvicorn.workers.UvicornWorker index_file:app
    ExecReload=/bin/kill -s HUP $MAINPID
    KillMode=mixed
    TimeoutStopSec=5
    PrivateTmp=true

    [Install]
    WantedBy=multi-user.target


## Nginx

    location / {
        proxy_pass http://127.0.0.1:8000;
    }

    location /path_/ {
        internal;
        alias /home/index_file_user/www;
    }
