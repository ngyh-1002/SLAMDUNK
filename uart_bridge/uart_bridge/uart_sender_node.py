import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
import time
import json

# ===========================================================================

class UARTSender(Node):
    def __init__(self):
        super().__init__('uart_sender')
        
        # --- 1. UART (시리얼 통신) 설정 ---
        # ⚠️ 연결 포트('/dev/ttyACM0')를 실제 환경에 맞게 수정하세요.
        self.SERIAL_PORT = '/dev/ttyACM0'
        self.BAUD_RATE = 115200
        
        try:
            self.ser = serial.Serial(self.SERIAL_PORT, self.BAUD_RATE, timeout=0.1)
            self.get_logger().info(f'✅ UART Connected: {self.SERIAL_PORT} @ {self.BAUD_RATE} bps')
        except serial.SerialException as e:
            self.get_logger().error(f'❌ Failed to open serial port {self.SERIAL_PORT}: {e}')
            self.ser = None # 통신 실패 시 None으로 설정

        # --- 2. 토픽 구독 설정 (QR 디텍터 성공 신호 수신) ---
        self.subscription = self.create_subscription(
            String,
            '/qr_detection_success',
            self.qr_success_callback,
            10
        )
        self.get_logger().info('✅ Subscribing to /qr_detection_success')

        # --- 3. 토픽 발행 설정 (RFID 인식 성공 신호 발행) ---
        self.publisher_ = self.create_publisher(
            String,
            '/rfid_detection_success',
            10
        )

        # 스피커 노드 설정
        self.speaker_pub = self.create_publisher(
            String,
            '/speaker_command', 
            10
        )

        self.get_logger().info('✅ Publishing to /rfid_detection_success')

        # --- 4. Pico 상태 확인 타이머 (UART 수신 체크) ---
        # 100ms 마다 Pico의 응답을 확인합니다.
        self.timer = self.create_timer(0.1, self.check_pico_status) 
        
        # --- 5. 상태 관리 변수 ---
        self.current_target_room = "NONE" # 현재 RFID 인식을 대기하는 목표 호실 (예: "501")
        
        self.get_logger().info('✅ UARTSender Node Initialized.')

    # --------------------------------------------------------------------------
    # 📌 콜백 함수: QR 디텍터 토픽 수신 (입력)
    # --------------------------------------------------------------------------
    def qr_success_callback(self, msg: String):
        """QR 인식 성공 신호를 받아 Pico에게 방 번호(501)를 전달합니다."""
        data = msg.data.strip() # 예: "QR_SUCCESS:501"
        self.get_logger().info(f"🟡 Received QR Success Topic: {data}") # 👈 토픽 수신 확인 로그
        
        if not self.ser:
            self.get_logger().warn('⚠️ UART Not Connected. Cannot send QR command to Pico.')
            return

        if data.startswith("QR_SUCCESS:"):
            try:
                # 'QR_SUCCESS:501'에서 '501' 추출
                room_id = data.split(':')[1].strip()
            except IndexError:
                self.get_logger().warn(f'⚠️ Malformed QR Success data received: {data}')
                return
            
            # 호실 번호가 숫자로 구성된 3자리인지 확인
            if room_id.isdigit() and len(room_id) == 3:
                # Pico로 보낼 명령어 (예: "501\n")
                command = f"{room_id}\n" 
                
                # UART 전송 및 상태 업데이트
                self.send_to_pico(command)
                self.current_target_room = room_id
                
                # 👈 RFID 인식 대기 상태 알림 로그
                self.get_logger().info(f'✅ [QR Trigger] Sent command "{room_id}" to Pico. Waiting for RFID response for Room {self.current_target_room}...')
            else:
                self.get_logger().warn(f'⚠️ Received invalid Room ID format: {room_id}')
        else:
              self.get_logger().warn(f'⚠️ Unrecognized QR Success format: {data}')

    # --------------------------------------------------------------------------
    # 📌 타이머 콜백: Pico로부터 RFID 인식 결과 수신 (출력)
    # --------------------------------------------------------------------------
    def check_pico_status(self):
        """Pico로부터 RFID 성공 신호를 주기적으로 확인하고 ROS 2 토픽으로 발행합니다."""
        if not self.ser or self.ser.in_waiting == 0:
            return

        try:
            # UART에서 데이터 라인을 읽고 디코딩 및 공백 제거
            received_data = self.ser.readline().decode('utf-8').strip()
            
            if not received_data: # 빈 줄이면 처리하지 않음
                return

            # 👈 UART에서 받은 모든 데이터 로그 (디버그 수준)
            self.get_logger().debug(f'UART Raw Data Received: {received_data}') 

            # Pico에서 보낸 성공 신호 형식인지 확인 (예: 'RFID_OK_501')
            if received_data.startswith("RFID_OK_"):
                
                # 'RFID_OK_501'에서 '501' 추출
                try:
                    room_id = received_data.split('_')[2].strip()
                except IndexError:
                    self.get_logger().warn(f'⚠️ Malformed RFID Success data from Pico: {received_data}')
                    return

                # 호실 번호 유효성 및 현재 대기 중인 호실과 일치하는지 확인
                if room_id == self.current_target_room:
                    
                    # ROS 2 토픽 발행 (/rfid_detection_success)
                    msg = String()
                    msg.data = f"RFID_SUCCESS:{room_id}"
                    self.publisher_.publish(msg)
                    
                    # 스피커 토픽 발행 (/speaker_command)
                    speaker_msg = String()
                    payload = {
                        "command": "user_sucess",
                        "room": room_id
                    }
                    speaker_msg.data = json.dumps(payload, ensure_ascii=False)
                    self.speaker_pub.publish(speaker_msg)
                    self.get_logger().info("🔊 Published Speaker Command: user_sucess")

                    # 👈 RFID 인식 완료 및 토픽 발행 알림 로그
                    self.get_logger().info(f'🟢 Published RFID Success Topic for Room: {room_id}') 
                    
                    # 미션 완료 후 대기 상태로 변경
                    self.current_target_room = "NONE"
                    
                elif room_id.isdigit() and len(room_id) == 3:
                    # 👈 다른 카드가 인식된 상황
                    self.get_logger().warn(f'⚠️ RFID Mismatch: Expected {self.current_target_room} but received {room_id}.')

                    # 스피커 토픽 발행 (인증 실패)
                    speaker_msg = String()
                    payload = {
                        "command": "user_fail",
                        "room": room_id
                    }
                    speaker_msg.data = json.dumps(payload, ensure_ascii=False)
                    self.speaker_pub.publish(speaker_msg)
                    self.get_logger().info("🔊 Published Speaker Command: user_fail")

            # 👈 'RFID_OK_'가 아닌 다른 데이터 수신 (Pico의 디버그 print문일 가능성이 높음)
            else:
                self.get_logger().info(f'Received message from Pico (Other card/Error): {received_data}')
            

        except UnicodeDecodeError:
            self.get_logger().error('❌ UART decode error.')
        except Exception as e:
            self.get_logger().error(f'❌ An unexpected error occurred in check_pico_status: {e}')


    # --------------------------------------------------------------------------
    # 📌 헬퍼 함수: Pico로 UART 데이터 전송
    # --------------------------------------------------------------------------
    def send_to_pico(self, data: str):
        """Pico로 데이터를 인코딩하여 전송합니다."""
        if self.ser and self.ser.is_open:
            self.ser.write(data.encode('utf-8'))
        else:
            self.get_logger().warn('⚠️ UART connection is not open. Data not sent.')

def main(args=None):
    rclpy.init(args=args)
    uart_sender = UARTSender()
    
    # 노드 실행 중 시리얼 통신이 끊어지면 에러가 발생하므로 try-except로 감싸줍니다.
    try:
        rclpy.spin(uart_sender)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        uart_sender.get_logger().error(f'Node failed with exception: {e}')
    finally:
        # 종료 시 시리얼 포트 닫기
        if uart_sender.ser and uart_sender.ser.is_open:
            uart_sender.ser.close()
            uart_sender.get_logger().info('🔌 UART Closed.')
        
        # 노드 종료
        uart_sender.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()