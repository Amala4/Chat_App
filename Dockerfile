FROM python:3.11
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV DJANGO_SETTINGS_MODULE=jbl_chat.settings
RUN mkdir /code
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install -r requirements.txt
COPY . /code/
EXPOSE 8000
CMD ["gunicorn", "jbl_chat.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "5", "--threads", "3", "--timeout", "300"]