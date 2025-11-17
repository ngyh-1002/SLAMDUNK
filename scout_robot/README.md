# scout_robot


-----

# 🤖 Scout Robot Navigation System 

## 📌 1. 프로젝트 개요

이 프로젝트는 ROS 2 (Robot Operating System 2) 및 Nav2 스택을 활용하여 자율 이동 로봇인 Scout가 지정된 목표 지점(방 또는 홈)에 도착했음을 **QR 코드 인식**을 통해 최종적으로 검증하는 시스템입니다.

| 항목 | 설명 |
| :--- | :--- |
| **목표** | Nav2를 이용한 자율 주행 후, 목표 지점의 QR 코드를 인식하여 도착을 확정하고 다음 동작을 준비 |
| **주요 기능** | `/room_command` 토픽을 통한 동적 목표 설정 및 QR 코드 기반 목표 달성 확인 |
| **ROS 버전** | ROS 2 Humble/Iron (작업 환경에 맞게 기재) |

-----

## 🛠️ 2. 빌드 매뉴얼 (Build Manual)

이 패키지는 ROS 2 워크스페이스 (`ros2_ws`) 내에서 `colcon`을 사용하여 빌드됩니다.

### 2.1. 코드 클론 및 워크스페이스 이동

터미널을 열고 워크스페이스의 `src` 디렉토리로 이동한 후, 프로젝트 저장소를 클론합니다.

```bash
# 1. src 디렉토리로 이동
cd ~/ros2_ws/src

# 2. 프로젝트 저장소 클론
git clone https://github.com/ngyh-1002/scout_robot.git
```

### 2.2. 패키지 빌드

워크스페이스 루트 디렉토리로 돌아가 `colcon build` 명령을 사용하여 `scout_robot` 패키지만 빌드합니다.

```bash
# 3. 워크스페이스 루트로 이동
cd ~/ros2_ws

# 4. 패키지 빌드 및 설치 경로 심볼릭 링크 생성
colcon build --packages-select scout_robot --symlink-install
```

### 2.3. 환경 설정 반영 (Source)

빌드된 패키지를 실행 환경에 반영합니다. 이는 새로운 터미널을 열 때마다 실행해야 합니다.

```bash
# 5. 환경 설정 반영
source ~/ros2_ws/install/setup.bash
```

-----

## 🚀 3. 노드 실행 명령어

**주의:** 네비게이션을 실행하기 전에 ROS 2 환경과 로봇 시뮬레이션 환경(Gazebo, Rviz 등)이 먼저 실행되어 있어야 합니다.

### 3.1. QR 인식 노드 실행

카메라 토픽 (`/image_raw/compressed`)을 구독하여 QR 코드를 감지하고, `/room_command` 토픽을 구독하여 기대 QR 코드를 동적으로 설정하는 노드를 실행합니다.

```bash
ros2 run scout_robot qr_detector
```

### 3.2. 네비게이션 명령 노드 실행

Nav2 Goal Action을 사용하여 목표 지점 이동 명령을 내리고, `/room_command` 토픽을 구독하여 QR 인식 노드로부터의 도착 확인 피드백을 처리하는 노드를 실행합니다.

```bash
ros2 run scout_robot nav2_commander
```

### 1\. 📍 `amcl_reset_node.py` (AmclResetter) 실행 매뉴얼

이 노드는 로봇이 QR 코드를 성공적으로 인식했을 때, \*\*AMCL (Adaptive Monte Carlo Localization)\*\*의 위치를 해당 QR 코드의 좌표로 강제로 재설정하는 역할을 합니다.

#### 🌟 핵심 역할

| 기능 | 설명 |
| :--- | :--- |
| **Localization 강제 재설정** | `/initialpose` 토픽 발행을 통해 AMCL의 위치 추정값(x, y, $\theta$)을 QR 코드 좌표로 강제 재배치 |
| **Home 복귀 후 임무 재개** | QR 데이터가 'home'일 경우, 다음 임무 (`go_start`)를 `RoomNavigator`에게 지시 |

#### 🔑 작동 원리

1.  **구독**: `QrDetector` 노드로부터 `/amcl_reset_command` 토픽을 받습니다. (예: `"501"`, `"home"`)
2.  **좌표 매핑**: 수신된 QR 데이터(`"501"`)를 `rooms.yaml` 파일에 매핑된 실제 지도 좌표 (x, y, $\theta$)로 변환합니다.
3.  **발행**: 변환된 좌표를 `/initialpose` 토픽으로 발행하여 AMCL 스택을 재배치합니다.
4.  **조건부 발행**: 수신된 QR 데이터가 \*\*`"home"`\*\*일 경우에만 `/room_command` 토픽에 `"go_start"` 명령을 추가로 발행하여 로봇을 시작 위치로 복귀시킵니다.

#### 🚀 실행 명령

```bash
# 터미널에서 ROS 2 환경이 설정되어 있는지 확인 후 실행합니다.
# (예: source install/setup.bash)

ros2 run scout_robot amcl_reset_node.py
```

-----

### 2\. 🔄 `robot_rotator_node.py` (RobotRotator) 실행 매뉴얼

이 노드는 `QrDetector`가 QR 코드를 인식하지 못했을 때 호출되어, 로봇을 45도씩 회전시키고 재검사를 요청하는 역할을 합니다.

#### 🌟 핵심 역할

| 기능 | 설명 |
| :--- | :--- |
| **로봇 회전** | Nav2를 사용하여 로봇을 **45도**씩 회전시킵니다. |
| **재검사 요청** | 회전 성공 후 `QrDetector`에게 **QR 재검사**를 요청합니다. |
| **최대 횟수 제한** | 회전 횟수가 8회를 초과하면 **홈 복귀 명령**을 강제 발행합니다. |

#### 🔑 작동 원리

1.  **구독**: `QrDetector` 노드로부터 `/robot_rotate_command` 토픽을 받습니다. (예: `"ROTATE_LEFT_45:go_room501"`)
2.  **카운트**: 내부 변수 `self.rotation_count`를 **+1** 합니다.
3.  **최대 횟수 확인**:
      * **8회 이하**: 로봇을 **45도 회전** (`rotate_robot` 함수)시키고, 성공 시 `/qr_check_command` 토픽에 목표 명령(예: `"go_room501"`)을 발행하여 `QrDetector`에게 재검사를 요청합니다.
      * **8회 초과**: `/room_command` 토픽에 **`"go_home"`** 명령을 발행하여 로봇에게 임무를 포기하고 기지로 복귀하도록 지시합니다.

#### 🚀 실행 명령

```bash
# 터미널에서 ROS 2 환경이 설정되어 있는지 확인 후 실행합니다.

ros2 run scout_robot robot_rotator_node.py
```
### 3.3. 명령 발행 (예시)

`nav2_commander` 노드가 실행 중일 때, 새로운 터미널에서 아래 명령을 통해 로봇에게 이동 목표를 지정할 수 있습니다.

```bash
# 로봇에게 501호로 이동 명령 (QR 코드로 '501'을 기대함)
ros2 topic pub --once /room_command std_msgs/String "data: 'go_room501'" --qos-reliability reliable
```

-----

---

# 🤖 자율주행 로봇 네비게이션 시스템 (ROS 2/Nav2 기반)

본 시스템은 Nav2의 `BasicNavigator`와 **토픽 기반 상태 제어 알고리즘**을 활용하여 로봇의 자율 이동, QR 코드 인식 및 위치 재설정 임무를 수행합니다.

## 1. 🗺️ 네비게이션 기본 원리 및 커스텀 구현

Nav2 스택은 일반적으로 **RViz의 GUI 상호작용**을 통해 작동합니다.

| RViz 표준 작동 방식 | 본 시스템의 작동 방식 | 비고 |
| :--- | :--- | :--- |
| **초기 위치 추정** | `2D Pose Estimate` 버튼으로 `/initialpose` 토픽 발행 | `RoomNavigator`의 `setInitialPose()` 또는 `AmclResetter`의 `/initialpose` 토픽 발행 |
| **목표 위치 설정** | `2D Goal Pose` 버튼으로 `/goal_pose` 토픽 발행 | `RoomNavigator`에서 `rooms.yaml` 파일의 좌표를 읽어 `navigator.goToPose()` 호출 |
| **경로 계획/실행** | `Global Planner`와 `Local Planner` 자동 실행 | `BasicNavigator`가 Nav2 액션 서버와 통신하여 **자동 처리** |

### ✨ 좌표 관리 및 변환

시스템은 **`rooms.yaml`** 파일을 사용하여 목표 위치 좌표를 관리하며, 이는 Rviz의 **`2D Goal Pose`** 역할을 대신합니다.

#### A. 좌표 파일 생성

`rooms.yaml` 파일은 다음과 같은 방식으로 생성됩니다.

1.  **로컬라이제이션 정보 수집**: AMCL은 로봇의 위치를 **`/amcl_pose`** 토픽으로 발행합니다.
    * 위치: $x, y$ (m)
    * 방향: $z, w$ (쿼터니언 성분)
2.  **쿼터니언 $\rightarrow$ 오일러(Theta) 변환**: `/amcl_pose`에서 얻은 쿼터니언($z, w$) 값을 로봇이 이해하기 쉬운 **Yaw 각도 ($\theta$)**로 변환하여 YAML 파일에 기록합니다.

#### B. 쿼터니언 to Yaw 수식

Nav2와 ROS 2에서 사용하는 표준 **쿼터니언 (Quaternion)**의 $z, w$ 성분으로부터 **Yaw ($\theta$)** 각도를 라디안(radian)으로 변환하는 수식은 다음과 같습니다.

$$
\theta = \text{atan2}(2 \cdot (q_w \cdot q_z + q_x \cdot q_y), 1 - 2 \cdot (q_y^2 + q_z^2))
$$

* 여기서 $q_x=0, q_y=0$ (2D 평면 네비게이션 가정)이므로, 수식은 다음과 같이 단순화됩니다:

$$
\theta = \text{atan2}(2 \cdot q_w \cdot q_z, 1 - 2 \cdot q_z^2)
$$

## 2. 🔄 토픽 기반 상태 제어 알고리즘 (핵심)

본 시스템은 **"구독 $\rightarrow$ 노드 작동 $\rightarrow$ 발행 $\rightarrow$ 노드 작동 중지"**라는 명확한 순차적 임무 흐름을 통해 Nav2의 안정성을 확보하고 복잡한 임무(QR 검사 및 회전)를 분리하여 처리합니다.

### 시스템 노드 및 토픽 흐름 요약

| 노드 (파일) | 구독 토픽 (시작 트리거) | 발행 토픽 (임무 완료/위임) | 임무 (작동 중 로직) |
| :--- | :--- | :--- | :--- |
| **RoomNavigator** (`nav2_commander.py`) | `/room_command` | `/qr_check_command` | Nav2 목표 좌표로 이동 (BasicNavigator 사용) |
| **QrDetector** (`qr_detector_node.py`) | `/qr_check_command` | `/amcl_reset_command` **OR** `/robot_rotate_command` | 기대 QR 스캔 (10초 타이머), 성공/실패에 따라 명령 위임 |
| **AmclResetter** (`amcl_reset_node.py`) | `/amcl_reset_command` | `/room_command` (QR이 'home'일 때만) | AMCL 위치 강제 재설정 (`/initialpose` 발행) |
| **RobotRotator** (`robot_rotator_node.py`) | `/robot_rotate_command` | `/qr_check_command` **OR** `/room_command` | 45도 회전 (최대 8회), 8회 초과 시 'go\_home' 명령 발행 |

### 임무 순환의 특징

* **상태 분리**: 로봇이 이동할 때 (`RoomNavigator` 작동), QR 코드를 스캔하거나 회전하는 등의 다른 복잡한 로직은 **절대 동시에 실행되지 않습니다.**
* **동기적 처리**: `RoomNavigator`의 `move_and_wait` 함수와 `RobotRotator`의 `rotate_robot` 함수는 **Nav2 액션이 완료될 때까지** `rclpy.spin_once`를 사용하여 확실하게 대기합니다.
* **작동 중지**: 한 노드가 임무를 완수하고 다음 임무를 트리거하는 토픽을 발행하면, 해당 노드는 다음 구독 명령을 받을 때까지 사실상 **대기 상태(작동 중지)**로 전환됩니다.
