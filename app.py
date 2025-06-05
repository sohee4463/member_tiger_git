import os
import json
import re
import pandas as pd
import gspread
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from datetime import datetime




# 환경 변수 로드
load_dotenv()
app = Flask(__name__)




# 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# 주문 시트 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호",
    "제품명", "가격", "PV", "결재방법",
    "주문자_고객명", "주문자_휴대폰번호", "배송처", "수령확인"
]


def parse_request(text):
    result = {"회원명": None, "수정목록": []}

    # 회원명 추출 (예: "홍길동 회원의" 또는 문장 맨 앞)
    name_match = re.search(r"^([가-힣]{2,3})", text)
    if not name_match:
        name_match = re.search(r"([가-힣]{2,3})\s*회원[의은는이가]?", text)
    if name_match:
        result["회원명"] = name_match.group(1)

    # 전체 필드
    필드패턴 = r"(회원명|휴대폰번호|회원번호|비밀번호|가입일자|생년월일|통신사|친밀도|근무처|계보도|소개한분|주소|메모|코드|카드사|카드주인|카드번호|유효기간|비번|카드생년월일|분류|회원단계|연령/성별|직업|가족관계|니즈|애용제품|콘텐츠|습관챌린지|비즈니스시스템|GLC프로젝트|리더님)"
    수정_패턴 = re.findall(rf"{필드패턴}\s*(?:은|는|을|를)?\s*([\w가-힣\d\-\.:/@]+)", text)

    for 필드, 값 in 수정_패턴:
        result["수정목록"].append({"필드": 필드, "값": 값})

    return result




# ✅ 공통 Google Sheets 연결 함수
def get_worksheet(sheet_name: str):
    keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
    keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    return client.open("members_list_main").worksheet(sheet_name)



@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."






# ✅ Google Sheets 연결 함수
def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")
 
def get_ss_sheet():
    return get_worksheet("후원수당")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_ltscounseling_sheet():
    return get_worksheet("이태수메모")








# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        if not name:
            return jsonify({"error": "회원명을 입력해주세요."}), 400

        sheet = get_member_sheet()
        df = pd.DataFrame(sheet.get_all_values()[1:], columns=sheet.row_values(1))

        # 회원명 기준 필터링
        result = df[df["회원명"] == name]
        if result.empty:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

        # 첫 번째 회원 정보를 딕셔너리로 반환
        return jsonify(result.iloc[0].to_dict()), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500









# ✅ 회원 수정
# ✅ 자연어 파싱 함수
def parse_request(text):
    result = {
        "회원명": None,
        "수정목록": []
    }

    # 회원명 추출: 앞부분 또는 "홍길동 회원의"
    name_match = re.search(r'^([가-힣]{2,3})', text)
    if not name_match:
        name_match = re.search(r'([가-힣]{2,3})\s*회원[의은는가이]', text)
    if name_match:
        result["회원명"] = name_match.group(1)

    # 문장 분리
    문장들 = re.split(r'[.。\n]|그리고|,|그리고 나서|또는', text)

    # 필드 + 값 추출
    for 문장 in 문장들:
        m = re.search(r'(휴대폰번호|계보도|주소|직급|친밀도)\s*(?:를|은|는)?\s*([\d가-힣A-Za-z\- ]{2,})\s*(?:으로|로)?\s*(?:수정|변경|바꿔|고쳐)', 문장)
        if m:
            필드 = m.group(1).strip()
            값 = m.group(2).strip()
            # ✅ 값 후처리: '으로', '로' 제거
            값 = re.sub(r'(으로|로)$', '', 값)            
            result["수정목록"].append({"필드": 필드, "값": 값})
    return result







# ✅ 자연어 기반 회원 수정 API
@app.route("/nlp_update", methods=["POST"])
def nlp_update():
    try:
        raw_data = request.data.decode("utf-8")
        data = json.loads(raw_data)
        요청문 = data.get("요청문", "").strip()

        if not 요청문:
            return jsonify({"error": "요청문이 비어 있습니다."}), 400

        parsed = parse_request(요청문)
        name = parsed["회원명"]
        수정목록 = parsed["수정목록"]

        if not name or not 수정목록:
            return jsonify({"error": "회원명 또는 수정 필드를 인식할 수 없습니다."}), 400

        # 시트 열기
        sheet = get_sheet()
        db = sheet.get_all_records()

        # 회원명 존재 확인
        matching_rows = [i for i, row in enumerate(db) if row.get("회원명") == name]
        if len(matching_rows) == 0:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404
        if len(matching_rows) > 1:
            return jsonify({"error": f"'{name}' 회원이 중복됩니다. 고유한 이름만 지원합니다."}), 400

        row_index = matching_rows[0] + 2  # 헤더 포함으로 +2

        # 헤더 정규화
        raw_headers = sheet.row_values(1)
        headers = [h.strip().lower() for h in raw_headers]

        # 필드 수정
        for 항목 in 수정목록:
            필드, 값 = 항목["필드"], 항목["값"]
            필드정규화 = 필드.strip().lower()
            if 필드정규화 not in headers:
                return jsonify({"error": f"'{필드}' 필드는 시트에 존재하지 않습니다. 수정할 수 없습니다."}), 400
            col_index = headers.index(필드정규화) + 1
            sheet.update_cell(row_index, col_index, 값)

        return jsonify({"status": "success", "회원명": name, "수정": 수정목록}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500







# ✅ 주문일자 처리
def process_order_date(raw_date: str) -> str:
    if not raw_date or raw_date.strip() == "":
        return "=TODAY()"
    raw_date = raw_date.strip()
    if "오늘" in raw_date:
        return "=TODAY()"
    elif "어제" in raw_date:
        return "=TODAY()-1"
    elif "내일" in raw_date:
        return "=TODAY()+1"
    try:
        datetime.strptime(raw_date, "%Y-%m-%d")
        return raw_date
    except ValueError:
        return "=TODAY()"

# ✅ OCR 필드 매핑 처리
def normalize_order_fields(data: dict) -> dict:
    result = data.copy()

    # 주문완료란 / 주문상품란 → 제품정보 매핑
    for prefix in ["주문완료", "주문상품"]:
        if f"{prefix}_제품명" in data:
            result["제품명"] = data.get(f"{prefix}_제품명", "")
            result["제품가격"] = data.get(f"{prefix}_가격", "")
            result["PV"] = data.get(f"{prefix}_PV", "")

    # 배송지란 → 주문자 정보 매핑
    if "배송지_이름" in data:
        result["주문자_고객명"] = data.get("배송지_이름", "")
        result["주문자_휴대폰번호"] = data.get("배송지_휴대폰번호", "")
        result["배송처"] = data.get("배송지_주소", "")

    return result

# ✅ 시트에 주문 삽입
def insert_order_row(order_data):
    sheet = get_product_order_sheet()
    headers = sheet.row_values(1)
    order_data["주문일자"] = process_order_date(order_data.get("주문일자", ""))
    row = [order_data.get(h, "") for h in headers]
    sheet.insert_row(row, index=2)

# ✅ 완전 수동형 JSON 주문 저장
@app.route("/save_order", methods=["POST"])
def save_order():
    try:
        raw_data = request.get_json()
        if not raw_data:
            return jsonify({"error": "주문 데이터를 입력해 주세요."}), 400

        order_data = normalize_order_fields(raw_data)
        insert_order_row(order_data)

        return jsonify({"status": "success", "message": "주문이 저장되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ DB 기반 자동 회원 정보 포함 주문 등록
@app.route("/add_order", methods=["POST"])
def add_order():
    try:
        data = request.get_json()
        member_name = data.get("회원명", "").strip()
        if not member_name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_sheet()
        records = sheet.get_all_records()
        member_info = next((r for r in records if r.get("회원명") == member_name), None)
        if not member_info:
            return jsonify({"error": f"'{member_name}' 회원을 DB에서 찾을 수 없습니다."}), 404

        order_sheet = get_product_order_sheet()

        if not order_sheet.get_all_values():
            ORDER_HEADERS = [
                "주문일자", "회원명", "회원번호", "휴대폰번호", "제품명", "제품가격", "PV",
                "결재방법", "주문자_고객명", "주문자_휴대폰번호", "배송처", "수령확인"
            ]
            order_sheet.append_row(ORDER_HEADERS)

        order_date = process_order_date(data.get("주문일자", ""))

        row = [
            order_date,
            member_name,
            member_info.get("회원번호", ""),
            member_info.get("휴대폰번호", ""),
            data.get("제품명", ""),
            float(data.get("제품가격", 0)),
            float(data.get("PV", 0)),
            data.get("결재방법", ""),
            data.get("주문자_고객명", ""),
            data.get("주문자_휴대폰번호", ""),
            data.get("배송처", ""),
            data.get("수령확인", "")
        ]

        order_sheet.insert_row(row, index=2)

        return jsonify({"status": "success", "message": "회원 기반 주문이 저장되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500















# ✅ 주문 삭제 요청 - 최근 5건 중 보여주기
def extract_recent_orders(sheet, count=5):
    all_values = sheet.get_all_values()
    if not all_values or len(all_values) < 2:
        return None, None, []
    headers, rows = all_values[0], all_values[1:]
    row_count = min(count, len(rows))
    recent_orders = [(i + 2, row) for i, row in enumerate(rows[:row_count])]
    return headers, rows, recent_orders

@app.route("/delete_order_request", methods=["POST"])
def delete_order_request():
    try:
        sheet = get_product_order_sheet()
        headers, rows, recent_orders = extract_recent_orders(sheet)

        if not recent_orders:
            return jsonify({"message": "등록된 주문이 없습니다."}), 404

        response = []
        for idx, (row_num, row_data) in enumerate(recent_orders, start=1):
            내용 = {
                "번호": idx,
                "행번호": row_num,
                "회원명": row_data[headers.index("회원명")],
                "제품명": row_data[headers.index("제품명")],
                "가격": row_data[headers.index("제품가격")],
                "PV": row_data[headers.index("PV")],
                "주문일자": row_data[headers.index("주문일자")]
            }
            response.append(내용)

        return jsonify({
            "message": f"\ud83d\udccc 최근 주문 내역 {len(response)}건입니다. 삭제할 번호(1~{len(response)})를 선택해 주세요.",
            "주문목록": response
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ 주문 삭제 확정
@app.route("/delete_order_confirm", methods=["POST"])
def delete_order_confirm():
    try:
        data = request.get_json()
        번호들 = data.get("삭제번호", "").strip()

        if 번호들 in ["없음", "취소", ""]:
            return jsonify({"message": "삭제 요청이 취소되었습니다."}), 200

        번호_리스트 = sorted(set(map(int, re.findall(r'\d+', 번호들))))

        sheet = get_product_order_sheet()
        headers, rows, recent_orders = extract_recent_orders(sheet)

        if not recent_orders:
            return jsonify({"message": "삭제할 주문이 없습니다."}), 404

        row_count = len(recent_orders)
        if any(n < 1 or n > row_count for n in 번호_리스트):
            return jsonify({"error": f"삭제할 주문 번호는 1 ~ {row_count} 사이로 입력해 주세요."}), 400

        recent_rows = [r[0] for r in recent_orders]  # 실제 행번호
        삭제행목록 = [recent_rows[n - 1] for n in 번호_리스트 if n <= row_count]
        삭제행목록.sort(reverse=True)

        for row_num in 삭제행목록:
            sheet.delete_rows(row_num)

        return jsonify({
            "message": f"{', '.join(map(str, 번호_리스트))}번 주문이 삭제되었습니다.",
            "삭제행번호": 삭제행목록
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500









# ✅ 후원수당 정리
@app.route("/trigger_bonus_by_sheet", methods=["POST"])
def trigger_bonus_by_sheet():
    try:
        data = request.get_json()
        command = data.get("명령", "").strip()
        sheet_url = data.get("링크", "").strip()
        member_name = data.get("회원명", "").strip() or "미입력"

        if "후원수당" not in command or not sheet_url:
            return jsonify({"error": "후원수당 명령어가 없거나 링크가 없습니다."}), 400

        keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
        keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
        client = gspread.authorize(creds)

        ss = client.open_by_url(sheet_url)
        sheet = ss.sheet1
        values = sheet.get_all_values()

        try:
            start_idx = next(i for i, row in enumerate(values) if "기준일자" in row)
        except StopIteration:
            return jsonify({"error": "'기준일자' 항목이 포함된 행이 없습니다."}), 400

        headers = values[start_idx]
        data_rows = values[start_idx + 1:]
        df = pd.DataFrame(data_rows, columns=headers)

        df["기준일자"] = pd.to_datetime(df["기준일자"], errors="coerce")
        df["취득점수"] = pd.to_numeric(df["취득점수"], errors="coerce")
        df = df[df["취득점수"] > 0].dropna(subset=["기준일자"])
        df.drop_duplicates(subset=["기준일자"], inplace=True)
        df["횟수"] = (df["취득점수"] // 15).astype(int)

        df["반기"] = df["기준일자"].apply(lambda d: f"{d.year}년 {d.month}월 {'전반기' if d.day <= 15 else '후반기'}")
        합계 = df.groupby("반기")["횟수"].sum().to_dict()
        마지막 = df.groupby("반기")["기준일자"].transform("max") == df["기준일자"]
        df["달성횟수"] = ""
        df.loc[마지막, "달성횟수"] = df.loc[마지막, "반기"].map(lambda k: f"{k} {합계[k]}회")
        df["회원명"] = member_name
        df.drop(columns=["반기"], inplace=True)

        df_final = df[["기준일자", "합계_좌", "합계_우", "취득점수", "관리자직급", "횟수", "달성횟수", "회원명"]]

        try:
            result_sheet = ss.worksheet("후원수당_정리")
        except gspread.exceptions.WorksheetNotFound:
            result_sheet = ss.add_worksheet(title="후원수당_정리", rows="1000", cols="20")

        result_sheet.clear()
        result_sheet.update([df_final.columns.tolist()] + df_final.values.tolist())

        return jsonify({"message": "후원수당 정리 결과가 시트에 저장되었습니다."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




















# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

