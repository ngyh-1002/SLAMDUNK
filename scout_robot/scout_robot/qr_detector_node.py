#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage 
from std_msgs.msg import String
import cv2
from pyzbar import pyzbar
import numpy as np
from ament_index_python.packages import get_package_share_directory
import os
import yaml

# --- 토픽 및 상수 정의 ---
QR_COMMAND_TOPIC = "/qr_check_command"
AMCL_RESET_COMMAND_TOPIC = "/amcl_reset_command"
# 🌟🌟🌟 로봇 회전 명령을 보낼 토픽 정의 🌟🌟🌟
ROBOT_ROTATE_COMMAND_TOPIC = "/robot_rotate_command"
# @@ qr node @@
QR_DETECTION_SUCCESS_TOPIC = "/qr_detection_success"
SPEAKER_COMMAND_TOPIC = "/speaker_command"
COMMAND_TO_QR_MAP = {
    "go_room501": "501",
    "go_home": "home",  
    "go_room502": "502",
    "go_room503": "503",
}
QR_DATA_TO_POSE = {}

# 🌟🌟🌟 QR 코드 검사 시간 제한 🌟🌟🌟
QR_CHECK_TIMEOUT_SEC = 10.0


class QrDetector(Node):
    def __init__(self):
        super().__init__('qr_detector_node')
        
        self.load_room_coordinates()
        
        self.expected_qr_data = None  
        self.is_qr_detected = False 
        self.qr_check_active = False # QR 검사 활성화 상태 플래그
        self.timeout_timer = None     # 타임아웃 타이머 객체
        self.last_command = None    # 🌟🌟🌟 마지막으로 받은 명령을 저장 🌟🌟🌟
        self.check_all_mode = False # 🌟🌟🌟 모든 QR 검사 모드 플래그 🌟🌟🌟
        
        # 1. 카메라 구독
        self.camera_subscription = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',  
            self.image_callback,
            10)
        
        # 2. 목표 명령 구독 (RoomNavigator/RobotRotator -> QR Detector)
        self.command_subscription = self.create_subscription(
            String,
            QR_COMMAND_TOPIC, 
            self.command_callback,
            10
        )
        
        # 3. AMCL 리셋 명령 발행
        self.amcl_reset_pub = self.create_publisher(
            String,
            AMCL_RESET_COMMAND_TOPIC,
            10
        )
        
        # 4. 로봇 회전 명령 발행
        self.rotate_command_pub = self.create_publisher(
            String,
            ROBOT_ROTATE_COMMAND_TOPIC,
            10
        )
        
        # @@:별2::별2::별2: 5. QR 인식 성공 신호 발행 Publisher 추가 :별2::별2::별2:@@
        self.qr_success_pub = self.create_publisher(
            String,
            QR_DETECTION_SUCCESS_TOPIC,
            10
        )
        
        # 스피커 노드
        self.speaker_pub = self.create_publisher(
            String,
            SPEAKER_COMMAND_TOPIC, 
            10
        )

        self.get_logger().info(f'QR Detector Node started. Publishing rotation commands on {ROBOT_ROTATE_COMMAND_TOPIC}...')

    def load_room_coordinates(self):
        """rooms.yaml 파일을 읽어 QR 코드에 해당하는 좌표를 로드합니다."""
        global QR_DATA_TO_POSE
        package_share = get_package_share_directory('scout_robot')
        yaml_path = os.path.join(package_share, 'rooms.yaml')
        
        try:
            with open(yaml_path, 'r') as f:
                rooms_data = yaml.safe_load(f)['rooms']
                
            # 일반 명령 매핑
            for cmd, qr_data in COMMAND_TO_QR_MAP.items():
                room_name = cmd.replace("go_", "")
                if room_name in rooms_data:
                    QR_DATA_TO_POSE[qr_data] = rooms_data[room_name]
                    
            # rooms.yaml에 있는 모든 QR 데이터를 인식 대상에 추가
            for room_name, data in rooms_data.items():
                # 'start'나 'home' 같은 특별한 이름도 포함
                if room_name in ['start', 'home']:
                    qr_data_key = room_name
                elif room_name.startswith('room'):
                    qr_data_key = room_name.replace("room", "")
                else:
                    continue # 다른 이름은 무시
                
                # 중복은 덮어쓰기 (COMMAND_TO_QR_MAP으로 이미 등록된 경우 포함)
                QR_DATA_TO_POSE[qr_data_key] = data
            
            self.get_logger().info("✅ rooms.yaml에서 QR 목표 좌표 로드 완료.")
        
        except FileNotFoundError:
            self.get_logger().error(f"rooms.yaml 파일을 찾을 수 없습니다: {yaml_path}")
            
    # QR 검사 타임아웃 처리 함수 (변경 없음)
    def check_qr_timeout(self):
        """10초 후 타이머에 의해 호출됩니다. QR 인식 성공 여부를 최종 확인합니다."""
        
        if self.timeout_timer is not None:
            self.timeout_timer.cancel()
            self.timeout_timer = None
        
        self.qr_check_active = False # 검사 비활성화

        if self.is_qr_detected:
            # QR 코드 인식 성공은 이미 image_callback에서 처리되었으므로 추가 행동 불필요
            return
        else:
            # 🌟🌟🌟 10초 동안 QR 코드를 인식하지 못했을 경우 (QR 인식 실패) 🌟🌟🌟
            self.get_logger().error(f"❌❌❌ QR 코드 인식 실패! {QR_CHECK_TIMEOUT_SEC}초 동안 '{self.expected_qr_data}'를 찾지 못했습니다. ❌❌❌")
            
            # 1. Robot Rotator Node에게 회전 명령과 목표 정보를 함께 발행
            if self.last_command is not None:
                rotate_msg = String()
                # 회전 명령과 목표 명령을 'ROTATE_LEFT_45:go_room501' 형태로 보냄
                rotate_msg.data = f"ROTATE_LEFT_45:{self.last_command}"
                self.rotate_command_pub.publish(rotate_msg)
                self.get_logger().warn(f"🔄 Robot Rotator Node에게 45도 회전 명령을 발행했습니다. 목표: {self.last_command}")
            else:
                self.get_logger().error("⚠️ last_command 정보가 없어 회전 명령을 보낼 수 없습니다.")
                
            # 2. 다음 명령을 기다리기 위해 QR 감지 비활성화 (expected_qr_data는 유지할 필요가 없음, command_callback에서 재설정됨)
            self.expected_qr_data = None # 재검사 명령을 기다리는 대기 상태로 전환
            self.check_all_mode = False # 일반 모드로 복귀

    def command_callback(self, msg: String):
        """/qr_check_command 토픽을 구독하여 기대 QR 코드를 동적으로 설정"""
        command = msg.data.strip()
        
        # 🌟🌟🌟 1. Nav2 실패로 인한 전체 QR 검사 모드 처리 🌟🌟🌟
        if command == "check_all_qr":
            self.last_command = "check_all_qr" # 마지막 명령 저장 (재시도용은 아니지만 상태 저장을 위해)
            self.expected_qr_data = None       # 모든 QR 코드를 인식 대상으로 함
            self.is_qr_detected = False
            self.qr_check_active = True
            self.check_all_mode = True         # 모든 QR 검사 모드 활성화
            
            self.get_logger().warn("🚨 Nav2 이동 실패! 모든 QR 코드를 인식 대상으로 설정하고 스캔을 시작합니다.")

            # 타임아웃 타이머 시작
            if self.timeout_timer is not None:
                self.timeout_timer.cancel()
            self.timeout_timer = self.create_timer(QR_CHECK_TIMEOUT_SEC, self.check_qr_timeout)
            self.get_logger().warn(f"⏳ 전체 QR 스캔 모드 활성화. {QR_CHECK_TIMEOUT_SEC}초 동안 스캔을 시작합니다.")
        
        # 🌟🌟🌟 2. 일반 명령 처리 🌟🌟🌟
        elif command in COMMAND_TO_QR_MAP:
            self.last_command = command 
            self.expected_qr_data = COMMAND_TO_QR_MAP[command]
            self.is_qr_detected = False
            self.qr_check_active = True
            self.check_all_mode = False # 일반 모드
            
            self.get_logger().info(f"✅ QR 검사 명령 수신: '{command}'. 기대 QR 코드가 '{self.expected_qr_data}'(으)로 설정되었습니다.")
            
            # 10초 타이머 시작
            if self.timeout_timer is not None:
                self.timeout_timer.cancel()
            self.timeout_timer = self.create_timer(QR_CHECK_TIMEOUT_SEC, self.check_qr_timeout)
            self.get_logger().warn(f"⏳ QR 스캔 모드 활성화. {QR_CHECK_TIMEOUT_SEC}초 동안 스캔을 시작합니다.")
            
        else:
            self.get_logger().warn(f"⚠️ 알 수 없는 QR 명령 수신: {command}.")


    def image_callback(self, data: CompressedImage):
        """QR 코드를 감지하고 성공 시 AMCL 재설정 명령을 발행합니다."""
        
        if not self.qr_check_active or self.is_qr_detected:
            # ... (비활성화 상태 디버그 뷰 로직 유지) ...
            try:
                np_arr = np.frombuffer(data.data, dtype=np.uint8)
                current_frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if current_frame is not None:
                    target_display = self.expected_qr_data if not self.check_all_mode and self.expected_qr_data else ('ALL' if self.check_all_mode else 'None')
                    status_text = f"Target: {target_display}. Scanning {'ON' if self.qr_check_active else 'OFF'}"
                    cv2.putText(current_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    cv2.imshow(f"QR Detector View", current_frame)
                    cv2.waitKey(1)
            except Exception as e:
                self.get_logger().error(f'Image data decoding/display failed: {e}')
            return
            
        try:
            np_arr = np.frombuffer(data.data, dtype=np.uint8)
            current_frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if current_frame is None: return

            decoded_objects = pyzbar.decode(current_frame)
            
            for obj in decoded_objects:
                decoded_data = obj.data.decode("utf-8")
                
                # 🌟🌟🌟 1. 인식 성공 조건 확인 🌟🌟🌟
                is_match = False
                if self.check_all_mode and decoded_data in QR_DATA_TO_POSE:
                    # check_all_mode일 경우, 디코딩된 데이터가 좌표 딕셔너리에 있기만 하면 성공
                    is_match = True
                elif not self.check_all_mode and decoded_data == self.expected_qr_data:
                    # 일반 모드일 경우, 기대 데이터와 일치해야 성공
                    is_match = True

                
                if is_match:
                    
                    if not self.is_qr_detected:
                        
                        # 목적지 도착 음성 출력 코드 날리기
                        speaker_msg = String()
                        speaker_msg.data = "arrival"
                        self.speaker_pub.publish(speaker_msg)
                        self.get_logger().info("🔊 Published Speaker Command: arrival")
                        
                        
                        self.is_qr_detected = True       # 감지 상태로 변경
                        self.qr_check_active = False     # 검사 즉시 비활성화
                        self.check_all_mode = False      # 모드 초기화
                        
                        self.get_logger().warn(f"✅✅✅ QR 코드 '{decoded_data}' 인식 성공! AMCL 재설정을 요청합니다. ✅✅✅")
                        
                        # 타이머 즉시 취소
                        if self.timeout_timer is not None:
                            self.timeout_timer.cancel()
                            self.timeout_timer = None
                        
                        # AMCL Reset Node에게 명령 발행 (실제 디코딩된 데이터를 보냄)
                        reset_msg = String()
                        reset_msg.data = decoded_data 
                        self.amcl_reset_pub.publish(reset_msg)
                        
                        # @@@:별2::별2::별2:초음파 노드에게 인식 성공 신호 발행 :별2::별2::별2: @@@
                        success_msg = String()
                        # 초음파 노드가 필요한 정보를 담아 발행 (예: "SUCCESS:501")
                        success_msg.data = f"QR_SUCCESS:{decoded_data}"
                        self.qr_success_pub.publish(success_msg)
                        self.get_logger().info(f"Published QR Success Signal: {success_msg.data}")

                        # QR 코드 감지 성공 후 스캔 중지
                        self.expected_qr_data = None
                        
                # ... (기타 QR 코드 표시 로직 유지) ...
                (x, y, w, h) = obj.rect
                # 색상 표시도 is_match를 기준으로 변경
                color = (0, 255, 0) if is_match else (0, 0, 255)
                cv2.rectangle(current_frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(current_frame, decoded_data, (x, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # 디버그 뷰 업데이트
            target_display = self.expected_qr_data if not self.check_all_mode and self.expected_qr_data else ('ALL' if self.check_all_mode else 'None')
            status_text = f"Target: {target_display}. Scanning {'ON' if self.qr_check_active else 'OFF'}"
            cv2.putText(current_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.imshow(f"QR Detector View", current_frame)
            cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f'Image processing failed: {e}')

def main(args=None):
    rclpy.init(args=args)
    qr_detector = QrDetector()
    
    try:
        rclpy.spin(qr_detector)
    except KeyboardInterrupt:
        pass
    
    qr_detector.destroy_node()
    rclpy.shutdown()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
