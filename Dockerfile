FROM --platform=$BUILDPLATFORM python:3.11-alpine AS builder

EXPOSE 8000

WORKDIR /app 

COPY requirements.txt /app

RUN pip3 install --upgrade pip && pip3 install -r requirements.txt --no-cache-dir

COPY . /app 

ENTRYPOINT ["python3"] 

CMD ["manage.py", "runserver", "0.0.0.0:8000"]
