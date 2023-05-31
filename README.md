# grm-backend

## Deployment

### Requirements and installation
1. Ubuntu 20.04/Hhigher 
2. Python 10 or Higher
3. apt install python3.10-venv

clone to the server	
`git clone  https://github.com/victor-abz/grm-backend.git`
`cd grm-backend/`

Install Postgres
`sudo apt install postgresql postgresql-contrib`
Create GRM Database
`sudo -u postgres psql`
`CREATE DATABASE grm_database_name;`


Create Postgres USer:
`CREATE USER grm_db_user WITH PASSWORD 'Your Postgres Pwd';` 
`GRANT ALL PRIVILEGES ON DATABASE grm TO grm;`

Generate a Python3 Virtual Environment 

`python3 -m venv venv` 

Activate the python environment
`source venv/bin/activate`

`sudo apt-get install --reinstall libpq-dev`  -- for some psycopg2-binary related errors
`sudo apt-get install gcc` 
`sudo apt-get install python3-dev`
`sudo apt install libjpeg8-dev zlib1g-dev` Install these as sometime it gives error about zlib1g-dev
`pip install --ignore-installed pillow`  Install pillow -- To avoid Errors
`pip install -r requirements.txt ` -- Instll the specific GRM packages

Configure the `.env` inside the GRM folder

RUn migration
`python3.10 manage.py makemigrations`
`python3.10 manage.py migrate`

Create Superuser for GRM
`python3.10 manage.py createsuperuser`


Collect Static Files for Django App
`python3.10 manage.py collectstatic`
`cp -r ~/grm-backend/venv/lib/python3.10/site-packages/django/contrib/admin/static/admin ~/grm-backend/src/dashboard/static/`

### Nginx Configuration

`sudo apt install nginx` Instl nginx if not installed already

Create NGINX Configuration file
`sudo nano /etc/nginx/conf.d/grm-backend.conf `

```sh
server {
        listen 80;
        server_name 197.243.25.128;

        location = /favicon.ico { access_log off; log_not_found off; }
        location /static/ {
            root /root/grm-backend/src/dashboard;
        }

        location / {
            include /etc/nginx/proxy_params;
            proxy_pass http://unix:/run/gunicorn.sock;
	    # proxy_set_header Host $host;
            proxy_set_header X-Script-Name /webapp;
	}
}
```
run `sudo nginx -t` to check if your nginx config if fine



#### change user for Nginx to avoid error 403 when loading DJANGO Static Files
##### sudo nano /etc/nginx/nginx.conf

Look for the following line.

`user www-data`
In some cases, if NGINX uses root/ubuntu user, then it might be

`user root`
OR
`user ubuntu`
If you want to change it to a different system user (e.g. nginx_user) then change the above line to

`user nginx_user`
Save and close the file.

##### Restart NGINX

```
sudo service nginx restart
OR
sudo systemctl restart nginx
```

Run the following command to view the user name for NGINX

```
$ sudo ps aux| grep nginx
nginx_user  1588  0.0  0.1 162484  5634 ?        Ss   Apr29   0:02 /usr/bin/nginx
nginx_user  1597  0.0  0.1 162484  5268 ?        S    Apr29   0:00 /usr/bin/nginx
```


### Gunicorn Service
`sudo nano /etc/systemd/system/gunicorn.service`

```sh
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/grm-backend/src
ExecStart=/root/grm-backend/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          grm.wsgi:application

[Install]
WantedBy=multi-user.target
```


`sudo nano /etc/systemd/system/gunicorn.socket`
```sh
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

Start Gunicorn `sudo systemctl start gunicorn.socket`
Enable Gunicorn on startup `sudo systemctl enable gunicorn.socket`
Status Gunicor `sudo systemctl status gunicorn.socket`

Restart Nginx `sudo systemctl restart nginx`

## Key functions

### Run Manual CELERY Jobs
Run `python3.10 src/manage.py shell`
Run `from dashboard.tasks import check_issues`
Run `check_issues()`


### Create Administrative Levels
Create a CSV file Separated by `;` then use the following command

The CSV should have headers (For Rwanda):
---------
Latitude |	Longitude |	District |	Sector	Cell|
-------

`python3.10 manage.py load_administrative_levels ~/adm_levels.csv `

### Create Administrative levels in CouchDB (For Rwanda)
Run `python3.10 manage.py shell`
Run `from grm.utils import create_facilitators_per_administrative_level`
Run `create_facilitators_per_administrative_level()`

### Create Goverment Workers (For Rwanda)
Run `python3.10 manage.py shell`
Run `from authentication.utils import create_government_workers`
Run `create_government_workers()`


### Download full list of App User with Activation Code
Ru  `python3.10 manage.py shell`
Run `from authentication.utils import get_facilitators_with_code`
RUn `get_facilitators_with_code()`


### 