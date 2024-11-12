FROM python:3.10-bullseye

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1  

RUN pip install --upgrade pip

# create app directory.
RUN mkdir -p /usr/appserver
WORKDIR /usr/appserver

# install requirement
COPY requirements.txt .
RUN pip install -r requirements.txt  

# copy all the code
COPY . .

EXPOSE 9000

ENTRYPOINT [ "./run.sh" ]

CMD [ "serve" ]
