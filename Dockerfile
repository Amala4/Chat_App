FROM python:3.10.2
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
RUN mkdir /code
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install -r requirements.txt
COPY . /code/
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "jbl_chat.wsgi:application"]
