# 사물 분석 앱

이미지를 여러 장 올린 뒤 크기·색상·흑백·모자이크·텍스트를 조정하고, 같은 설정을 모든 이미지에 일괄 적용해 저장하는 PyQt5 데스크톱 앱입니다.

저장소: [https://github.com/sngbae12/object-analyzer](https://github.com/sngbae12/object-analyzer)

현재 코드에는 YOLO 같은 사물 인식 모델이나 외부 AI API가 없습니다. 처리 기준은 사용자가 화면에서 지정한 편집 값입니다.

## 구현된 기능

- 다중 이미지 업로드 (jpg, jpeg, png, bmp, gif, webp, tif, tiff)
- 한 장의 편집 내용을 나머지 이미지에 같은 기준으로 일괄 적용
- RGB 슬라이더로 빨강/초록/파랑을 실시간 조절 (0~200%, 기본 100%)
- 가로 픽셀 입력 시 세로는 각 이미지 비율로 자동 계산
- 흑백 변환
- 마우스 드래그로 선택한 영역 모자이크
- 클릭한 위치에 텍스트 삽입 (문구, 크기, 색상)
- 결과를 jpg / png / gif / bmp로 폴더에 일괄 저장 (`원본이름_edited`)

화면은 왼쪽 약 80%에 미리보기, 오른쪽 약 20%에 메뉴가 있습니다.

## 실행 환경

| 항목 | 내용 |
| --- | --- |
| OS | Windows 10/11 권장 |
| Python | 3.11 이상 |
| GPU | **필요 없음** |
| 인터넷 | **처음 패키지를 설치할 때만 필요**. 설치 후에는 오프라인으로 실행 가능 |
| 로컬 모델 | **없음** (다운로드할 모델 파일 없음) |
| 외부 API / API 키 | **없음** (키 입력란을 넣지 않음) |

## 내려받기

PowerShell 또는 명령 프롬프트:

```powershell
git clone https://github.com/sngbae12/object-analyzer.git
cd object-analyzer
```

Git이 없으면 GitHub 저장소 페이지에서 `Code` → `Download ZIP`으로 받은 뒤 압축을 풀고 해당 폴더로 이동합니다.

## 실행 환경 준비

1. [Python 3.11+](https://www.python.org/downloads/) 설치
2. 설치 화면에서 **Add python.exe to PATH** 를 선택
3. 터미널을 다시 연 뒤 `python --version` 으로 설치 확인

## 라이브러리 설치

프로젝트 폴더에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt`에 포함된 패키지:

- `PyQt5==5.15.11`
- `Pillow>=10.0.0`

## 모델 또는 API 준비

추가 준비가 없습니다.

- 로컬 가중치 파일, `models/` 폴더, Hugging Face 다운로드가 필요하지 않습니다.
- OpenAI 등 외부 API 키도 사용하지 않습니다. 키를 파일·로그·Git에 넣을 일도 없습니다.

텍스트를 넣을 때는 Windows 기본 글꼴(`malgun.ttf` 등)을 사용합니다. 해당 글꼴이 없으면 Pillow 기본 글꼴로 대체됩니다.

## 실행 명령어

Windows에서 가장 간단한 방법:

```text
start.bat
```

`start.bat`은 `.venv`가 있으면 그 가상환경의 Python으로 실행하고, 없으면 `.venv`를 만든 뒤 `requirements.txt`를 설치합니다.

직접 실행:

```powershell
.\.venv\Scripts\python.exe main.py
```

PowerShell에서 `main.py`만 입력하면 실행되지 않습니다. 반드시 `python main.py` 또는 `start.bat`을 사용하세요.

## 사용 방법

1. **다중 이미지 업로드**로 사진을 선택합니다. 왼쪽 아래 썸네일로 미리보기 대상을 바꿀 수 있습니다.
2. 오른쪽에서 RGB, 가로 픽셀, 흑백, 모자이크, 텍스트를 조정합니다.
3. 모자이크는 버튼을 누른 뒤 이미지 위를 드래그합니다. 텍스트는 버튼을 누른 뒤 위치를 클릭합니다.
4. **결과 파일 저장**에서 폴더와 형식(jpg/png/gif/bmp)을 고릅니다.
5. 한 장에 적용한 설정(색상, 가로 크기, 흑백, 모자이크 상대 위치, 텍스트)이 저장 시 모든 이미지에 반영됩니다.

## 프로젝트 구조

```text
object-analyzer/
  main.py            앱 진입점
  main_window.py     화면과 편집 메뉴
  canvas.py          이미지 표시, 모자이크 드래그, 텍스트 클릭
  image_ops.py       RGB/크기/흑백/모자이크/텍스트/저장 처리
  requirements.txt   의존성
  start.bat          Windows 실행
  실행.bat           start.bat 호출
  README.md
```

경로와 Qt 플러그인은 현재 실행 중인 Python(보통 `.venv`)을 기준으로 찾습니다. 특정 PC의 `C:\Users\...` 절대경로는 사용하지 않습니다.

## 안면인식 프로젝트와의 관계

이 저장소는 안면인식 프로젝트와 별도로 관리합니다. 기존 저장소를 덮어쓰지 마세요.
