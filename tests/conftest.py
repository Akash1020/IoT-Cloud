import json
import os
import re
import warnings
import pytest
from click.testing import CliRunner
from sqlalchemy.exc import SADeprecationWarning

from app.app_setup import create_app, db
from app.models.models import UserDevice


@pytest.fixture(scope="module")
def runner():
    return CliRunner(echo_stdin=True)


@pytest.fixture(scope="module")
def client():
    warnings.filterwarnings("ignore", category=SADeprecationWarning)
    app = create_app(os.getenv('TESTING_ENV', "testing"))
    return app.test_client()


@pytest.fixture(scope="module")
def app_and_ctx():
    warnings.filterwarnings("ignore", category=SADeprecationWarning)
    app = create_app(os.getenv('TESTING_ENV', "testing"))
    ctx = app.app_context()
    ctx.push()
    yield app, ctx
    db.drop_all()


@pytest.fixture(scope="module")
def application():
    warnings.filterwarnings("ignore", category=SADeprecationWarning)
    app = create_app(os.getenv('TESTING_ENV', "testing"))
    yield app
    db.drop_all()


@pytest.fixture(scope="session")
def access_token():
    return "5c36ab84439c45a3719644c0d9bd7b31929afd9f"


@pytest.fixture(scope="session")
def access_token_two():
    return "5c36ab84439c55a3c196f4csd9bd7b319291239f"


@pytest.fixture(scope="session")
def access_token_three():
    return '5c36ab84439c55a3c196f4csd9bd7b3d9291f39g'


@pytest.fixture(scope="session")
def access_token_four():
    return '5c36ab84439gden3c196f4csd9bd7b3d9291f39g'


@pytest.fixture(scope="session")
def master_key_user_one():  # `b'...'.decode("utf-8")`
    return 'eJyNUstOxDAM/JWo5x7iNC/zKwhVXVTBoQekLkhotf+Ox45hjxzSJs7Enhn7Nl326zY9hdu0rq/Hdp7rKqfp8n3dz2kOEv3ajs9do8+5z6HIqnUOlEgO2MQ0h8ZyyHMAohYJEm5l0+UyN9' \
           'njLyCWfYsAMJ42fBaBIdwMSkmwlUcSgJkts9ZUCB42ibQM2IKIUumeFOkrYb3cRcZbWrfj4/3fSks0peDVQRuUowobUYpSupdBl6LUYhCSQ19Mb1uMegcrGoxhSqEhMEV71avpqm4KbIKf' \
           'FfUF1LOn4V+Z2RsRByMQUcJlWNXkunpx7RPagWLMI4oMxdupHkOJnpAGUoiSNRW0G5muohfV3HloZlKjogMWGw0lUuxf/BGgelEtbfcuR7eouGhQivwwItSHDXAMliqWjTCS/TmTbfB8EN' \
           'UGtBcBomxPdY1xuf8AJSqbbw=='


@pytest.fixture(scope="session")
def master_key_user_two():  # `b'...'.decode("utf-8")`
    return 'eJyNUrtuwzAM/JXAcwZRFiWqv1IUhlMY7eChgNMCRZB/D4+kUGTrQJmijo87+jZdtus6vZxu07K87+txLIvepsvvdTum80mjP+v+vVn0tcj5xGqUEo6qB+nRzMnqdDV9ErWuVqv7PKvfAN' \
           'KjqLFaY9QQz2K9SAYCJQoccUdq5BFRdAB2jgArpOlrRxHc0VK/1eztrhQ+8rLuX5//ZsnJWfo8eojWlxJjsEUVUmaPoiuGbOJIkG0ApfIXdLHSPMIUGFMNQmTyhsbdVEGmuI488tCvxEOb' \
           'Q/4a6OiRvDT20ELVOnYmGgA9ouIFDBEkbDxA2TbTXFyOIGXjRJ6DIl1iX1iGse6D0ROJ2JK/zC4c5eRM6li+uIo9YrWPJWN+Hk5wp9S9sAlZne34FRAvPWZsrgbukkIF+zX5+T+5PwBHm5k5'


@pytest.fixture(scope="session")
def attr_auth_access_token_one():
    return '54agPr4edV9PvyyBNkjFfA))'


@pytest.fixture(scope="session")
def attr_auth_access_token_two():
    return '7jagPr4edVdgvyyBNkjdaQ))'


@pytest.fixture(scope='function')
def setup_user_device_public_key(request):
    device_id, user_id, pk, db_name = request.param
    warnings.filterwarnings("ignore", category=SADeprecationWarning)
    app = create_app(os.getenv('TESTING_ENV', "testing"))
    with app.app_context():
        _swap_db(app, "testing", db_name)
        _set_user_device_public_key(device_id, user_id, pk)
        _swap_db(app, db_name, "testing")
    yield None
    with app.app_context():
        _swap_db(app, "testing", db_name)
        _set_user_device_public_key(device_id, user_id, None)
        _swap_db(app, db_name, "testing")


@pytest.fixture(scope='function')
def reset_tiny_db(request):
    path = request.param
    if os.path.isfile(path):
        os.remove(path)
    yield None
    os.remove(path)


def _swap_db(app, current, new):
    app.config["SQLALCHEMY_DATABASE_URI"] = re.sub(f"{current}$", new, app.config["SQLALCHEMY_DATABASE_URI"])


def _set_user_device_public_key(device_id, user_id, pk):
    user_device = UserDevice.get_by_ids(device_id, user_id)
    user_device.device_public_session_key = pk
    db.session.add(user_device)
    db.session.commit()


@pytest.fixture(scope='function')
def col_keys():
    data = {
        "device_id": "23",
        "shared_key": "aefe715635c3f35f7c58da3eb410453712aaf1f8fd635571aa5180236bb21acc",
        "action:name": "a70c6a23f6b0ef9163040f4cc02819c22d7e35de6469672d250519077b36fe4d",
        "device_type:description": "2c567c6fde8d29ee3c1ac15e74692089fdce507a43eb931be792ec3887968d33",
        "device_data:added": "8dabfaf75c380f03e95f55760af02dc84026654cf2019d6da44cc69f600ba8f7",
        "device_data:num_data": "3130d649f90006ef90f5c28fd486a6e748ffc35bad4981799708a411f7acaa60",
        "device_data:data": "af785b829c4502286f5abec3403b43324971acfdb22fd80007216e8fa1abbf2e",  # TODO change to ABE Key
        "device_data:tid": "9692e6525c19e6fa37978626606534015cd120816a28b501bebec142d86002b2",
        "device:name": "ae89ebdb00d48b6e2aca3218213888aff3af9915831b9cdde8f82b709fd8802e",
    }
    return data


def assert_got_error_from_post(client, url, data, error_code, error_string="", follow_redirects=True):
    response = client.post(url, query_string=data, follow_redirects=follow_redirects)
    assert response.status_code == error_code
    json_data = json.loads(response.data.decode("utf-8"))
    if error_string != "":
        assert json_data["error"] == error_string


def assert_got_data_from_post(client, url, data_in, follow_redirects=True, **data_out):
    response = client.post(url, query_string=data_in, follow_redirects=follow_redirects)
    assert response.status_code == 200
    json_data = json.loads(response.data.decode("utf-8"))
    for k, v in data_out.items():
        assert json_data[k] == v


def get_data_from_post(client, url, data, follow_redirects=True):
    response = client.post(url, query_string=data, follow_redirects=follow_redirects)
    json_data = json.loads(response.data.decode("utf-8"))
    return response.status_code, json_data
