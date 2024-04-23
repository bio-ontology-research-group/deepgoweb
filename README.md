# DeepGO web interface

Webinterface for the DeepGO function prediction method. A demo is available at http://deepgo.bio2vec.net.


# Commands to run in development mode:

- Start server:

```
python manage.py runserver
```

- Start Celery (in another terminal):

```
celery worker -A deepgoweb -l info
```
