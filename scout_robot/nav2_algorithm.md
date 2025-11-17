## 🗺️ Nav2 경로 계획 알고리즘 분석 보고서 

Nav2 패키지의 Global Planner와 Local Planner가 사용하는 핵심 알고리즘을 파악하기 위해 수행했던 탐색 과정 및 그 결과를 상세하게 정리했습니다.

-----

### 1\. 📌 목표 및 탐색 과정 요약

이 문서는 `sudo apt install`로 설치된 Nav2 패키지가 사용하는 **전역 경로 계획 (Global Planning)** 및 **지역 경로 제어 (Local Planning)** 알고리즘을 파악하는 과정을 요약합니다.

| 단계 | 수행 내용 | 결과/결론 |
| :--- | :--- | :--- |
| **1단계** | 설치된 Nav2 패키지(.yaml 파일) 분석 | Global Planner: **NavfnPlanner**, Local Planner: **DWBLocalPlanner** 사용 확인. |
| **2단계** | 설치 디렉토리 탐색 (`share/nav2_*`) | 소스 코드가 아닌 CMake 설정 및 환경 파일만 존재. 알고리즘 코드는 **바이너리 형태**로 컴파일되어 설치됨. |
| **3단계** | 공식 소스 코드 저장소 확인 | 모든 Nav2 패키지의 소스는 **`ros-navigation/navigation2`** GitHub 저장소에 있음을 확인. |
| **4단계** | 핵심 알고리즘 코드 분석 | 각 플래너의 세부 알고리즘 및 구현 구조 파악. |

-----

### 2\. 🤖 Nav2 경로 계획 알고리즘 상세 분석 결과

분석을 통해 확인된 Nav2의 Global Planner 및 Local Planner의 알고리즘과 그 코드가 정의된 위치는 다음과 같습니다.

### 2.1. Global Planner (전역 경로 계획)

| 항목 | 상세 내용 |
| :--- | :--- |
| **알고리즘 클래스** | `nav2_navfn_planner/NavfnPlanner` |
| **사용 알고리즘** | **Dijkstra** (다익스트라) 또는 **A\* (A-Star)** |
| **결정 로직** | 파라미터 `use_astar` 값에 따라 동적으로 선택됨. (YAML 파일에서 `false`로 설정 시 **Dijkstra** 사용) |
| **핵심 코드 파일** | `navigation2/nav2_planners/nav2_navfn_planner/src/navfn_planner.cpp` |
| **주요 로직** | `NavfnPlanner::makePlan` 함수 내의 조건문 (`if (use_astar_)`...)에서 **`planner_->calcNavFnAstar()`** 또는 **`planner_->calcNavFnDijkstra()`** 호출. |

<br>

### 2.2. Local Planner (지역 경로 제어)

| 항목 | 상세 내용 |
| :--- | :--- |
| **알고리즘 클래스** | `dwb_core::DWBLocalPlanner` |
| **사용 알고리즘** | **DWB (Dynamic Window Approach)** 기반 |
| **구현 방식** | **Generate-Simulate-Evaluate** 루프를 플러그인 기반으로 모듈화. |
| **핵심 제어 파일** | `navigation2/nav2_dwb_controller/dwb_core/src/dwb_local_planner.cpp` |
| **주요 로직** | `DWBLocalPlanner::coreScoringAlgorithm` 함수가 DWA의 핵심 루프를 실행: |
| **궤적 생성** | **`TrajectoryGenerator`** 플러그인 (예: `StandardTrajectoryGenerator`)을 호출하여 **Dynamic Window** 내에서 속도 샘플링 및 예측 궤적 생성. |
| **궤적 평가** | **`TrajectoryCritic`** 플러그인 (예: `BaseObstacle`, `PathAlign` 등)들을 호출하여 각 궤적에 비용을 할당하고, **가장 낮은 비용**의 궤적을 최적 명령으로 선택. |

-----

### 3\. 🌐 공식 GitHub 저장소 출처 확인

Nav2 소스 코드가 \*\*`https://github.com/ros-navigation/navigation2`\*\*임을 확인한 근거는 다음과 같은 **공식 문서**에서 찾을 수 있습니다.

  * **Nav2 공식 문서 (`docs.nav2.org`):**
      * **Build Instructions** 섹션에서 사용자가 소스 코드를 복제(Clone)할 때 해당 GitHub URL을 사용하도록 명시적으로 지시하고 있습니다.
  * **ROS 2 배포 시스템:**
      * `apt` 패키지 생성에 사용되는 ROS Build Farm의 기록에서도 Nav2 패키지들의 \*\*Upstream Repository (원본 저장소)\*\*가 해당 GitHub URL로 지정되어 있습니다.

이 모든 근거는 `ros-navigation/navigation2`가 Nav2 프로젝트의 유일하고 공식적인 소스 코드 저장소임을 확증합니다.
