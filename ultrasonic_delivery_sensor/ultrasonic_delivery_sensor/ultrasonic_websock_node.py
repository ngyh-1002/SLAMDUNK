import rclpy
from rclpy.node import Node
import RPi.GPIO as GPIO
# --- 경고 비활성화 추가 ---
GPIO.setwarnings(False)
# -------------------------
import time
from std_msgs.msg import String

# --- 설정값 ---
TRIG_PIN = 18
ECHO_PIN = 24
DELIVERY_COMPLETE_DISTANCE = 17.0 # 배달 완료 기준 거리 (17cm 이상)
DELIVERY_TOPIC_NAME = '/delivery_status'
ROOM_COMMAND_TOPIC_NAME = '/room_command'
RFID_SUCCESS_TOPIC = '/rfid_detection_success'

class UltrasonicPublisherNode(Node):
    def __init__(self):
        super().__init__('ultrasonic_publisher_node')
        
        self.get_logger().info('🚚 Ultrasonic Delivery Check Node Initialized (Awaiting RFID Success).')

        # 1. ROS 2 Publisher 생성
        self.publisher_ = self.create_publisher(String, DELIVERY_TOPIC_NAME, 10)
        self.command_publisher_ = self.create_publisher(String, ROOM_COMMAND_TOPIC_NAME, 10)

        # 2. ROS 2 Subscriber 생성 (RFID 성공 명령 수신)
        # 미션 완료 후 이 구독 객체를 다시 생성하여 루프를 재개합니다.
        self.subscription = self.create_subscription(
            String,
            RFID_SUCCESS_TOPIC,
            self.rfid_success_callback,
            10
        )
        
        # 3. 상태 변수 초기화
        self.timer = None
        self.delivery_status = False
        self.target_room_number = 'UNKNOWN'
        
        # 스파이크 방지 로직: 연속 완료 카운터
        self.completion_count = 0
        self.REQUIRED_COMPLETION_COUNT = 3 
        
        # 4. GPIO 핀 설정 초기화
        GPIO.setmode(GPIO.BCM)
        
        try:
            GPIO.setup(TRIG_PIN, GPIO.OUT)
            GPIO.setup(ECHO_PIN, GPIO.IN)
            GPIO.output(TRIG_PIN, False)
            time.sleep(0.5)
        except Exception as e:
            self.get_logger().error(f"❌ GPIO Setup Error: {e}. Check RPi.GPIO permissions and pins.")
            

    # ----------------------------------------------------------------------
    # 📌 콜백 함수: RFID 성공 신호 수신 (미션 시작)
    # ----------------------------------------------------------------------
    def rfid_success_callback(self, msg):
        """'/rfid_detection_success' 토픽에서 메시지('RFID_SUCCESS:501' 등)를 수신했을 때 호출됩니다."""
        
        # 타이머가 이미 활성화(모니터링 중)되면 신호를 무시합니다.
        if self.timer is not None:
            self.get_logger().warn('⚠️ Monitoring is already active. Ignoring new RFID signal.')
            return

        raw_data = msg.data.strip()
        room_id = None
        
        # RFID 파싱 로직
        if raw_data.startswith("RFID_SUCCESS:"):
            try:
                room_id = raw_data.split(':')[1].strip()
            except IndexError:
                self.get_logger().warn(f'❌ Malformed RFID signal (missing ID part): {raw_data}')
                return
        
        elif raw_data.isdigit() and len(raw_data) == 3:
            room_id = raw_data
        
        
        # 최종 ID 유효성 검증
        if room_id and room_id.isdigit() and len(room_id) == 3:
            self.target_room_number = room_id
            self.get_logger().info(f'✅ RFID Success received for Room {self.target_room_number}. Starting ultrasonic monitoring.')
        else:
            self.get_logger().warn(f'❌ Invalid RFID signal format: {raw_data} (Parsed ID: {room_id}). Monitoring skipped.')
            return

        # 4. 타이머 생성 (1.0초 간격으로 거리 확인 시작)
        self.timer = self.create_timer(1.0, self.distance_check_callback)
        
        # ❗ RFID 구독 일시 중단 (모니터링이 끝날 때까지 새로운 RFID 신호는 받지 않음)
        self.destroy_subscription(self.subscription)
        self.subscription = None


    # ----------------------------------------------------------------------
    # 📌 초음파 센서 거리 측정 함수
    # ----------------------------------------------------------------------
    def get_distance(self):
        # 센서 초기화 및 펄스 생성 로직
        GPIO.output(TRIG_PIN, False)
        time.sleep(0.000002)
        GPIO.output(TRIG_PIN, True)
        time.sleep(0.00001)
        GPIO.output(TRIG_PIN, False)

        pulse_start = time.time()
        timeout = pulse_start + 0.1 

        while GPIO.input(ECHO_PIN) == 0 and time.time() < timeout:
            pulse_start = time.time()
        
        pulse_end = time.time()
        timeout = pulse_end + 0.1 
        
        while GPIO.input(ECHO_PIN) == 1 and time.time() < timeout:
            pulse_end = time.time()

        pulse_duration = pulse_end - pulse_start
        distance = (pulse_duration * 34300) / 2

        # 비정상적인 값 처리
        if distance > 400 or distance < 0 or pulse_duration > 0.05:
            return -1

        return distance

    # ----------------------------------------------------------------------
    # 📌 타이머 콜백 함수: 거리 확인 및 배달 완료 처리 (루프 로직)
    # ----------------------------------------------------------------------
    def distance_check_callback(self):
        distance = self.get_distance()
        
        if distance == -1:
            self.get_logger().warn('Invalid distance measurement. Resetting count.')
            self.completion_count = 0
            return

        self.get_logger().info(f'Measured Distance: {distance:.2f} cm (Count: {self.completion_count}/{self.REQUIRED_COMPLETION_COUNT})')

        # 배달 완료 조건 검사: 거리가 설정값 이상일 때 (물건 제거 감지)
        if distance >= DELIVERY_COMPLETE_DISTANCE:
            self.completion_count += 1
            
            # 연속 횟수 확인: 3회 이상 연속 측정 시 완료로 판정
            if self.completion_count >= self.REQUIRED_COMPLETION_COUNT and not self.delivery_status:
                
                self.delivery_status = True
                
                # 1. /delivery_status 토픽 발행
                room_tag = f"DELIVERY_COMPLETE_{self.target_room_number}"
                msg_delivery = String()
                msg_delivery.data = room_tag
                self.publisher_.publish(msg_delivery)
                self.get_logger().info(f'✅ Published Delivery Complete Status: "{msg_delivery.data}"')

                # 2. /room_command 토픽에 'go_home' 명령 발행
                msg_command = String()
                msg_command.data = "go_home"
                self.command_publisher_.publish(msg_command)
                self.get_logger().info(f'🏠 Published Go Home Command: "{msg_command.data}"')

                # 💡 루프 로직 시작: 미션 완료 후 타이머 중지 및 RFID 재구독
                if self.timer is not None:
                    self.timer.cancel()
                    self.timer = None
                    self.get_logger().info('Sensor monitoring stopped.')
                    
                    # 🚀 상태 초기화
                    self.delivery_status = False
                    self.target_room_number = 'UNKNOWN'
                    self.completion_count = 0
                    
                    # ❗ RFID 구독 재개 (다음 미션을 받기 위해)
                    self.subscription = self.create_subscription(
                        String,
                        RFID_SUCCESS_TOPIC,
                        self.rfid_success_callback,
                        10
                    )
                    self.get_logger().info('🟢 Ready for next mission. Re-subscribing to /rfid_detection_success.')

        else:
            # 물품이 감지되면 (17cm 미만) 카운트 리셋
            if self.completion_count > 0:
                 self.get_logger().info('Package detected (distance < 17cm). Resetting count.')
            self.completion_count = 0


def main(args=None):
    rclpy.init(args=args)
    node = UltrasonicPublisherNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Node stopped by user (Ctrl+C).')
    except Exception as e:
        node.get_logger().error(f'Unexpected error during spin: {e}')
    finally:
        # 안전한 종료를 위한 정리
        if node.timer is not None:
            node.timer.cancel()
        GPIO.cleanup()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()