## 📌 1. 프로젝트 개요

이 프로젝트는 ROS 2 (Robot Operating System 2) 및 Nav2 스택을 활용하여 자율 이동 로봇인 Scout가 지정된 목표 지점(방 또는 홈)에 도착했음을 **QR 코드 인식**, **RFID 태그 인식**, 및 **초음파 센서**를 통한 배달 물품 제거 감지를 통해 최종적으로 검증하고 음성 피드백을 제공하는 통합 시스템입니다.

| 항목 | 설명 |
| :--- | :--- |
| **목표** | Nav2를 이용한 자율 주행 후, RFID 인식, 초음파 센서 감지, 및 음성 출력을 통합하여 복합 임무 수행 |
| **주요 기능** | `/room_command` 토픽을 통한 동적 목표 설정 및 QR 코드/RFID/초음파 센서 기반 목표 달성 확인 및 음성 알림 |
| **ROS 버전** | ROS 2 Humble |


-----

## 🚀 2. 노드 실행 명령어

**주의:** 네비게이션을 실행하기 전에 ROS 2 환경과 로봇 시뮬레이션 환경(Gazebo, Rviz 등)이 먼저 실행되어 있어야 합니다.

### 2.1. 네비게이션 및 QR 코드 관련 노드 실행

| 노드 파일 | 패키지 명 | 실행 명령 | 설명 |
| :--- | :--- | :--- | :--- |
| `qr_detector_node.py` | `scout_robot` | `ros2 run scout_robot qr_detector` | 카메라 토픽 구독, QR 감지 및 기대 QR 동적 설정 |
| `nav2_commander.py` | `scout_robot` | `ros2 run scout_robot nav2_commander` | Nav2 목표 이동 명령 및 도착 피드백 처리 |
| `amcl_reset_node.py` | `scout_robot` | `ros2 run scout_robot amcl_reset_node.py` | QR 좌표로 AMCL 위치 강제 재설정 (`/initialpose` 발행) |
| `robot_rotator_node.py`| `scout_robot` | `ros2 run scout_robot robot_rotator_node.py` | QR 인식 실패 시 로봇 45도 회전 및 재검사 요청 |

### 2.2. I/O 및 센서 제어 노드 실행 (추가된 노드)

| 노드 파일 | 패키지 명 | 실행 명령 | 설명 |
| :--- | :--- | :--- | :--- |
| `uart_sender_node.py` | `uart_bridge` | `ros2 run uart_bridge uart_sender_node` | **UART 통신**: QR 성공 신호를 Pico로 전송하고, RFID 성공/실패 신호를 수신하여 토픽 발행 및 스피커 제어 |
| `speaker_node.py` | `speaker_pkg` | `ros2 run speaker_pkg speaker_node` | **음성 출력**: `/speaker_command` 토픽에 따라 `.wav` 파일을 재생하여 음성 피드백 제공 (`aplay` 사용) |
| `ultrasonic_websock_node.py`| `ultrasonic_delivery_sensor`| `ros2 run ultrasonic_delivery_sensor ultrasonic_node` | **초음파 센서**: RFID 성공 후 배달 물품 제거 감지 및 배달 완료 명령 발행 |

### 2.3. 명령 발행 (예시)

`nav2_commander` 노드가 실행 중일 때, 새로운 터미널에서 아래 명령을 통해 로봇에게 이동 목표를 지정할 수 있습니다.

```bash
# 로봇에게 501호로 이동 명령 (QR 코드로 '501'을 기대함)
ros2 topic pub --once /room_command std_msgs/String "data: 'go_room501'" --qos-reliability reliable
```

-----

## 3\. 🔄 토픽 기반 상태 제어 알고리즘 (핵심)

본 시스템은 \*\*"구독 $\rightarrow$ 노드 작동 $\rightarrow$ 발행 $\rightarrow$ 노드 작동 중지"\*\*라는 명확한 순차적 임무 흐름을 통해 Nav2의 안정성을 확보하고 복잡한 임무를 분리하여 처리합니다.

### 시스템 노드 및 토픽 흐름 요약

| 노드 (파일) | 구독 토픽 (시작 트리거) | 발행 토픽 (임무 완료/위임) | 임무 (작동 중 로직) |
| :--- | :--- | :--- | :--- |
| **RoomNavigator** (`nav2_commander.py`) | `/room_command` | `/qr_check_command` | Nav2 목표 좌표로 이동 (BasicNavigator 사용) |
| **QrDetector** (`qr_detector_node.py`) | `/qr_check_command` | `/amcl_reset_command` **OR** `/robot_rotate_command` | 기대 QR 스캔 (10초 타이머), 성공/실패에 따라 명령 위임 |
| **AmclResetter** (`amcl_reset_node.py`) | `/amcl_reset_command` | `/room_command` (QR이 'home'일 때만) | AMCL 위치 강제 재설정 (`/initialpose` 발행) |
| **RobotRotator** (`robot_rotator_node.py`) | `/robot_rotate_command` | `/qr_check_command` **OR** `/room_command` | 45도 회전 (최대 8회), 8회 초과 시 'go\_home' 명령 발행 |
| **UARTSender** (`uart_sender_node.py`)| `/qr_detection_success` | `/rfid_detection_success`, `/speaker_command` | QR 성공 신호를 Pico에 전송, RFID 응답 수신 후 토픽 발행 및 음성 출력 |
| **SpeakerNode** (`speaker_node.py`) | `/speaker_command` | **없음** | 수신된 명령에 따라 `aplay`로 음성 파일 재생 |
| **UltrasonicPublisherNode** (`ultrasonic_websock_node.py`)| `/rfid_detection_success` | `/delivery_status`, `/room_command` | RFID 성공 후 초음파 센서로 물품 제거 감지 (연속 3회) 후 배달 완료 및 'go\_home' 명령 발행 |

### 임무 순환의 특징

  * **상태 분리**: 이동, QR 스캔, 회전, RFID 체크, 배달 완료 감지 등의 복잡한 로직은 **절대 동시에 실행되지 않고** 순차적으로 처리됩니다.
  * **동기적 처리**: `RoomNavigator`의 `move_and_wait` 함수와 `RobotRotator`의 `rotate_robot` 함수는 Nav2 액션 완료를 **확실하게 대기**합니다.
  * **작동 중지**: 한 노드가 임무를 완수하고 다음 임무를 트리거하는 토픽을 발행하면, 해당 노드는 다음 구독 명령을 받을 때까지 사실상 **대기 상태**로 전환됩니다.

-----

## 4\. 🗺️ 네비게이션 기본 원리 및 커스텀 구현

Nav2 스택은 일반적으로 **RViz의 GUI 상호작용**을 통해 작동합니다.

| RViz 표준 작동 방식 | 본 시스템의 작동 방식 | 비고 |
| :--- | :--- | :--- |
| **초기 위치 추정** | `2D Pose Estimate` 버튼으로 `/initialpose` 토픽 발행 | `RoomNavigator`의 `setInitialPose()` 또는 `AmclResetter`의 `/initialpose` 토픽 발행 |
| **목표 위치 설정** | `2D Goal Pose` 버튼으로 `/goal_pose` 토픽 발행 | `RoomNavigator`에서 `rooms.yaml` 파일의 좌표를 읽어 `navigator.goToPose()` 호출 |
| **경로 계획/실행** | `Global Planner`와 `Local Planner` 자동 실행 | `BasicNavigator`가 Nav2 액션 서버와 통신하여 **자동 처리** |

### ✨ 좌표 관리 및 변환

시스템은 **`rooms.yaml`** 파일을 사용하여 목표 위치 좌표를 관리하며, 이는 Rviz의 **`2D Goal Pose`** 역할을 대신합니다.

#### A. 쿼터니언 to Yaw 수식

Nav2와 ROS 2에서 사용하는 표준 \*\*쿼터니언 (Quaternion)\*\*의 $z, w$ 성분으로부터 **Yaw ($\theta$)** 각도를 라디안(radian)으로 변환하는 수식은 다음과 같습니다.

$$
\theta = \text{atan2}(2 \cdot q_w \cdot q_z, 1 - 2 \cdot q_z^2)
$$

-----

## 🛠️ 5. 빌드 매뉴얼 (Build Manual)

이 패키지들은 ROS 2 워크스페이스 (`ros2_ws`) 내에서 `colcon`을 사용하여 빌드됩니다.

### 5.1. 코드 클론 및 워크스페이스 이동

터미널을 열고 워크스페이스의 `src` 디렉토리로 이동한 후, 프로젝트 저장소를 클론합니다.

```bash
# 1. src 디렉토리로 이동
cd ~/ros2_ws/src

# 2. 프로젝트 저장소 클론 (scout_robot은 기존 내용 유지)
git clone https://github.com/ngyh-1002/SLAMDUNK.git
```

### 5.2. 패키지 빌드

워크스페이스 루트 디렉토리로 돌아가 `colcon build` 명령을 사용하여 필요한 모든 패키지를 빌드합니다.

```bash
# 3. 워크스페이스 루트로 이동
cd ~/ros2_ws

# 4. 모든 패키지 빌드 및 설치 경로 심볼릭 링크 생성
colcon build --symlink-install
# 혹은 특정 패키지만 빌드
# colcon build --packages-select scout_robot uart_bridge speaker_pkg ultrasonic_delivery_sensor --symlink-install
```

### 5.3. 환경 설정 반영 (Source)

빌드된 패키지를 실행 환경에 반영합니다. 이는 새로운 터미널을 열 때마다 실행해야 합니다.

```bash
# 5. 환경 설정 반영
source ~/ros2_ws/install/setup.bash
```

[**navigation기능 상세설명**](https://github.com/ngyh-1002/scout_robot)
