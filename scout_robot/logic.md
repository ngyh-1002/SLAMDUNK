## 🤖 1. ROS 2 네비게이션 문제 및 해결 요약


| 구분 | 이전 코드 (실패 원인: Nav2 충돌) | 현재 코드 (성공 원인: 토픽 기반 상태 관리) |
| :--- | :--- | :--- |
| **문제점** | `BasicNavigator`를 사용하면서 로봇 이동 후 **QR 탐색 및 연속 회전 액션(`goToPose`)**을 **동기적인 대기 루프** 안에 쑤셔 넣어 Nav2 액션 서버의 상태를 불안정하게 만들었습니다. | `Nav2`의 목표 이동은 `RoomNavigator`에서 **완전히 완료**될 때까지 동기적으로 처리합니다. |
| **해결책** | 복잡한 QR 탐색/회전 로직을 `RoomNavigator`에서 완전히 **분리**하여 별도의 노드(`QrDetector`, `RobotRotator`)로 옮겼습니다. |
| **핵심 원리** | 각 노드가 **특정 임무만 완수**하도록 하고, 임무가 끝날 때마다 **토픽을 발행**하여 다음 노드의 작동을 **시작**시키는 방식으로 로봇의 상태를 **명확하게 제어**했습니다. (토픽 구독 → 노드 작동 → 토픽 발행 → 노드 작동 중지) |
| **결론** | Nav2는 하나의 목표를 확실히 끝낼 때까지 다른 목표나 복잡한 대기 로직에 얽히지 않도록 **외부 노드에게 임무를 위임**하는 방식으로 안정성을 확보했습니다. |

---

## 🧭 2. 4개 노드의 임무 순환 알고리즘 (토픽 기반 제어 흐름)

제공하신 네 개의 노드 파일은 토픽 구독과 발행을 통해 **로봇 이동 → QR 검사 → 위치 재설정 → 이동 재개 또는 회전**이라는 복잡한 임무를 순차적으로 실행합니다.

전체 로직은 **"Nav2 이동 루프"**와 **"QR 인식 실패 시 회전 루프"** 두 가지 큰 흐름으로 나뉩니다.

### A. 일반적인 임무 성공 흐름 (Nav2 이동 루프)

| 단계 | 노드 작동 시작 (구독) | 핵심 로직 | 노드 작동 중지 (발행) |
| :--- | :--- | :--- | :--- |
| **1. 목표 이동** | `RoomNavigator`(`/room_command` 구독) | Nav2를 이용해 목표 지점(예: room501)까지 이동 (`navigator.goToPose()`, `while not isTaskComplete()`) | `RoomNavigator` (`/qr_check_command` 발행) |
| **2. QR 검사** | `QrDetector`(`/qr_check_command` 구독) | 기대 QR 코드(예: "501") 설정 후 **10초 타이머 시작**, 카메라 데이터에서 QR 검사 | `QrDetector` (`/amcl_reset_command` 발행) (QR 성공 시) |
| **3. 위치 재설정** | `AmclResetter`(`/amcl_reset_command` 구독) | 수신한 QR 데이터에 해당하는 좌표로 **AMCL 위치 강제 재설정** (`/initialpose` 발행) | **토픽 발행 없음** (AMCL에 명령만 전달) |
| **4. 다음 임무** | **대기** | AMCL 재설정 후, `RoomNavigator`는 다음 `/room_command`를 기다립니다. | |

### B. QR 인식 실패 및 회전 흐름 (최대 8회 반복)

| 단계 | 노드 작동 시작 (구독) | 핵심 로직 | 노드 작동 중지 (발행) |
| :--- | :--- | :--- | :--- |
| **A. QR 검사 실패** | `QrDetector` (10초 타이머 만료) | 10초 동안 QR을 찾지 못함. | `QrDetector` (`/robot_rotate_command` 발행) |
| **B. 로봇 회전** | `RobotRotator` (`/robot_rotate_command` 구독) | **회전 횟수 +1** (최대 8회), 로봇 45도 회전 (`navigator.goToPose()`) | `RobotRotator` (`/qr_check_command` 발행) |
| **C. 재검사** | `QrDetector` (`/qr_check_command` 구독) | **(2) 단계로 돌아가** QR 검사 재시작 (10초 타이머 재설정) | |
| **D. 최대 횟수 초과**| `RobotRotator` (`/robot_rotate_command` 구독) | 회전 횟수가 8회 초과 시 | `RobotRotator` (`/room_command` 발행) |
| **E. 홈 복귀** | `RoomNavigator` (`/room_command` 구독) | **'go_home'** 명령을 받아 홈으로 이동 | `RoomNavigator` (`/qr_check_command` 발행) |

### C. 임무 종료 (Home 도착 후 시작 지점 복귀)

| 단계 | 노드 작동 시작 (구독) | 핵심 로직 | 노드 작동 중지 (발행) |
| :--- | :--- | :--- | :--- |
| **1. Home 도착**| **(A. 2)** 단계에서 QR 검사 | QR 코드가 **"home"**인 것을 인식 | `QrDetector` (`/amcl_reset_command` 발행) |
| **2. 위치 재설정**| `AmclResetter` (`/amcl_reset_command` 구독) | Home 좌표로 AMCL 재설정 **+ 'home' QR 일 때만** 다음 명령 발행 | `AmclResetter` (`/room_command` 발행) |
| **3. Start 이동** | `RoomNavigator` (`/room_command` 구독) | **'go_start'** 명령을 받아 Start 지점으로 이동 **(QR 검사 명령 미발행)** | **토픽 발행 없음** (최종 종료 대기) |
