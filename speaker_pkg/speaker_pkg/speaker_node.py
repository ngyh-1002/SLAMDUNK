import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os
import json

class SpeakerNode(Node):
    def __init__(self):
        super().__init__('speaker_node')
        self.subscription = self.create_subscription(
            String,
            'speaker_command',
            self.command_callback,
            10
        )

    def command_callback(self, msg):
        try:
            data = json.loads(msg.data)
            command = data.get("command")
            room = data.get("room")
        except Exception:
            # JSON이 아닐 경우, 그냥 문자열로 처리
            command = msg.data
            room = None
        
        # 배달을 시작합니다.
        if command == "start_delivery":
            self.get_logger().info("배달 시작 음성 재생")
            os.system("aplay ~/sound/start_delivery.wav")

        # 목적지에 도착했습니다.
        if command == "arrival":
            self.get_logger().info("arrival 음성 재생")
            os.system("aplay ~/sound/arrival.wav")

        # 인증 성공
        if command == "user_sucess":
            self.get_logger().info("user_sucess 재생")
            os.system("aplay ~/sound/user_sucess.wav")

        # 인증 실패
        if command == "user_fail":
            self.get_logger().info("user_fail 재생")
            os.system("aplay ~/sound/user_fail.wav")

        if command == "user_authentication":
            self.get_logger().info("user_authentication 재생")
            os.system("aplay ~/sound/user_authentication.wav")

        # 배달 완료
        if command == "finish_delivery":
            self.get_logger().info("finish_delivery 재생")
            os.system("aplay ~/sound/finish_delivery.wav")

        # 다녀왔습니다.
        if command == "home":
            self.get_logger().info("home 재생")
            os.system("aplay ~/sound/home.wav")



def main(args=None):
    rclpy.init(args=args)
    node = SpeakerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
