from setuptools import find_packages, setup

package_name = 'scout_robot'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name, ['rooms.yaml']),
        ('share/' + package_name + '/launch', ['launch/scout_main_launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hoyeon',
    maintainer_email='hoyeon@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'assign_order_node = scout_robot.assign_order_node:main',
            'nav2_commander = scout_robot.nav2_commander:main',
            'aruco_detector = scout_robot.aruco:main',
            'qr_detector = scout_robot.qr_detector_node:main',
            'room_nav2 = scout_robot.room_nav2:main',
            'amcl_reset = scout_robot.amcl_reset_node:main',
            'robot_rotator = scout_robot.robot_rotator_node:main',
        ],
    },
)
