import logging
import threading
import face_recognition
import httpx
import cv2
import numpy as np
import lethingaccesssdk
from threading import Timer
import time
import socket
import json

UNKNOWN_PERSON = "陌生人"
current_person = UNKNOWN_PERSON

qx_face = face_recognition.load_image_file("./known/qx.jpg")
qx_face_encoding = face_recognition.face_encodings(qx_face)[0]

known_face_encodings = [qx_face_encoding]

known_face_names = ["钱旭"]


class camera:
    def __init__(self, url: str):
        self.url = url

    def get_frame(self):
        """
        获取图像
        """
        try:
            r = httpx.get(self.url)
            image = np.asarray(bytearray(r.content), dtype="uint8")
            return True, cv2.imdecode(image, cv2.IMREAD_COLOR)
        except Exception as e:
            logging.error("get image fail %s" % e)
            return False, None


class camera_connector(lethingaccesssdk.ThingCallback):
    """
    camera连接器
    """

    def __init__(
        self, config, camera: camera, known_faces: list, known_faces_encodings: list
    ):
        # 摄像头类
        self.camera = camera
        # 通过设备三码获取客户端
        self._client = lethingaccesssdk.ThingAccessClient(config)
        # 已知人脸
        self.known_faces = known_faces
        # 已知人脸编码
        self.known_faces_encodings = known_faces_encodings
        # 是否开启识别
        self._is_recognition = False

    def connect(self):
        # TODO:检查设备是否在线
        self._client.registerAndOnline(self)

    def disconnect(self):
        """
        设备下线
        """
        self._client.offline()

    @property
    def client(self):
        return self._client

    @property
    def is_recognition(self):
        """
        是否识别
        """
        return self._is_recognition

    @is_recognition.setter
    def is_recognition(self, value):
        self._is_recognition = value

    def recognize_face(self, image):
        """
        识别人脸
        """
        # 获得所有人脸的位置以及它们的编码
        face_locations = face_recognition.face_locations(image)
        # 检测到人脸数
        count = len(face_locations)
        logging.info("Found {} faces in image.".format(count))
        name = UNKNOWN_PERSON
        if count > 0:
            face_encodings = face_recognition.face_encodings(image, face_locations)
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(
                    self.known_faces_encodings, face_encoding, tolerance=0.5
                )
                # # If a match was found in known_face_encodings, just use the first one.
                # if True in matches:
                #     first_match_index = matches.index(True)
                #     name = known_face_names[first_match_index]

                # Or instead, use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(
                    self.known_faces_encodings, face_encoding
                )
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = known_face_names[best_match_index]
                    break
        return count, name

    def getProperties(self, input_value):
        """
        Get properties from the physical thing and return the result.
        :param input_value:
        :return:
        """
        global current_person
        retDict = {}
        if "isRecognition" in input_value:
            retDict["isRecognition"] = 1 if self.is_recognition else 0
        if "face_count" in input_value or "person" in input_value:
            if self.is_recognition:
                # 获取图像 检测
                ret, image = self.camera.get_frame()
                if False == ret:
                    retDict["face_count"] = -1
                    retDict["person"] = UNKNOWN_PERSON
                    self.disconnect()
                else:
                    # 检测
                    retDict["face_count"], retDict["person"] = self.recognize_face(
                        image
                    )
            else:
                retDict["face_count"] = -1
                retDict["person"] = UNKNOWN_PERSON
            current_person = retDict["person"]
        return 0, retDict

    def setProperties(self, input_value):
        """
        Set properties to the physical thing and return the result.
        :param input_value:
        :return:
        """
        return 0, {}

    def callService(self, name, input_value):
        """
        Call services on the physical thing and return the result.
        :param name:
        :param input_value:
        :return:
        """
        if "startRecognition" == name:
            # 启动识别服务
            self._is_recognition = True
        if "stopRecognition" == name:
            # 停止识别服务
            self._is_recognition = False
        return 0, {}


class haas:
    pass


class haas_connector(lethingaccesssdk.ThingCallback):
    def __init__(self, config):
        # 通过设备三码获取客户端
        self._client = lethingaccesssdk.ThingAccessClient(config)
        #
        self._period = 0
        self._duty = 0
        self._isOpen = 0
        self.last_person = UNKNOWN_PERSON
        self.lock = threading.RLock()

    def connect(self):
        # TODO:检查设备是否在线
        self._client.registerAndOnline(self)

    def disconnect(self):
        """
        设备下线
        """
        self._client.offline()

    @property
    def period(self):
        return self._period

    @period.setter
    def period(self, value):
        self._period = value

    @property
    def duty(self):
        return self._duty

    @duty.setter
    def duty(self, value):
        self._duty = value

    @property
    def back_msg(self):
        """
        获取发送的信息
        """
        msg = " "
        self.lock.acquire()
        if self.last_person != current_person:
            if UNKNOWN_PERSON == current_person:
                msg = "close"
            else:
                msg = "open"
        self.lock.release()
        self.last_person = current_person
        return msg

    @property
    def isOpen(self):
        return self._isOpen

    @isOpen.setter
    def isOpen(self, value):
        self._isOpen = value

    @property
    def client(self):
        return self._client

    def getProperties(self, input_value):
        """
        Get properties from the physical thing and return the result.
        :param input_value:
        :return:
        """
        retDict = {}
        return 0, retDict

    def setProperties(self, input_value):
        """
        Set properties to the physical thing and return the result.
        :param input_value:
        :return:
        """
        if "period" in input_value:
            self.period = input_value["period"]
        if "duty" in input_value:
            self.duty = input_value["duty"]
        if "isOpen" in input_value:
            self.isOpen = input_value["isOpen"]
        return 0, {}

    def callService(self, name, input_value):
        return 0, {}


def camera_thing_behavior(connect):
    """
    摄像头行为 上报属性啥的
    """
    client = connect.client
    while True:
        _, props = connect.getProperties(["isRecognition", "face_count"])
        client.reportProperties(props)
        time.sleep(1)


def haas_thing_behavior(connect):
    """
    haas行为
    """
    client = connect.client
    # TODO: socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port = 233
    ip = "192.168.31.196"
    # 绑定端口号
    s.bind((ip, port))
    #
    s.listen(5)
    while True:
        logging.info("starting socket")
        conn, addr = s.accept()
        logging.info("connect with %s" % addr.__str__())
        connect.connect()
        while True:
            try:
                props = conn.recv(1024)
                msg = connect.back_msg
                conn.send(msg.encode("utf-8"))
                if " " != msg:
                    client.reportEvent(msg, {})
                props = props.decode("utf-8")
                if len(props) > 0:
                    # 读到props
                    logging.info(props)
                    # 转为json
                    props = json.loads(props)
                    # 设置props
                    connect.setProperties(props)
                    # 上报属性
                    client.reportProperties(props)
                time.sleep(0.5)
            except Exception as e:
                logging.error("connect fail %s" % e.__str__())
                break
        conn.close()
        connect.disconnect()


infos = lethingaccesssdk.Config().getThingInfos()
for info in infos:
    logging.info(info)
    if "g5_cam" == info["deviceName"]:
        try:
            cam = camera("http://192.168.31.22/capture")
            connector = camera_connector(
                info, cam, known_face_names, known_face_encodings
            )
            connector.connect()
            t = Timer(2, camera_thing_behavior, (connector,))
            t.start()
        except Exception as e:
            logging.error(e)
    if "g5_servo" == info["deviceName"]:
        try:
            # TODO: haas处理
            connector = haas_connector(info)
            t = Timer(2, haas_thing_behavior, (connector,))
            t.start()
        except Exception as e:
            logging.error(e)
# don't remove this function
def handler(event, context):
    return "hello world"
