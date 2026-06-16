import json
import paho.mqtt.client as mqtt

#  broker 
mqtt_broker = "mqtt-broker"
mqtt_port = 1883
mqtt_topic = "imu/data"

#  client
mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code " + str(rc))
    # Subscribe to the IMU data topic
    client.subscribe(mqtt_topic)

def on_message(client, userdata, message):
    try:
        imu_data = json.loads(message.payload)
        print("Received IMU Data:", imu_data)  # Log the received data
        check_for_anomalies(imu_data)
    except json.JSONDecodeError as e:
        print("JSON Decode Error:", e)
    except KeyError as e:
        print(f"Key error: {e}. Please check the IMU data format.")

def check_for_anomalies(imu_data):
    try:
        # Extract relevant IMU data
        acceleration = imu_data['acceleration']  # X, Y, Z axes
        gyro1 = imu_data['gyro1']  
        gyro2 = imu_data['gyro2'] 
        magnetometer = imu_data['magnetometer']  # X, Y, Z axes

        
        THRESHOLD_ACCELERATION_Z = 1.5  # Threshold for Z-axis acceleration in g (approximately 1.5g)
        THRESHOLD_GYRO = 5.0  # Threshold for gyroscope (roll/pitch) in degrees
        THRESHOLD_MAGNETOMETER = 50.0  # Threshold for magnetometer data (adjust as needed)

        # Check for anomalies in acceleration data (for vertical movements)
        z_acceleration = acceleration[2]  # Z-axis acceleration (up/down)
        if abs(z_acceleration) > THRESHOLD_ACCELERATION_Z:
            print("Anomaly detected in vertical acceleration data (Z-axis):", z_acceleration)
        
        # Check for anomalies in gyroscope data (roll and pitch mainly)
        roll_gyro1 = gyro1[0]  # Roll (rotation around X-axis)
        pitch_gyro1 = gyro1[1]  # Pitch (rotation around Y-axis)
        if abs(roll_gyro1) > THRESHOLD_GYRO or abs(pitch_gyro1) > THRESHOLD_GYRO:
            print(f"Anomaly detected in gyroscope data (Roll: {roll_gyro1}, Pitch: {pitch_gyro1}) from Gyro1")

        
        roll_gyro2 = gyro2[0]  # Roll (rotation around X-axis)
        pitch_gyro2 = gyro2[1]  # Pitch (rotation around Y-axis)
        if abs(roll_gyro2) > THRESHOLD_GYRO or abs(pitch_gyro2) > THRESHOLD_GYRO:
            print(f"Anomaly detected in gyroscope data (Roll: {roll_gyro2}, Pitch: {pitch_gyro2}) from Gyro2")

        
    except KeyError as e:
        print(f"Key error: {e}. Please check the IMU data format.")

# Set the on_connect and on_message callbacks
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to MQTT broker
mqtt_client.connect(mqtt_broker, mqtt_port, 60)

# Start the MQTT client loop
mqtt_client.loop_forever()