#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped
from tf_transformations import quaternion_from_euler
import math

# 🌟 QR Detector로부터 명령을 받을 토픽 정의
ROBOT_ROTATE_COMMAND_TOPIC = "/robot_rotate_command"

# 🌟 QR Detector에게 재검사 명령을 보낼 토픽 (기존 QR Detector의 구독 토픽)
QR_COMMAND_TOPIC = "/qr_check_command" 

# 🌟 Nav2 Commander에게 홈 복귀 명령을 보낼 토픽 (실제 nav2_commander.py가 구독하는 토픽으로 수정)
HOME_COMMAND_TOPIC = "/room_command" 

# 🌟 회전 각도 정의 (라디안)
ROTATE_LEFT_45_RAD = math.pi / 4.0   # 왼쪽 45도
ROTATE_RIGHT_90_RAD = -math.pi / 2.0 # 오른쪽 90도 (음수)

# 🌟🌟🌟 최대 회전 횟수 (1회 동작만 허용) 🌟🌟🌟
MAX_ROTATION_COUNT = 1 

class RobotRotator(Node):
    def __init__(self):
        super().__init__('robot_rotator_node')
        self.navigator = BasicNavigator()
        
        # 🌟🌟🌟 회전 횟수 카운터 초기화 🌟🌟🌟
        self.rotation_count = 0 
        
        # --- Nav2 활성화까지 대기 ---
        self.get_logger().info("Nav2 활성화 대기 중...")
        self.navigator.waitUntilNav2Active()
        self.get_logger().info("Nav2 활성화 완료!")

        # 1. 회전 명령 구독 (QR Detector -> RobotRotator)
        self.command_subscription = self.create_subscription(
            String,
            ROBOT_ROTATE_COMMAND_TOPIC, 
            self.rotate_command_callback,
            10
        )
        
        # 2. QR Detector에게 재검사 명령 발행
        self.qr_command_pub = self.create_publisher(
            String,
            QR_COMMAND_TOPIC,
            10
        )

        # 3. Nav2 Commander에게 홈 복귀 명령 발행
        self.home_command_pub = self.create_publisher(
            String,
            HOME_COMMAND_TOPIC,
            10
        )
        
        self.get_logger().info(f'RobotRotator Node started. Waiting for rotation commands on {ROBOT_ROTATE_COMMAND_TOPIC}...')

    def create_relative_goal_pose(self, angle_rad):
        """base_link 프레임 기준으로 회전 목표 PoseStamped를 생성합니다."""
        pose = PoseStamped()
        pose.header.frame_id = "base_link" 
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = 0.0
        pose.pose.position.y = 0.0
        pose.pose.position.z = 0.0
        qx, qy, qz, qw = quaternion_from_euler(0, 0, angle_rad)
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        return pose

    def rotate_robot(self, angle_rad):
        """로봇을 지정된 각도(라디안)만큼 회전시킵니다."""
        
        goal_pose = self.create_relative_goal_pose(angle_rad)
        self.get_logger().warn(f"🔄 로봇 회전 명령 전송: {math.degrees(angle_rad):.1f}도 회전 시작...")
        self.navigator.goToPose(goal_pose) 

        while not self.navigator.isTaskComplete():
            rclpy.spin_once(self, timeout_sec=0.1) 
        
        result = self.navigator.getResult()
        
        if result == TaskResult.SUCCEEDED:
            self.get_logger().warn(f"✅ 회전 완료! {math.degrees(angle_rad):.1f}도 회전 성공.")
            return True
        else:
            self.get_logger().error("❌ 회전 실패 또는 취소되었습니다.")
            return False


    def rotate_command_callback(self, msg: String):
        """QR Detector로부터 회전 명령을 받아 회전을 실행하고 재검사 명령을 발행합니다."""
        full_command = msg.data.strip()
        
        parts = full_command.split(':', 1)
        if len(parts) != 2:
            self.get_logger().error(f"❌ 잘못된 회전 명령 형식 수신: {full_command}. 형식은 'COMMAND:TARGET'이어야 합니다.")
            return
            
        command = parts[0]
        target_command = parts[1] # go_room501 등

        if command == "ROTATE_LEFT_45":
            self.rotation_count += 1
            
            # 🌟🌟🌟 1회 초과 검사 로직 (두 번째 회전 명령은 홈 복귀) 🌟🌟🌟
            if self.rotation_count > MAX_ROTATION_COUNT:
                self.get_logger().error(f"🚨🚨🚨 회전 명령 재수신! (2번째 이상). 홈 복귀 명령을 발행합니다. 🚨🚨🚨")
                
                # 홈 복귀 명령 발행 (토픽: /room_command)
                home_msg = String()
                home_msg.data = "go_home"
                self.home_command_pub.publish(home_msg)
                
                # 카운트 초기화 (다음 임무 대비)
                self.rotation_count = 0
                return

            # 🌟🌟🌟 1회 동작 실행: 왼쪽 45도 회전 🌟🌟🌟
            if self.rotate_robot(ROTATE_LEFT_45_RAD):
                
                # 1. QR Detector에게 재검사 명령 발행 (QR 인식 중이라는 것을 확인하는 용도)
                self.get_logger().warn(f"🔄 왼쪽 45도 회전 완료. QR Detector에게 재검사 명령 ({target_command})을 보냅니다.")
                recheck_msg = String()
                recheck_msg.data = target_command
                self.qr_command_pub.publish(recheck_msg)
                
                # 2. 🌟🌟🌟 (추가) QR 인식 중인지 확인하는 시간 필요 🌟🌟🌟
                # 실제 동작에서는 QR Detector가 응답하거나 타임아웃될 때까지 대기해야 하지만,
                # 여기서는 단순히 *로직 상의 순서*를 맞추기 위해 1초 정도 대기 (실제 로봇 동작에 따라 수정 필요)
                rclpy.spin_once(self, timeout_sec=1.0) 
                
                # 3. 🌟🌟🌟 오른쪽 90도 회전 (총 -45도 위치) 🌟🌟🌟
                if self.rotate_robot(ROTATE_RIGHT_90_RAD):
                    self.get_logger().warn("✅ 1회 회전 동작(L45 -> R90) 완료. 다음 명령 대기 중.")
                
            
        else:
            self.get_logger().warn(f"⚠️ 알 수 없는 회전 명령 수신: {command}")


def main(args=None):
    rclpy.init(args=args)
    robot_rotator = RobotRotator()
    
    try:
        rclpy.spin(robot_rotator)
    except KeyboardInterrupt:
        pass
    
    robot_rotator.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
