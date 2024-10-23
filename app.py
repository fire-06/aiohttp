import pydantic
from flask import Flask, jsonify, request
from flask.views import MethodView
from sqlalchemy.exc import IntegrityError
from models import Session, Advert, User
from shema import CreateAdvert, CreateUser

app = Flask('adverts_app')


class HttpError(Exception):
    def __init__(self, status_code: int, description: str):
        self.status_code = status_code
        self.description = description


@app.errorhandler(HttpError)
def error_handler(error: HttpError):
    return jsonify({'error': error.description}), error.status_code


@app.before_request
def before_request():
    request.session = Session()


@app.after_request
def after_request(response):
    request.session.close()
    return response


def get_advert_by_id(advert_id: int) -> Advert:
    advert = request.session.get(Advert, advert_id)
    if advert is None:
        raise HttpError(404, 'Advert not found')
    return advert


def validate(schema_class, json_data):
    try:
        return schema_class(**json_data).dict(exclude_unset=True)
    except pydantic.ValidationError as err:
        error = err.errors()[0]
        error.pop('ctx', None)
        raise HttpError(400, error)


def add_instance(instance, conflict_message: str):
    try:
        request.session.add(instance)
        request.session.commit()
    except IntegrityError:
        raise HttpError(409, conflict_message)
    return instance


class AdvertView(MethodView):
    def get(self, advert_id: int):
        advert = get_advert_by_id(advert_id)
        return jsonify(advert.json)

    def post(self):
        json_data = validate(CreateAdvert, request.json)
        advert = Advert(**json_data)
        add_instance(advert, 'Advert already exists')
        return jsonify(advert.json), 201

    def delete(self, advert_id: int):
        advert = get_advert_by_id(advert_id)
        request.session.delete(advert)
        request.session.commit()
        return jsonify({'status': 'success'})


class UserView(MethodView):
    def get(self, user_id: int):
        user = request.session.get(User, user_id)
        if user is None:
            raise HttpError(404, "User not found")
        return jsonify(user.json)

    def post(self):
        json_data = validate(CreateUser, request.json)
        user = User(**json_data)
        add_instance(user, 'User already exists')
        return jsonify(user.json), 201


app.add_url_rule('/advert', view_func=AdvertView.as_view('advert_view'), methods=['POST'])
app.add_url_rule('/advert/<int:advert_id>', view_func=AdvertView.as_view('advert_detail'), methods=['GET', 'DELETE'])
app.add_url_rule('/user', view_func=UserView.as_view('user_view'), methods=['POST'])
app.add_url_rule('/user/<int:user_id>', view_func=UserView.as_view('user_detail'), methods=['GET'])

if __name__ == '__main__':
    app.run()