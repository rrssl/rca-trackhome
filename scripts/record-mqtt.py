import json
import pickle
from datetime import datetime

import paho.mqtt.client as mqtt
# import ssl

host = "localhost"
port = 1883
topic = "tags"


def on_connect(client, userdata, flags, rc):
    print(mqtt.connack_string(rc))


# callback triggered by a new Pozyx data packet
def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())[0]
    if not data['success']:
        return
    data = {
        'i': data['tagId'],
        't': data['timestamp'],
        'x': data['data']['coordinates']['x'],
        'y': data['data']['coordinates']['y'],
        'z': data['data']['coordinates']['z'],
    }
    userdata.append(data)
    print(data)


def on_subscribe(client, userdata, mid, granted_qos):
    print("Subscribed to topic!")


def main():
    data = []
    client = mqtt.Client(userdata=data)

    # set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    client.connect(host, port=port)
    client.subscribe(topic)

    # works blocking, other, non-blocking, clients are available too.
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        fname = f"data-{datetime.now().strftime('%Y%m%d%H%M%S')}.pkl"
        with open(fname, 'wb') as f:
            pickle.dump(data, f)


if __name__ == "__main__":
    main()
