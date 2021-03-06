"""
Сервер для приема и отправки метрик
"""
import asyncio
from collections import defaultdict
from operator import itemgetter
import re
import sys

#TODO: обвешать тестами с использованием моего класса Client.
#TODO: заменить все шаблоны строк на _.format(key,value) чтобы если что заменить
#в одном месте протокол

#----------------=======Хранилище=======-----------------------------
class DictInStorage(dict):
    """
    Также перегружен метод __str__, 
    чтобы соответствовать протоколу отправки запросов
    """
    def __init__(self, key, *args, **kwargs):
        self.upperkey = key
        super().__init__(*args, **kwargs)

    def __str__(self):
        return '\n'.join([f"{self.upperkey} {val} {time}" for time, val in self.items()])

        
class Storage(defaultdict):
    """
    Обёртка класса defaultdict, с перегруженным __str__ чтобы печатать в
    соответствии с протоколом запроса. В отличие от defaultdict, вызывает
    производящую функцию с **одним** аргументом, а не с нулем
    """
    def __init__(self):
        super().__init__(DictInStorage)

    def __missing__(self, key):
        """Вызывается при генерации значения по несуществующему ключу"""
        val = self.default_factory(key)
        self.setdefault(key, val)
        return val 

    def __str__(self): 
        triples = sorted(
            [(k,v,t) for k in self.keys() for t, v in self[k].items()], 
            key=itemgetter(2))
        resp = '\n'.join([f"{k} {v} {t}" for k,v,t in triples])
        return '\n' + resp if resp else '' 


storage = Storage()


#---------------==========Константы и шаблоны=========-------------------
PUT_PATTERN = re.compile(r'put \S+ \d+.?\d* \d+\n')
GET_PATTERN = re.compile(r'get \S+\n')
BY_SPACE = re.compile(r'\s+')
RESPONSE_TEMPLATE = "{}\n{}\n\n"


#---------------==========Сервер===========-------------------------------
async def handle_request(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    buff=4096, cd='utf8') -> None:

    while True:
        request = await reader.read(buff)
        request = request.decode(cd)

        addr = writer.get_extra_info('peername')
        print(f"Received {request!r} from {addr!r}")
        if not request:
            break
        else:
            if PUT_PATTERN.match(request):
                response = handle_put(request)
            elif GET_PATTERN.match(request):
                response = handle_get(request)
            else:
                response = raise_error()

            print(f"Send {response} at {addr}")
            writer.write(response.encode())
            await writer.drain()

    print(f"Closing connection with {addr}")
    writer.close()


def handle_put(request: str) -> str:
    _, key, value, timestamp, _ = BY_SPACE.split(request)
    storage[key][int(timestamp)] = float(value)
    response = 'ok\n\n' 
    return response 


def handle_get(request: str) -> str:
    _, key, _ = BY_SPACE.split(request)

    if key == '*':
        response = "ok" + f"{storage}" + "\n\n"
    else:
        cont = storage[key] 
        if (cont):
            response = "ok\n" + f"{cont}"  + "\n\n"
        else:
            response = "ok\n\n"
            x = storage.pop(key)
            del x
    return response 


def raise_error() -> str:
    return "error\nwrong command\n\n" 


def run_server(host: str, port: int) -> None:
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(
                    handle_request, host, 
                    port, loop=loop)

    server = loop.run_until_complete(coro)
    addr = server.sockets[0].getsockname()
    print(f'Starting server on {addr}')
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print('Stopping server')
        server.close()


if __name__ == '__main__':
    try:
        host, port = sys.argv[1].split(':')
    except Exception:
        hostport = input('host:port ::')
        host, port = hostport.split(':')
    run_server(host, port)