# MusicSync Backend
Totaly not ready for prime time yet!

## Running it
You will need python3, nginx with some modules and a mongodb server

### Setting up python enviroment
```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Nginx
Nginx needs to have the [push-stream](https://github.com/wandenberg/nginx-push-stream-module)
compiled into it so that the event sending code would work

There is a sample nginx config in `nignx.conf` file that can be used for development

nginx server can be ran like this:
```
sudo nginx -p `pwd` -c nginx.conf
```


