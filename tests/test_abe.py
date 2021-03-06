from unittest.mock import Mock

import pytest
from charm.adapters.abenc_adapt_hybrid import HybridABEnc
from charm.schemes.abenc.abenc_bsw07 import CPabe_BSW07
from charm.toolbox.pairinggroup import PairingGroup

from app.app_setup import db
from app.consts import INVALID_ATTR_LIST_ERROR_MSG, MESSAGE_MISSING_ERROR_MSG, POLICY_STRING_MISSING_ERROR_MSG, \
    CIPHERTEXT_MISSING_ERROR_MSG, COULD_NOT_DECRYPT_ERROR_MSG, INVALID_OWNER_API_USERNAME_ERROR_MSG, OWNER_API_USERNAME_MISSING_ERROR_MSG, \
    API_USERNAME_MISSING_ERROR_MSG, ATTR_LIST_MISSING_ERROR_MSG, DEVICE_ID_MISSING_ERROR_MSG, INCORRECT_API_USERNAME_ERROR_MSG, API_USERNAME_ALREADY_PRESENT_MSG
from app.attribute_authority.utils import create_pairing_group, create_cp_abe, serialize_charm_object, deserialize_charm_object, already_has_key_from_owner, \
    create_attributes, \
    replace_existing_key, parse_attr_list, get_private_key_based_on_owner, is_valid, create_private_key
from app.auth.utils import INVALID_ACCESS_TOKEN_ERROR_MSG
from app.models.models import AttrAuthUser, PrivateKey
from tests.conftest import assert_got_error_from_post, assert_got_data_from_post, get_data_from_post, \
    assert_got_error_from_get, get_data_from_get


def test_charm_crypto():
    # instantiate a bilinear pairing map
    pairing_group = PairingGroup('MNT224')

    cpabe = CPabe_BSW07(pairing_group)
    hyb_abe = HybridABEnc(cpabe, pairing_group)
    # run the set up
    (pk, msk) = hyb_abe.setup()  # Public Key and Master SECRET Key

    # generate a key
    attr_list = ['U-11890454', 'D-46', 'D-46-GUEST']
    key = hyb_abe.keygen(pk, msk, attr_list)

    serialized_pk = serialize_charm_object(pk, pairing_group)
    pk = deserialize_charm_object(serialized_pk, pairing_group)

    serialized_key = serialize_charm_object(key, pairing_group)
    key = deserialize_charm_object(serialized_key, pairing_group)

    # choose a random message
    msg = "Hello World"

    # generate a ciphertext
    policy_str = '(u-11890454 OR d-46 OR d-46-GUEST)'  # evaluates to "((U-11890454 or D-46) or D-46-GUEST)" - see upper chars
    ctxt = hyb_abe.encrypt(pk, msg, policy_str)

    policy_str = '(u-1 AND d-46 AND d-46-GUEST)'  # Re-encrypted data with new policy
    ctxt2 = hyb_abe.encrypt(pk, msg, policy_str)

    # decryption
    rec_msg = hyb_abe.decrypt(pk, key, ctxt).decode("utf-8")
    with pytest.raises(Exception):
        hyb_abe.decrypt(pk, key, ctxt2)
    assert rec_msg == msg, "Failed."  # "First successfully decrypted, second not."


def test_serialize_and_deserialize_pk():
    pairing_group = create_pairing_group()
    cp_abe = create_cp_abe()

    public_key, master_key = cp_abe.setup()

    assert public_key == deserialize_charm_object(serialize_charm_object(public_key, pairing_group), pairing_group)


def test_require_attr_auth_access_token_missing(client):
    data = {"access_token": "missing"}
    assert_got_error_from_get(client, '/attr_auth/setup', data, 400, INVALID_ACCESS_TOKEN_ERROR_MSG)


def test_set_username_missing_api_username(client, attr_auth_access_token_one):
    data = {"access_token": attr_auth_access_token_one}
    assert_got_error_from_post(client, '/attr_auth/set_username', data, 400, API_USERNAME_MISSING_ERROR_MSG)


def test_set_username_already_present(client, attr_auth_access_token_one):
    data = {"access_token": attr_auth_access_token_one, "api_username": "TestUser"}
    assert_got_error_from_post(client, '/attr_auth/set_username', data, 400, API_USERNAME_ALREADY_PRESENT_MSG)


def test_set_username(client, app_and_ctx, attr_auth_access_token_one):
    data = {"access_token": attr_auth_access_token_one, "api_username": "Changed"}
    assert_got_data_from_post(client, '/attr_auth/set_username', data)

    app, ctx = app_and_ctx
    with app.app_context():
        user = AttrAuthUser.get_by_id(1)
        assert user.api_username == "Changed"

        data = {"access_token": attr_auth_access_token_one, "api_username": "MartinHeinz"}
        assert_got_data_from_post(client, '/attr_auth/set_username', data)
        user = AttrAuthUser.get_by_id(1)
        assert user.api_username == "MartinHeinz"


def test_already_has_key_from_owner(app_and_ctx, attr_auth_access_token_one, attr_auth_access_token_two):
    app, ctx = app_and_ctx
    with app.app_context():
        owner = AttrAuthUser.get_by_id(1)
        receiver = AttrAuthUser.get_by_id(2)

        assert already_has_key_from_owner(receiver, owner)


def test_doesnt_have_key_from_owner(app_and_ctx, attr_auth_access_token_two):
    app, ctx = app_and_ctx
    with app.app_context():
        receiver = AttrAuthUser.get_by_id(2)

        owner = AttrAuthUser()

        assert not already_has_key_from_owner(receiver, owner)


def test_create_attributes():
    attr_list = ["TODAY", "TOMORROW"]
    attrs = create_attributes(attr_list)
    assert attrs[0].value == "TODAY"
    assert attrs[1].value == "TOMORROW"
    assert len(attrs) == 2


def test_decrypt_missing_owner_api_username(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one
    }
    assert_got_error_from_get(client, '/attr_auth/decrypt', data, 400, OWNER_API_USERNAME_MISSING_ERROR_MSG)


def test_decrypt_missing_ciphertext(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one,
        "api_username": "MartinHeinz"
    }
    assert_got_error_from_get(client, '/attr_auth/decrypt', data, 400, CIPHERTEXT_MISSING_ERROR_MSG)


def test_decrypt_invalid_owner(client, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_two,
        "api_username": "INVALID",
        "ciphertext": "anything-doesnt-matter"
    }
    assert_got_error_from_get(client, '/attr_auth/decrypt', data, 400, INVALID_OWNER_API_USERNAME_ERROR_MSG)


def test_decrypt_could_not_decrypt(client, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_two,
        "api_username": "MartinHeinz"
    }
    plaintext = "any text"
    data_encrypt = {
        "access_token": attr_auth_access_token_one,
        "message": plaintext,
        "policy_string": "(TODAY)"  # INVALID
    }
    status_code, json_data = get_data_from_get(client, '/attr_auth/encrypt', data_encrypt)
    assert json_data["ciphertext"] is not None
    data["ciphertext"] = json_data["ciphertext"]

    assert_got_error_from_get(client, '/attr_auth/decrypt', data, 400, COULD_NOT_DECRYPT_ERROR_MSG)


def test_decrypt_succesfull(client, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_two,
        "api_username": "MartinHeinz"
    }
    plaintext = "any text"
    data_encrypt = {
        "access_token": attr_auth_access_token_one,
        "message": plaintext,
        "policy_string": "(GUESTTODAY)"
    }
    status_code, json_data = get_data_from_get(client, '/attr_auth/encrypt', data_encrypt)
    assert status_code == 200
    assert json_data["ciphertext"] is not None
    data["ciphertext"] = json_data["ciphertext"]

    status_code, json_data = get_data_from_get(client, '/attr_auth/decrypt', data)
    assert status_code == 200
    assert json_data["plaintext"] == plaintext


def test_keygen_missing_device_id(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "1 1-2 1-GUEST",
        "api_username": "TestUser",
    }
    assert_got_error_from_post(client, '/attr_auth/user/keygen', data, 400, DEVICE_ID_MISSING_ERROR_MSG)


def test_keygen_invalid_receiver(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "TODAY_GUEST, ANOTHER",
        "api_username": "invalid",
        "device_id": "1"
    }
    assert_got_error_from_post(client, '/attr_auth/user/keygen', data, 400, INCORRECT_API_USERNAME_ERROR_MSG)


def test_keygen_invalid_attr_list(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "TODAY_GUEST, ANOTHER",
        "api_username": "TestUser",
        "device_id": "1"
    }
    assert_got_error_from_post(client, '/attr_auth/user/keygen', data, 400, INVALID_ATTR_LIST_ERROR_MSG)

    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "15-GUEST #$%^&* 15",
        "api_username": "TestUser",
        "device_id": "1"
    }
    assert_got_error_from_post(client, '/attr_auth/user/keygen', data, 400, INVALID_ATTR_LIST_ERROR_MSG)


def test_keygen_already_has_key_from_owner(client, app_and_ctx, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "1 1-2 1-GUEST",
        "api_username": "TestUser",
        "device_id": "1"
    }
    app, ctx = app_and_ctx
    with app.app_context():
        receiver = AttrAuthUser.get_by_id(2)  # TestUser access_token
        old_private_key = next(key for key in receiver.private_keys if key.challenger_id == 1)
        old_private_key_data = old_private_key.data
        old_private_key_key_update = old_private_key.key_update
        private_keys_num = len(receiver.private_keys)

        assert_got_data_from_post(client, '/attr_auth/user/keygen', data)

        receiver = AttrAuthUser.get_by_id(2)  # TestUser access_token
        new_private_key = next(key for key in sorted(receiver.private_keys, key=lambda p: p.key_update, reverse=True) if key.challenger_id == 1)

        assert old_private_key_data != new_private_key.data
        assert old_private_key_key_update < new_private_key.key_update

        assert len(receiver.private_keys) > private_keys_num

        # Try to encrypt and decrypt
        pairing_group = create_pairing_group()
        cp_abe = create_cp_abe()
        plaintext = "Hello World"
        data_owner = AttrAuthUser.get_by_id(1)
        policy_str = '(1-GUEST)'
        public_key = deserialize_charm_object(data_owner.master_keypair.data_public, pairing_group)
        new_private_key = deserialize_charm_object(new_private_key.data, pairing_group)
        ciphertext = cp_abe.encrypt(public_key, plaintext, policy_str)
        decrypted_msg = cp_abe.decrypt(public_key, new_private_key, ciphertext)
        assert plaintext == decrypted_msg.decode("utf-8")


def test_keygen_replaces_old_key(client, app_and_ctx, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "1 1-2 1-GUEST",
        "api_username": "TestUser",
        "device_id": "99"
    }
    app, ctx = app_and_ctx
    with app.app_context():

        assert_got_data_from_post(client, '/attr_auth/user/keygen', data)

        receiver = AttrAuthUser.get_by_id(2)
        old_private_key = next(key for key in receiver.private_keys if key.challenger_id == 1 and key.device_id == 99)
        old_private_key_data = old_private_key.data
        old_private_key_key_update = old_private_key.key_update
        old_private_keys_num = len(receiver.private_keys)

        assert_got_data_from_post(client, '/attr_auth/user/keygen', data)  # This should replace old_private_key_data

        receiver = AttrAuthUser.get_by_id(2)
        new_private_key = next(key for key in receiver.private_keys if key.challenger_id == 1 and key.device_id == 99)
        new_private_key_data = new_private_key.data
        new_private_key_key_update = new_private_key.key_update

        assert old_private_key_data != new_private_key_data
        assert old_private_key_key_update < new_private_key_key_update
        assert old_private_keys_num == len(receiver.private_keys)

        db.session.delete(new_private_key)
        db.session.commit()


def test_retrieve_private_keys(client, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_one,
    }
    assert_got_data_from_post(client, '/attr_auth/user/retrieve_private_keys', data, private_keys=[])

    data = {
        "access_token": attr_auth_access_token_two,
    }
    status_code, json_data = get_data_from_post(client, '/attr_auth/user/retrieve_private_keys', data)
    assert status_code == 200
    assert len(json_data["private_keys"]) == 2


def test_keygen_doesnt_have_key_from_owner(client, app_and_ctx, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_two,
        "attr_list": "2 2-1 2-GUEST",
        "api_username": "MartinHeinz",
        "device_id": "1"
    }
    app, ctx = app_and_ctx
    with app.app_context():
        receiver = AttrAuthUser.get_by_id(1)

        num_of_old_keys = len(receiver.private_keys)

        assert_got_data_from_post(client, '/attr_auth/user/keygen', data)

        receiver = AttrAuthUser.get_by_id(1)
        new_private_key = next(key for key in receiver.private_keys if key.challenger_id == 2)

        assert len(receiver.private_keys) == num_of_old_keys + 1

        # Try to encrypt and decrypt
        pairing_group = create_pairing_group()
        cp_abe = create_cp_abe()
        plaintext = "Hello World"
        data_owner = AttrAuthUser.get_by_id(2)
        policy_str = '(2-GUEST)'
        public_key = deserialize_charm_object(data_owner.master_keypair.data_public, pairing_group)
        new_private_key = deserialize_charm_object(new_private_key.data, pairing_group)
        ciphertext = cp_abe.encrypt(public_key, plaintext, policy_str)
        decrypted_msg = cp_abe.decrypt(public_key, new_private_key, ciphertext)
        assert plaintext == decrypted_msg.decode("utf-8")


def test_device_keygen(client, app_and_ctx, attr_auth_access_token_one, attr_auth_access_token_two):
    data = {
        "access_token": attr_auth_access_token_one,
    }
    assert_got_error_from_post(client, '/attr_auth/device/keygen', data, 400, ATTR_LIST_MISSING_ERROR_MSG)

    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "sedr_gd 1 1-23 1-GUEST",  # invalid
    }
    assert_got_error_from_post(client, '/attr_auth/device/keygen', data, 400, INVALID_ATTR_LIST_ERROR_MSG)

    data = {
        "access_token": attr_auth_access_token_one,
        "attr_list": "1 1-23 1-GUEST",
    }
    status, data_out = get_data_from_post(client, '/attr_auth/device/keygen', data)
    assert status == 200
    assert "private_key" in data_out


def test_parse_attr_list():
    valid_attr_list = 'QH QD\t JC KD 4   JS'
    valid_attr_list_2 = '12-GUEST 12-13 12'
    empty_attr_list = ''
    invalid_attr_list = 'Q-H QD JC K_D JS'
    assert parse_attr_list(valid_attr_list) == ['QH', 'QD', 'JC', 'KD', '4', 'JS']
    assert parse_attr_list(valid_attr_list_2) == ['12-GUEST', '12-13', '12']
    assert len(parse_attr_list(empty_attr_list)) == 0
    assert len(parse_attr_list(invalid_attr_list)) == 0


def test_get_private_key_based_on_owner():
    decryptor = Mock()
    expected = PrivateKey(challenger=AttrAuthUser(id=10))
    decryptor.private_keys = [PrivateKey(challenger=AttrAuthUser(id=11)), expected, PrivateKey(challenger=AttrAuthUser(id=25))]
    owner = expected.challenger
    key = get_private_key_based_on_owner(decryptor, owner)
    assert key == expected


def test_is_valid():
    assert not is_valid(["3-thdr", "1-34, 1"], 1)
    assert is_valid(["1-thdr", "1-34, 1"], 1)


def test_create_private_key():
    pairing_group = create_pairing_group()
    cp_abe = create_cp_abe()

    public_key, master_key = cp_abe.setup()
    serialized_public_key = serialize_charm_object(public_key, pairing_group)
    serialized_master_key = serialize_charm_object(master_key, pairing_group)

    serialized_private_key = create_private_key(serialized_master_key, serialized_public_key, ["1", "1-2", "1-GUEST"])

    plaintext_in = "stuff"
    policy_string = "(1)"
    ciphertext = cp_abe.encrypt(public_key, plaintext_in, policy_string)

    private_key = deserialize_charm_object(serialized_private_key, pairing_group)
    plaintext_out = cp_abe.decrypt(public_key, private_key, ciphertext)

    assert plaintext_in == plaintext_out.decode()


def test_get_private_key_based_on_owner_missing():
    decryptor = Mock()
    decryptor.private_keys = [PrivateKey(challenger=AttrAuthUser(id=10)),
                              PrivateKey(challenger=AttrAuthUser(id=34)),
                              PrivateKey(challenger=AttrAuthUser(id=37))]
    owner = AttrAuthUser(id=235)
    with pytest.raises(Exception):
        get_private_key_based_on_owner(decryptor, owner)


def test_key_setup(client, app_and_ctx, attr_auth_access_token_one):
    data = {"access_token": attr_auth_access_token_one}

    status_code, json_data = get_data_from_get(client, '/attr_auth/setup', data)
    assert status_code == 200
    serialized_public_key_response = json_data["public_key"]

    app, ctx = app_and_ctx
    with app.app_context():
        serialized_public_key_from_db = AttrAuthUser.get_by_id(1).master_keypair.data_public.decode("utf-8")
        assert serialized_public_key_response == serialized_public_key_from_db


def test_encrypt_missing_plaintext(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one
    }
    assert_got_error_from_get(client, '/attr_auth/encrypt', data, 400, MESSAGE_MISSING_ERROR_MSG)


def test_encrypt_missing_policy_string(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one,
        "message": "any text"
    }
    assert_got_error_from_get(client, '/attr_auth/encrypt', data, 400, POLICY_STRING_MISSING_ERROR_MSG)


def test_encrypt_succesfull(client, attr_auth_access_token_one):
    data = {
        "access_token": attr_auth_access_token_one,
        "message": "any text",
        "policy_string": "(TODAY)"
    }
    status_code, json_data = get_data_from_get(client, '/attr_auth/encrypt', data)
    assert status_code == 200
    assert json_data["ciphertext"] is not None


def test_replace_existing_key(app_and_ctx, attr_auth_access_token_one, attr_auth_access_token_two):
    app, ctx = app_and_ctx
    attr_list = ["TODAY", "TOMORROW"]
    dummy_serialized_key = b'key'
    with app.app_context():
        owner = AttrAuthUser.get_by_id(1)
        receiver = AttrAuthUser.get_by_id(2)

        replace_existing_key(receiver, dummy_serialized_key, owner, attr_list)
        modified_key = receiver.private_keys[0]
        assert modified_key.data == dummy_serialized_key
        assert modified_key.attributes[0].value == "TODAY"
