import os
import atexit
import datetime
from dotenv import load_dotenv
from typing import List

from sqlalchemy import create_engine, String, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, relationship

load_dotenv()

DB_NAME = os.getenv('DB_NAME', 'adverts.db')

engine = create_engine(f'sqlite:///{DB_NAME}?charset=utf8')
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100))
    adverts: Mapped[List['Advert']] = relationship(back_populates="owner")

    @property
    def json(self):
        return {'id': self.id, 'name': self.name, 'email': self.email}


class Advert(Base):
    __tablename__ = 'advert'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    owner_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    owner: Mapped[User] = relationship(User, back_populates="adverts")

    @property
    def json(self):
        return {
            'id': self.id,
            'title': self.title,
            'note': self.note,
            'created_at': self.created_at,
            'owner': self.owner.name
        }


Base.metadata.create_all(bind=engine)
atexit.register(engine.dispose)