# 🎼 Score Capture Pro

![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Release](https://img.shields.io/github/v/release/AveMortis0114/ScoreCapturePro?include_prereleases&color=orange)

**화면 악보 자동 캡처 및 PDF 변환 도구**

**Score Capture Pro**는 유튜브 연주 영상이나 전자 악보 뷰어에서 **악보를 자동으로 캡처하고 깔끔한 PDF로 변환**해주는 프로그램입니다.  
단순한 화면 캡처를 넘어 **페이지 넘김 감지**, **스크롤 악보 이어붙이기**, **AI 화질 개선** 등 다양한 자동화 기능을 통해 연주자들에게 최적화된 악보 생성 경험을 제공합니다.

---

## ✨ 주요 기능

### 📺 두 가지 캡처 모드 지원
* **페이지 넘김 모드 (Page Turn):** 화면의 변화를 감지하여 악보가 넘어갈 때만 자동으로 캡처합니다.  
* **스크롤 모드 (Scroll Stitching):** 좌우로 흐르는 악보 영상을 자동으로 인식하고 이어 붙여 하나의 긴 파노라마 이미지로 생성합니다.

### 🧠 이미지 화질 개선 (AI Upscaling)
* **OpenCV DNN 기반 업스케일링:**  
  EDSR 및 LapSRN 모델을 지원하여 저화질 영상 속 악보를 고해상도로 선명하게 보정합니다.

### 🌗 스마트 필터 & 다크모드 반전
* **다크모드 대응:** 검은 배경의 악보를 **흰 배경의 인쇄용 악보**로 자동 반전합니다.  
* **스캔 효과 필터:** "자연스러운 흑백" 필터를 통해 실제 스캔한 듯한 가독성을 제공합니다.

### 📄 PDF 자동 생성 및 관리
* 캡처된 이미지들을 **A4 사이즈 PDF**로 자동 변환합니다.  
* 제목, 아티스트, BPM 정보 및 **원본 영상 링크(QR코드)** 를 악보에 자동 삽입할 수 있습니다.

### 🖱️ 사용자 편의 기능
* **미니 모드:** 영상 시청을 방해하지 않는 컴팩트한 UI 제공  
* **영역 선택 도구:** 멀티 모니터 지원 + 드래그 앤 드롭 캡처 영역 지정 가능

---

## 📸 실행 화면 (Screenshots)

| 메인 화면 |
| :---: |
| <img width="1198" height="727" alt="스크린샷 2026-02-01 오후 3 38 38" src="https://github.com/user-attachments/assets/84cea23c-0253-4148-8a81-24886aeb40d7" />

| PDF 편집 및 미리보기 |
| :---: |
|<img width="1158" height="705" alt="스크린샷 2026-02-01 오후 7 35 50" src="https://github.com/user-attachments/assets/bf11a241-4e85-4c1d-9358-ac5bf384f795" />


| 미니 모드 |
| :---: |
| <img width="319" height="488" alt="스크린샷 2026-02-01 오후 3 38 53" src="https://github.com/user-attachments/assets/1549a8ea-9768-4130-9d4b-c975b8137872" />

---

## 📥 다운로드 및 실행 (일반 사용자)

개발 환경 설정 없이 프로그램을 바로 사용하고 싶다면 **Releases** 페이지에서 실행 파일을 다운로드하세요.

1. 우측의 **Releases** 섹션 또는 [여기](https://github.com/AveMortis0114/ScoreCapturePro/releases)를 클릭  
2. 최신 버전의 `ScoreCapturePro.zip` 또는 `.exe` 다운로드  
3. 압축 해제 후 `ScoreCapturePro.exe` 실행

---

## 🛠 설치 및 실행 (개발자용)

소스 코드를 직접 실행하거나 수정하고 싶은 경우 아래 절차를 따르세요.

### 1. 사전 요구 사항 (Prerequisites)
* Python **3.10 이상**
* (선택) `models/` 폴더에 `EDSR_x4.pb` 등 업스케일링 모델 추가 시 고화질 변환 기능 활성화

---

### 2. 저장소 클론 (Clone)

```bash
git clone https://github.com/AveMortis0114/ScoreCapturePro.git
cd ScoreCapturePro
```

---

### 3. 가상환경 생성 및 활성화 (Virtual Environment)

**Windows (CMD / PowerShell)**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 4. 패키지 설치

```bash
pip install -r requirements.txt
```

requirements.txt가 없다면 아래 패키지를 직접 설치:

```bash
pip install PySide6 numpy opencv-python pillow imagehash qrcode
```

---

### 5. 프로젝트 구조

```
ScoreCapturePro/
├── main.py             # 메인 실행 파일
├── assets/             # UI 리소스 (icon.png 등)
├── fonts/              # 폰트 파일
│   ├── NotoSansKR-Bold.ttf
│   └── NotoSansKR-Regular.ttf
├── models/             # AI 업스케일링 모델 파일
└── version.json        # 버전 정보
```

---

### 6. 실행

```bash
python main.py
```

---

## 📖 사용 가이드

### ▶️ 영역 선택
1. **영역 선택** 버튼 클릭  
2. 캡처할 악보 영역을 드래그하여 지정

### ▶️ 모드 설정
- 일반 영상 → **페이지 넘김 모드(기본)**  
- 스크롤 악보 영상 → **가로 스크롤 모드**

### ▶️ 캡처 시작
1. **캡처 시작** 클릭  
2. 설정된 딜레이(기본 3초) 후 자동 감지 시작  
3. 영상 재생 시 프로그램이 페이지/스크롤 변화를 감지하여 자동 캡처

### ▶️ 편집 및 저장
1. **편집 및 저장** 버튼 클릭  
2. PDF 옵션(여백, 반전, 필터, 메타데이터 등) 확인  
3. PDF로 저장

---

## ⚙️ 설정 옵션

| 옵션 | 설명 |
|------|------|
| **민감도 (Sensitivity)** | 기본값 0.9 — 높을수록 작은 변화는 무시하고 큰 변화만 감지 |
| **딜레이 (Delay)** | 캡처 시작 전 대기 시간 |
| **투명도 (Opacity)** | 캡처 중 UI가 영상을 가리지 않도록 투명도 조절 |

---

## 🤝 기여하기 (Contributing)

* 버그 제보 및 기능 요청은 **Issues** 탭에 등록  
* Pull Request 환영합니다!

---

## ⚠️ 면책 조항 (Disclaimer)

본 프로그램은 개인적인 연습 및 학습 목적의 보조 도구입니다.  
캡처되는 모든 콘텐츠의 저작권은 원저작자에게 있으며,  
본 도구를 통해 생성된 파일의 사용으로 발생하는 모든 법적 책임은 사용자 본인에게 있습니다.  
개발자는 본 프로그램 사용으로 인한 어떠한 책임도 지지 않습니다.

---

## 📝 라이선스

이 프로젝트는 **MIT License**를 따릅니다.  
자세한 내용은 `LICENSE` 파일을 참고하세요.
