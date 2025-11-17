# 파일: scout_robot/launch/scout_main_launch.py

from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # 1. RoomNavigator 노드 정의 (이동 및 명령 발행 담당)
    room_navigator_node = Node(
        package='scout_robot',
        # ⚠️ setup.py에 등록된 nav2_commander.py의 실행 파일 이름
        executable='nav2_commander', 
        name='nav2_commander_node',
        output='screen'
    )

    # 2. QR 코드 인식 노드 정의 (대기 및 감지 후 종료 담당)
    qr_detector_node = Node(
        package='scout_robot', 
        # ⚠️ setup.py에 등록된 qr_detector.py의 실행 파일 이름
        executable='qr_detector',   
        name='qr_detector_node',
        output='screen'
    )
    
    return LaunchDescription([
        room_navigator_node,
        qr_detector_node
    ])
