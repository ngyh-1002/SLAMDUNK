import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class ScoutAssignOrderNode(Node):
    def __init__(self):
        super().__init__('scout_assign_order_node')
        # /scout/assign_order 토픽 구독
        self.subscription = self.create_subscription(
            String,
            '/scout/assign_order',
            self.order_callback,
            10  # 큐 사이즈
        )

    def order_callback(self, msg: String):
        order_number = msg.data
        self.get_logger().info(f'배달 주문 수신: {order_number}')
        # 여기서 실제 스카우트 미니 배달 명령 실행
        self.start_delivery(order_number)

    def start_delivery(self, order_number: str):
        # TODO: 로봇 제어 로직
        self.get_logger().info(f'주문 {order_number} 배달 시작!')

def main(args=None):
    rclpy.init(args=args)
    node = ScoutAssignOrderNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
