from app.app_setup import db


class MixinGetById:
    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def get_by_id(cls, device_id):
        return db.session.query(cls).filter(cls.id == device_id).first()


class MixinGetByAccessToken:
    access_token = db.Column(db.String(200), unique=True, nullable=False)

    @classmethod
    def get_by_access_token(cls, token):
        return db.session.query(cls).filter(cls.access_token == token).first()


class MixinAsDict:
    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}