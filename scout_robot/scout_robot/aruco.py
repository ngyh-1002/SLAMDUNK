import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import PoseArray
import cv2
import numpy as np

# Aruco Dictionary 설정 (사용하는 마커에 맞게 변경)
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
ARUCO_DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)

class CompressedArucoDetector(Node):
    def __init__(self):
        super().__init__('compressed_aruco_detector')

        # 1. 구독자 설정: 라즈베리파이에서 발행하는 compressed 토픽 구독
        self.subscription = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',  # 라즈베리파이의 압축 토픽 이름
            self.compressed_image_callback,
            10
        )

        # 2. 발행자 설정 (선택 사항: 인식된 마커 포즈 발행)
        self.pose_publisher = self.create_publisher(
            PoseArray,
            '/aruco_poses',
            10
        )

        self.get_logger().info('ArUco Detector Node has been started, subscribing to /image_raw/compressed.')

    def compressed_image_callback(self, msg):
        # 1. CompressedImage -> OpenCV Mat (압축 해제)
        np_arr = np.frombuffer(msg.data, np.uint8)
        cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if cv_image is None:
            self.get_logger().error("Failed to decode compressed image.")
            return        

        # 2. ArUco 마커 인식
        corners, ids, rejected = ARUCO_DETECTOR.detectMarkers(cv_image)

        # 3. 인식 결과 처리 및 화면 표시
        if ids is not None:
            # 인식된 마커 주변에 사각형 그리기
            cv2.aruco.drawDetectedMarkers(cv_image, corners, ids)
            # (추가: 포즈 추정을 위해서는 카메라 캘리브레이션 정보(CameraInfo)가 필요합니다.)

        # 4. 영상 화면 띄우기
        cv2.imshow("ArUco Marker Detection (Compressed)", cv_image)
        cv2.waitKey(1)  # 화면을 유지하기 위해 필수

def main(args=None):
    rclpy.init(args=args)
    aruco_detector_node = CompressedArucoDetector()
    try:
        rclpy.spin(aruco_detector_node)
    except KeyboardInterrupt:
        pass
    finally:
        # 노드 종료 시 OpenCV 창 닫기
        cv2.destroyAllWindows()
        aruco_detector_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
