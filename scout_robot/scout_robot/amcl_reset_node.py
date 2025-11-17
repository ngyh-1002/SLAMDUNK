#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseWithCovarianceStamped
from ament_index_python.packages import get_package_share_directory
from tf_transformations import quaternion_from_euler
import numpy as np
import os
import yaml

# 🌟 QR Detector로부터 명령을 받을 토픽 정의
AMCL_RESET_COMMAND_TOPIC = "/amcl_reset_command"
# 🌟 Nav2 Commander에게 복귀 명령을 보낼 토픽 정의
ROOM_COMMAND_TOPIC = "/room_command" # 🌟🌟🌟 추가 🌟🌟🌟

# Nav2 명령과 기대 QR 데이터 매핑 딕셔너리 (좌표 로드에 사용)
COMMAND_TO_QR_MAP = {
    "go_room501": "501",
    "go_home": "home",  
    "go_room502": "502",
    "go_room503": "503",
}

# QR 데이터에 해당하는 좌표 딕셔너리
QR_DATA_TO_POSE = {}


class AmclResetter(Node):
    def __init__(self):
        super().__init__('amcl_reset_node')
        
        self.load_room_coordinates() # 좌표 로드
        
        # 1. 🌟 AMCL 리셋 명령 구독 (QR Detector -> AmclResetter)
        self.command_subscription = self.create_subscription(
            String,
            AMCL_RESET_COMMAND_TOPIC, 
            self.reset_command_callback,
            10
        )
        
        # 2. 초기 위치 재설정 발행 (AMCL에게)
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped,
            '/initialpose',
            10
        )
        
        # 3. 🌟🌟🌟 RoomNavigator에게 명령 발행 (home 복귀 후 start 이동용) 🌟🌟🌟
        self.room_command_pub = self.create_publisher(
            String,
            ROOM_COMMAND_TOPIC,
            10
        )
        
        self.get_logger().info(f'AmclResetter Node started. Waiting for reset commands on {AMCL_RESET_COMMAND_TOPIC}...')

    def load_room_coordinates(self):
        """rooms.yaml 파일을 읽어 QR 코드에 해당하는 좌표를 로드합니다."""
        global QR_DATA_TO_POSE
        package_share = get_package_share_directory('scout_robot')
        yaml_path = os.path.join(package_share, 'rooms.yaml')
        
        try:
            with open(yaml_path, 'r') as f:
                rooms_data = yaml.safe_load(f)['rooms']
                
            # QR 데이터에 해당하는 실제 좌표 매핑
            for room_name, data in rooms_data.items():
                qr_data_key = room_name.replace("room", "").replace("start", "start").replace("home", "home")
                if qr_data_key:
                    QR_DATA_TO_POSE[qr_data_key] = data
                    
            self.get_logger().info("✅ rooms.yaml에서 AMCL 리셋 목표 좌표 로드 완료.")
        
        except FileNotFoundError:
            self.get_logger().error(f"rooms.yaml 파일을 찾을 수 없습니다: {yaml_path}")


    def publish_initial_pose(self, pose_data):
        """AMCL에 위치를 강제 재설정하도록 명령합니다."""
        x, y, theta = pose_data['x'], pose_data['y'], pose_data['theta']
        
        initial_pose_msg = PoseWithCovarianceStamped()
        initial_pose_msg.header.frame_id = "map"
        initial_pose_msg.header.stamp = self.get_clock().now().to_msg()

        initial_pose_msg.pose.pose.position.x = x
        initial_pose_msg.pose.pose.position.y = y
        initial_pose_msg.pose.pose.position.z = 0.0

        q = quaternion_from_euler(0, 0, theta)
        initial_pose_msg.pose.pose.orientation.x = q[0]
        initial_pose_msg.pose.pose.orientation.y = q[1]
        initial_pose_msg.pose.pose.orientation.z = q[2]
        initial_pose_msg.pose.pose.orientation.w = q[3]

        # 🌟🌟 공분산 강제 확정 (낮은 불확실성으로 강제 재설정) 🌟🌟
        COV_X, COV_Y, COV_YAW = 1e-9, 1e-9, 1e-9
        
        initial_pose_msg.pose.covariance = np.array([
            COV_X, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, COV_Y, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, COV_YAW 
        ]).flatten().tolist()
        
        self.initial_pose_pub.publish(initial_pose_msg)
        self.get_logger().error(f"✅✅✅ AMCL 위치 재설정 완료! 좌표: ({x:.2f}, {y:.2f}, {theta:.2f} rad) ✅✅✅")


    def reset_command_callback(self, msg: String):
        """QR Detector로부터 AMCL 재설정 명령을 받아 처리합니다."""
        qr_data = msg.data.strip()
        
        if qr_data in QR_DATA_TO_POSE:
            pose_data = QR_DATA_TO_POSE[qr_data]
            self.get_logger().warn(f"🌟 '{qr_data}' QR 데이터 수신! AMCL 위치 재설정 시작...")
            self.publish_initial_pose(pose_data)
            
            # 🌟🌟🌟 QR 데이터가 'home'일 경우 RoomNavigator에게 'go_start' 명령 발행 🌟🌟🌟
            if qr_data == "home":
                start_msg = String()
                start_msg.data = "go_start"
                self.room_command_pub.publish(start_msg)
                self.get_logger().warn("🏠 'home' QR 인식 후, RoomNavigator에게 'go_start' 명령 발행.")
                
        else:
            self.get_logger().error(f"❌ 알 수 없는 QR 데이터 '{qr_data}' 수신. AMCL 재설정 실패.")


def main(args=None):
    rclpy.init(args=args)
    amcl_resetter = AmclResetter()
    
    try:
        rclpy.spin(amcl_resetter)
    except KeyboardInterrupt:
        pass
    
    amcl_resetter.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
