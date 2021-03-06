from flask import request

from app.attribute_authority.utils import create_attributes, parse_attr_list, get_private_key_based_on_owner, create_private_key
from app.app_setup import db
from app.attribute_authority import attr_authority
from app.attribute_authority.utils import serialize_charm_object, create_cp_abe, create_pairing_group, deserialize_charm_object
from app.auth.utils import require_api_token
from app.consts import ATTR_LIST_MISSING_ERROR_MSG, \
    INVALID_ATTR_LIST_ERROR_MSG, MESSAGE_MISSING_ERROR_MSG, POLICY_STRING_MISSING_ERROR_MSG, CIPHERTEXT_MISSING_ERROR_MSG, COULD_NOT_DECRYPT_ERROR_MSG, \
    INVALID_OWNER_API_USERNAME_ERROR_MSG, OWNER_API_USERNAME_MISSING_ERROR_MSG, API_USERNAME_MISSING_ERROR_MSG, DEVICE_ID_MISSING_ERROR_MSG, \
    INCORRECT_API_USERNAME_ERROR_MSG, API_USERNAME_ALREADY_PRESENT_MSG
from app.models.models import AttrAuthUser, MasterKeypair, PrivateKey
from app.utils import http_json_response, check_missing_request_argument

"""
    Lots of people working in cryptography have no deep concern with real application issues.
    They are trying to discover things clever enough to write papers about.
        -- Whitfield Diffie
"""


@attr_authority.route('/set_username', methods=['POST'])
@require_api_token("attr_auth")
def set_username():
    user = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))
    api_username = request.form.get("api_username", None)

    arg_check = check_missing_request_argument((api_username, API_USERNAME_MISSING_ERROR_MSG))
    if arg_check is not True:
        return arg_check

    if AttrAuthUser.get_by_user_name(api_username) is not None:
        return http_json_response(False, 400, **{"error": API_USERNAME_ALREADY_PRESENT_MSG})

    user.api_username = api_username
    db.session.add(user)
    db.session.commit()

    return http_json_response()


@attr_authority.route('/setup', methods=['GET'])  # NOTE: This is not idempotent
@require_api_token("attr_auth")
def key_setup():
    pairing_group = create_pairing_group()
    cp_abe = create_cp_abe()

    public_key, master_key = cp_abe.setup()

    # "store keypair in DB"
    user = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))

    serialized_public_key = serialize_charm_object(public_key, pairing_group)
    serialized_master_key = serialize_charm_object(master_key, pairing_group)
    user.master_keypair = MasterKeypair(data_public=serialized_public_key,
                                        data_master=serialized_master_key)
    db.session.add(user)
    db.session.commit()

    # return pk, msk
    return http_json_response(**{'public_key': serialized_public_key.decode("utf-8")})


@attr_authority.route('/user/keygen', methods=['POST'])
@require_api_token("attr_auth")
def keygen():
    data_owner = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))
    attr_list = request.form.get("attr_list", None)
    api_username = request.form.get("api_username", None)
    device_id = request.form.get("device_id", None)

    arg_check = check_missing_request_argument(
        (attr_list, ATTR_LIST_MISSING_ERROR_MSG),
        (api_username, API_USERNAME_MISSING_ERROR_MSG),
        (device_id, DEVICE_ID_MISSING_ERROR_MSG))
    if arg_check is not True:
        return arg_check

    receiver = AttrAuthUser.get_by_user_name(api_username)
    if receiver is None:
        return http_json_response(False, 400, **{"error": INCORRECT_API_USERNAME_ERROR_MSG})

    attr_list = parse_attr_list(attr_list)
    if not attr_list:
        return http_json_response(False, 400, **{"error": INVALID_ATTR_LIST_ERROR_MSG})

    serialized_private_key = create_private_key(data_owner.master_keypair.data_master,
                                                data_owner.master_keypair.data_public,
                                                attr_list)

    # delegate to receiver of generated key
    old_key = next((k for k in receiver.private_keys if k.challenger == data_owner and k.device_id == int(device_id)), None)
    if old_key:
        db.session.delete(old_key)
    receiver.private_keys.append(PrivateKey(data=serialized_private_key,
                                            challenger=data_owner,
                                            device_id=device_id,
                                            attributes=create_attributes(attr_list)))
    db.session.commit()
    return http_json_response()


@attr_authority.route('/device/keygen', methods=['POST'])
@require_api_token("attr_auth")
def device_keygen():
    data_owner = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))
    attr_list = request.form.get("attr_list", None)

    arg_check = check_missing_request_argument(
        (attr_list, ATTR_LIST_MISSING_ERROR_MSG))
    if arg_check is not True:
        return arg_check

    attr_list = parse_attr_list(attr_list)
    if not attr_list:
        return http_json_response(False, 400, **{"error": INVALID_ATTR_LIST_ERROR_MSG})

    serialized_private_key = create_private_key(data_owner.master_keypair.data_master,
                                                data_owner.master_keypair.data_public,
                                                attr_list)

    # delegate to receiver of generated key
    return http_json_response(private_key=serialized_private_key.decode("utf-8"))


@attr_authority.route('/user/retrieve_private_keys', methods=['POST'])
@require_api_token("attr_auth")
def retrieve_private_keys():
    user = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))

    private_keys = [{
        "data": key.data.decode("utf-8"),
        "key_update": key.key_update,
        "attributes": [a.value for a in key.attributes],
        "challenger_id": key.challenger_id,
        "device_id": key.device_id,

    } for key in user.private_keys]
    return http_json_response(**{'private_keys': private_keys})


@attr_authority.route('/encrypt', methods=['GET'])
@require_api_token("attr_auth")
def encrypt():
    data_owner = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))
    plaintext = request.args.get("message", None)
    policy_string = request.args.get("policy_string", None)

    arg_check = check_missing_request_argument(
        (plaintext, MESSAGE_MISSING_ERROR_MSG),
        (policy_string, POLICY_STRING_MISSING_ERROR_MSG))
    if arg_check is not True:
        return arg_check

    pairing_group = create_pairing_group()
    cp_abe = create_cp_abe()
    public_key = deserialize_charm_object(data_owner.master_keypair.data_public, pairing_group)
    ciphertext = cp_abe.encrypt(public_key, plaintext, policy_string)

    # return ciphertext
    return http_json_response(**{'ciphertext': serialize_charm_object(ciphertext, pairing_group).decode("utf-8")})


@attr_authority.route('/decrypt', methods=['GET'])  # NOTE: ciphertext might be too long for url
@require_api_token("attr_auth")
def decrypt():
    decryptor = AttrAuthUser.get_using_jwt_token(request.headers.get("Authorization", None))
    owner_api_username = request.args.get("api_username", None)
    serialized_ciphertext = request.args.get("ciphertext", None)

    arg_check = check_missing_request_argument(
        (owner_api_username, OWNER_API_USERNAME_MISSING_ERROR_MSG),
        (serialized_ciphertext, CIPHERTEXT_MISSING_ERROR_MSG))
    if arg_check is not True:
        return arg_check

    pairing_group = create_pairing_group()
    cp_abe = create_cp_abe()

    data_owner = db.session.query(AttrAuthUser) \
        .filter(AttrAuthUser.api_username == owner_api_username) \
        .first()
    if data_owner is None:
        return http_json_response(False, 400, **{"error": INVALID_OWNER_API_USERNAME_ERROR_MSG})

    public_key = deserialize_charm_object(data_owner.master_keypair.data_public, pairing_group)
    private_key = deserialize_charm_object(get_private_key_based_on_owner(decryptor, data_owner).data, pairing_group)
    ciphertext = deserialize_charm_object(str.encode(serialized_ciphertext), pairing_group)

    try:
        plaintext = cp_abe.decrypt(public_key, private_key, ciphertext)
    except:
        return http_json_response(False, 400, **{"error": COULD_NOT_DECRYPT_ERROR_MSG})

    # return plaintext
    return http_json_response(**{'plaintext': plaintext.decode("utf-8")})
