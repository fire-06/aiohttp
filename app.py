import os
import pydantic
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from models import Advert, User, Base
from shema import CreateAdvert, CreateUser
from typing import Callable, Awaitable
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv('DB_NAME', 'adverts.db')

DATABASE_URL = f"sqlite+aiosqlite:///{DB_NAME}"
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

app = web.Application()

# Обработчик ошибок
class HttpError(web.HTTPException):
    def __init__(self, status_code: int, reason: str):
        self.status_code = status_code
        super().__init__(reason=reason)


async def error_middleware(app, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
    async def middleware_handler(request):
        try:
            response = await handler(request)
            return response
        except HttpError as err:
            return web.json_response({'error': err.reason}, status=err.status_code)

    return middleware_handler

app.middlewares.append(error_middleware)


async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_session(request: web.Request):
    session = request['db']
    await session.close()


async def db_session_middleware(app: web.Application, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
    async def middleware_handler(request: web.Request) -> web.StreamResponse:
        async with AsyncSessionLocal() as session:
            request['db'] = session
            response = await handler(request)
            await close_session(request)
            return response

    return middleware_handler

app.middlewares.append(db_session_middleware)


async def get_advert_by_id(request: web.Request, advert_id: int) -> Advert:
    session = request['db']
    advert = await session.get(Advert, advert_id)
    if not advert:
        raise HttpError(status_code=404, reason='Advert not found')
    return advert


def validate(schema_class, json_data):
    try:
        return schema_class(**json_data).dict(exclude_unset=True)
    except pydantic.ValidationError as err:
        error = err.errors()[0]
        error.pop('ctx', None)
        raise HttpError(400, error)


async def add_instance(request, instance, conflict_message: str):
    session = request['db']
    try:
        session.add(instance)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HttpError(409, conflict_message)
    return instance


class AdvertView(web.View):
    async def get(self):
        advert_id = int(self.request.match_info['advert_id'])
        advert = await get_advert_by_id(self.request, advert_id)
        return web.json_response(advert.json)

    async def post(self):
        json_data = validate(CreateAdvert, await self.request.json())
        advert = Advert(**json_data)
        advert = await add_instance(self.request, advert, 'Advert already exists')
        return web.json_response(advert.json, status=201)

    async def delete(self):
        advert_id = int(self.request.match_info['advert_id'])
        advert = await get_advert_by_id(self.request, advert_id)
        session = self.request['db']
        await session.delete(advert)
        await session.commit()
        return web.json_response({'status': 'success'})


class UserView(web.View):
    async def get(self):
        user_id = int(self.request.match_info['user_id'])
        session = self.request['db']
        user = await session.get(User, user_id)
        if not user:
            raise HttpError(404, "User not found")
        return web.json_response(user.json)

    async def post(self):
        json_data = validate(CreateUser, await self.request.json())
        user = User(**json_data)
        user = await add_instance(self.request, user, 'User already exists')
        return web.json_response(user.json, status=201)


app.router.add_view('/advert', AdvertView, name='advert_view')
app.router.add_view('/advert/{advert_id:\d+}', AdvertView, name='advert_detail')
app.router.add_view('/user', UserView, name='user_view')
app.router.add_view('/user/{user_id:\d+}', UserView, name='user_detail')


if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8080)
