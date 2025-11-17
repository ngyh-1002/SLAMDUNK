## 📝 README: 로봇 내비게이션 및 QR 코드 연동 시스템 (Nav2 & QR)

---

## 1. 🚨 발생 오류 및 근본 원인 분석

| 오류 메시지 | 원인 및 진단 | 해결 방안 |
| :--- | :--- | :--- |
| `❌ 로봇의 현재 위치(/amcl_pose)를 수신할 수 없습니다. QR 확인을 건너뜁니다.` | 로봇이 목표 지점에 도착한 직후, **`RoomNavigator`** 노드의 `verify_and_realign_with_qr` 함수가 **비동기적으로 업데이트되는** 로봇 위치 정보 (`self.current_pose`)를 확인했을 때, **아직 `/amcl_pose` 토픽 메시지를 받지 못한** `None` 상태였기 때문에 발생. | `verify_and_realign_with_qr` 함수 시작 부분에 **`self.current_pose`가 유효할 때까지 최대 5초 동안 강제 대기**하는 로직 추가. |
| `[ERROR] [1761889325.779963724] [room_navigator]: ❌ 로봇의 현재 위치(/amcl_pose)를 수신할 수 없습니다. QR 확인을 건너뜁니다.` | `RoomNavigator` 노드가 초기화된 직후, 로봇의 위치 추정(Localization)을 담당하는 **AMCL 노드**가 활성화되거나 첫 `/amcl_pose` 메시지를 발행하기 전에 `RoomNavigator`가 먼저 실행되어 `/amcl_pose` 구독이 불완전했음. | `RoomNavigator` 초기화 시 **`setInitialPose` 호출 직후 1.0초 대기**를 추가하여 AMCL이 안정화될 시간을 확보. |

---

## 2. 🛠️ 코드 수정 사항 (Changelog)

### A. `RoomNavigator` (`nav2_commander.py`)

| 함수 | 수정 내용 | 효과 |
| :--- | :--- | :--- |
| `__init__` | `self.navigator.waitUntilNav2Active()` 호출 직후 **`time.sleep(1.0)`** 추가. | 노드 시작 시 AMCL의 초기 위치 추정 안정화 시간을 확보하여, `/amcl_pose` 수신 실패 가능성 감소. |
| `verify_and_realign_with_qr` | 함수 시작 시 **`while self.current_pose is None:` 루프**를 추가하고, 최대 5.0초의 타임아웃을 설정. | 로봇이 목표 지점에 도착한 직후에도 `/amcl_pose` 콜백이 수신될 때까지 강제로 대기. 이로써 `self.current_pose`가 `None`인 상태에서 QR 확인 로직이 실행되는 것을 원천적으로 차단. |

### B. `QrDetector` (`qr_detector_node.py`)

* **수정 사항 없음:** `QrDetector` 노드는 자체적인 문제가 없으며, `RoomNavigator`의 명령에 따라 위치 재설정 (`/initialpose` 발행) 및 응답 (`/qr_check_response` 발행) 역할을 충실히 수행하도록 설계됨.

---

## 3. 🗺️ 토픽 구독 및 발행 관계 (Topic Communication Flow)

이 시스템은 총 5개의 핵심 토픽을 사용하여 `RoomNavigator`, `QrDetector`, 그리고 Nav2 스택의 핵심 요소인 **AMCL** 간에 데이터를 주고받습니다. 

| 토픽명 | 발행 노드 (Publisher) | 구독 노드 (Subscriber) | 데이터 타입 | 용도 |
| :--- | :--- | :--- | :--- | :--- |
| **`/amcl_pose`** | **AMCL** (Nav2) | **`RoomNavigator`** | `PoseWithCovarianceStamped` | 로봇의 **현재 위치 및 자세** 정보를 지속적으로 제공. QR 확인 시 로봇의 초기 방향을 계산하는 데 사용됨. |
| **`/initialpose`** | **`RoomNavigator`** (초기화 시), **`QrDetector`** (QR 감지 성공 시) | **AMCL** (Nav2) | `PoseWithCovarianceStamped` | 로봇의 **초기 위치를 설정**하거나, QR 코드를 통해 **위치를 재설정(Relocalization)**할 때 사용됨. |
| **`/room_command`** | 외부 (사용자 또는 상위 제어) | **`RoomNavigator`** | `String` | 로봇에게 `"go_room501"`, `"go_home"` 등 **목표 이동 명령**을 전달. |
| **`/qr_check_command`** | **`RoomNavigator`** | **`QrDetector`** | `String` | 로봇이 목표에 도착했을 때, **QR 코드 확인을 시작하라는 명령**을 `QrDetector`에 전달. |
| **`/qr_check_response`** | **`QrDetector`** | **`RoomNavigator`** | `String` | QR 코드 감지 **성공/실패 여부** (`qr_check_success`, `qr_check_failure`)를 `RoomNavigator`에게 응답. |
