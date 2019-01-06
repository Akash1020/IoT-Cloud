from datetime import datetime
from flask import current_app
from app.models.models import Device, DeviceData
from app.utils import bytes_to_json


# The callback for when the client receives a CONNACK response from the server.
def handle_on_connect(client, userdata, flags, rc):
    current_app.logger.info("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("#")


# The callback for when a PUBLISH message is received from the server.
def handle_on_message(client, userdata, msg, app, db):
    msg.payload = bytes_to_json(msg.payload)
    current_app.logger.info("Received message '" + str(msg.payload) + "' on topic '" + msg.topic + "' with QoS " + str(msg.qos))

    if msg.topic == "save_data":
        with app.app_context():
            device = db.session.query(Device).filter(Device.id == msg.payload["device_id"]).first()
            current_app.logger.info("Querying device with id: " + str(msg.payload["device_id"]))
            if device is not None:
                db.session.add(DeviceData(
                    data=str.encode(msg.payload["device_data"]),
                    device=device,
                    correctness_hash=msg.payload["correctness_hash"],
                    num_data=msg.payload["num_data"],
                    added=datetime.strptime(msg.payload["added"], "%Y-%m-%d %H:%M:%S")
                ))
                db.session.commit()
                current_app.logger.info("Inserting device data for device: " + str(msg.payload["device_id"]) + " data: " + msg.payload["device_data"])
            else:
                current_app.logger.info("Device with id: " + str(msg.payload["device_id"]) + " doesn't exist.")


def handle_on_log(client, userdata, level, buf):
    if not current_app.testing:
        current_app.logger.info("[ON LOG]: level: {} data: {}".format(level, buf))


def handle_on_publish(client, userdata, mid):
    current_app.logger.info("[ON PUBLISH]: userdata: {}  mid: {}".format(userdata, mid))
