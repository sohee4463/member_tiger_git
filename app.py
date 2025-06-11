import os
import json
import re
import pandas as pd
import gspread
import pytz
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from datetime import datetime
from collections import Counter




# ✅ 환경 변수 로드
load_dotenv()
app = Flask(__name__)
if not os.getenv("GOOGLE_SHEET_KEY"):
    raise EnvironmentError("환경변수 GOOGLE_SHEET_KEY가 설정되지 않았습니다.")




# 자연어 명령 키워드 매핑
UPDATE_KEYS = {
    "회원": ["회원수정", "회원내용수정", "회원내용을 수정", "회원변경", "회원내용변경", "회원내용을 고쳐", "수정", "변경", "고쳐"],
    "주문": ["주문수정", "주문내용수정", "주문내용을 수정", "주문변경", "주문내용변경", "주문내용을 고쳐"],
    "후원수당": ["후원수당수정", "후원수당내용수정", "후원수당내용을 수정", "후원수당변경", "후원수당내용변경", "후원수당내용을 고쳐"]
}

# ✅ 주문 항목 헤더
ORDER_HEADERS = [
    "주문일자", "회원명", "회원번호", "휴대폰번호", "제품명",
    "제품가격", "PV", "결재방법", "주문자_고객명", "주문자_휴대폰번호",
    "배송처", "수령확인"
]




def parse_request(text):
    result = {"회원명": "", "수정목록": []}

    # 회원명 추출
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





@app.route("/")
def home():
    return "Flask 서버가 실행 중입니다."


def get_db_sheet():
    return get_worksheet("DB")

def get_member_sheet():
    return get_worksheet("DB")

def get_product_order_sheet():
    return get_worksheet("제품주문")

def get_ss_sheet():
    return get_worksheet("후원수당")

def get_counseling_sheet():
    return get_worksheet("상담일지")

def get_mymemo_sheet():
    return get_worksheet("개인메모")

def get_search_memo_by_tags_sheet():
    return get_worksheet("개인메모")

def get_dailyrecord_sheet():
    return get_worksheet("활동일지")

def get_image_sheet():
    return get_worksheet("사진저장")







# ✅ Google Sheets 연동 함수
def get_worksheet(sheet_name):
    try:
        keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
        keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
        client = gspread.authorize(creds)

      
        sheet_name_env = os.getenv("GOOGLE_SHEET_DOC_NAME")
        sheet = client.open(sheet_name_env)


        return sheet.worksheet(sheet_name)
    except Exception as e:
        print(f"[시트 접근 오류] {e}")
        return None






# ✅ 필드 키워드 → 시트의 실제 컬럼명 매핑
field_map = {
    "휴대폰번호": "휴대폰번호",
    "핸드폰": "휴대폰번호",
    "주소": "주소",
    "이메일": "이메일",
    "이름": "회원명",
    "생일": "생년월일",
    "생년월일": "생년월일",
    "비밀번호": "비밀번호",
    "직업": "근무처",
    "직장": "근무처",
    # 필요한 항목 계속 추가 가능
}










# ✅ 회원 조회
@app.route("/find_member", methods=["POST"])
def find_member():
    try:
        data = request.get_json()
        name = data.get("회원명", "").strip()
        number = data.get("회원번호", "").strip()

        if not name and not number:
            return jsonify({"error": "회원명 또는 회원번호를 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        db = sheet.get_all_values()
        headers, rows = db[0], db[1:]

        for row in rows:
            row_dict = dict(zip(headers, row))
            if name and row_dict.get("회원명") == name:
                return jsonify(row_dict), 200
            if number and row_dict.get("회원번호") == number:
                return jsonify(row_dict), 200

        return jsonify({"error": "해당 회원 정보를 찾을 수 없습니다."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500





















# ✅ 회원 수정
# ✅ 자연어 요청문에서 필드와 값 추출, 회원 dict 수정
# 필드 맵 (추가 가능)
field_map = {
    "휴대폰번호": "휴대폰번호",
    "핸드폰": "휴대폰번호",
    "주소": "주소",
    "이메일": "이메일",
    "이름": "회원명",
    "생일": "생년월일",
    "생년월일": "생년월일",
    "비밀번호": "비밀번호",
    "직업": "근무처",
    "직장": "근무처",
}




def parse_request_and_update(data: str, member: dict) -> tuple:
    수정된필드 = {}

    for keyword in sorted(field_map.keys(), key=lambda k: -len(k)):  # 긴 키워드 우선
        pattern = rf"{keyword}(?:를|은|는|이|:|：)?\s*(?P<value>[\d\-@.\w()]+)"
        matches = re.finditer(pattern, data)

        for match in matches:
            value_raw = match.group("value").strip()

            # 후처리: 조사/명령어 제거
            value = re.sub(r"(으로|로|에)?(수정|변경|바꿔줘|바꿔|바꿈)?$", "", value_raw)

            field = field_map[keyword]

            if field not in 수정된필드 and value not in 수정된필드.values():  # ✅ 중복 저장 방지
                수정된필드[field] = value
                member[field] = value
                member[f"{field}_기록"] = f"(기록됨: {value})"

    return member, 수정된필드
















# ✅ 회원 수정 API
@app.route("/update_member", methods=["POST"])
def update_member():
    try:
        raw_data = request.data.decode("utf-8")
        data = json.loads(raw_data)
        요청문 = data.get("요청문", "").strip()

        if not 요청문:
            return jsonify({"error": "요청문이 비어 있습니다."}), 400

        # ✅ 시트 가져오기 및 회원명 리스트 확보
        sheet = get_member_sheet()
        db = sheet.get_all_records()
        raw_headers = sheet.row_values(1)
        headers = [h.strip().lower() for h in raw_headers]

        # ✅ 안전하게 문자열로 변환 후 strip()
        member_names = [str(row.get("회원명", "")).strip() for row in db if row.get("회원명") is not None]


        # ✅ 요청문 내 포함된 실제 회원명 찾기 (길이순 정렬)
        name = None
        for candidate in sorted(member_names, key=lambda x: -len(x)):
            if candidate and candidate in 요청문:
                name = candidate
                break

        if not name:
            return jsonify({"error": "요청문에서 유효한 회원명을 찾을 수 없습니다."}), 400

        # ✅ 해당 회원 찾기
        matching_rows = [i for i, row in enumerate(db) if row.get("회원명") == name]
        if len(matching_rows) == 0:
            return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404
        if len(matching_rows) > 1:
            return jsonify({"error": f"'{name}' 회원이 중복됩니다. 고유한 이름만 지원합니다."}), 400

        row_index = matching_rows[0] + 2  # 헤더 포함으로 +2
        member = db[matching_rows[0]]

        # ✅ 자연어 해석 및 필드 수정
        updated_member, 수정된필드 = parse_request_and_update(요청문, member)

        수정결과 = []
        무시된필드 = []

        for key, value in updated_member.items():
            key_strip = key.strip()
            key_lower = key_strip.lower()

            # _기록 필드는 저장 안 함
            if key_strip.endswith("_기록"):
                continue

            if key_lower in headers:
                col_index = headers.index(key_lower) + 1
                sheet.update_cell(row_index, col_index, value)
                수정결과.append({"필드": key_strip, "값": value})
            else:
                무시된필드.append(key_strip)

        return jsonify({
            "status": "success",
            "회원명": name,
            "수정": 수정결과,
            "무시된_필드": 무시된필드
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


    




# ✅ 회원 저장 (신규 또는 기존 덮어쓰기)
@app.route('/save_member', methods=['POST'])
def save_member():
    try:
        req = request.get_json()
        name = req.get("회원명")
        if not name:
            return jsonify({"error": "회원명은 필수입니다"}), 400

        sheet = get_member_sheet()  # ✅ 수정된 부분
        data = sheet.get_all_records()
        headers = sheet.row_values(1)

        # 기존 회원이 있으면 덮어쓰기
        for i, row in enumerate(data):
            if row.get('회원명') == name:
                for key, value in req.items():
                    if key in headers:
                        sheet.update_cell(i + 2, headers.index(key) + 1, value)
                return jsonify({"message": f"기존 회원 '{name}' 정보 수정 완료"})

        # 신규 회원이면 추가
        new_row = [''] * len(headers)
        for key, value in req.items():
            if key in headers:
                new_row[headers.index(key)] = value
   
        sheet.insert_row(new_row, 2)
        return jsonify({"message": f"신규 회원 '{name}' 저장 완료"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500







# ✅ 회원 삭제 API
@app.route('/delete_member', methods=['POST'])
def delete_member():
    try:
        name = request.get_json().get("회원명")
        if not name:
            return jsonify({"error": "회원명을 입력해야 합니다."}), 400

        sheet = get_member_sheet()
        data = sheet.get_all_records()

        for i, row in enumerate(data):
            if row.get('회원명') == name:
                sheet.delete_rows(i + 2)  # 헤더 포함으로 인덱스 +2
                return jsonify({"message": f"'{name}' 회원 삭제 완료"}), 200

        return jsonify({"error": f"'{name}' 회원을 찾을 수 없습니다."}), 404

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500













# 예시 데이터베이스 (실제 환경에서는 DB 연동)
mock_db = {
    "홍길동": {
        "회원명": "홍길동",
        "회원번호": "12345678",
        "휴대폰번호": "010-1234-5678",
        "주소": "서울시 강남구"
    }
}

# 동의어 포함 field_map
field_map = {
    "회원명": "회원명", "이름": "회원명", "성함": "회원명",
    "회원번호": "회원번호", "번호": "회원번호", "아이디": "회원번호",
    "생년월일": "생년월일", "생일": "생년월일", "출생일": "생년월일",
    "성별": "연령/성별", "연령": "연령/성별", "나이": "연령/성별",
    "휴대폰번호": "휴대폰번호", "전화번호": "휴대폰번호", "연락처": "휴대폰번호", "폰": "휴대폰번호",
    "주소": "주소", "거주지": "주소", "사는곳": "주소",
    "직업": "직업", "일": "직업", "하는일": "직업",
    "가입일자": "가입일자", "입회일": "가입일자", "등록일": "가입일자",
    "가족관계": "가족관계", "가족": "가족관계",
    "추천인": "소개한분", "소개자": "소개한분",
    "계보도": "계보도",
    "후원인": "카드주인", "카드주인": "카드주인", "스폰서": "카드주인",
    "카드사": "카드사", "카드번호": "카드번호", "카드생년월일": "카드생년월일",
    "리더": "리더님", "리더님": "리더님", "멘토": "리더님",
    "비밀번호": "비번", "비번": "비번", "비밀번호힌트": "비밀번호힌트", "힌트": "비밀번호힌트",
    "시스템코드": "코드", "코드": "코드", "시스템": "비즈니스시스템",
    "콘텐츠": "콘텐츠", "통신사": "통신사", "유효기간": "유효기간", "수신동의": "수신동의",
    "메모": "메모", "비고": "메모", "노트": "메모",
    "GLC": "GLC프로젝트", "프로젝트": "GLC프로젝트", "단계": "회원단계",
    "분류": "분류", "니즈": "니즈", "관심": "니즈",
    "애용제품": "애용제품", "제품": "애용제품", "주력제품": "애용제품",
    "친밀도": "친밀도", "관계": "친밀도",
    "근무처": "근무처", "회사": "근무처", "직장": "근무처"
}









# 다중 필드 업데이트 함수
def parse_request_and_update_multi(data: str, member: dict) -> dict:
    for keyword in field_map:
        # 유연한 한글 + 숫자 + 기호 값 처리
        pattern = rf"{keyword}\s*[:：]?\s*([^\s]+)"
        for match in re.finditer(pattern, data):
            value_raw = match.group(1)
            value = re.sub(r"(으로|로|에|를|은|는)$", "", value_raw)
            field = field_map[keyword]
            member[field] = value
            member[f"{field}_기록"] = f"(기록됨: {value})"
    return member



def extract_nouns(text):
    return re.findall(r'[가-힣]{2,}', text)

def generate_tags(text):
    nouns = extract_nouns(text)
    top_keywords = [word for word, _ in Counter(nouns).most_common(5)]
    return top_keywords




API_URL = os.getenv("EXTERNAL_API_URL")

HEADERS = {"Content-Type": "application/json"}

def determine_mode(content: str) -> str:
    if "상담일지" in content:
        return "1"  # 상담일지 (공유)
    elif "개인메모" in content:
        return "개인"
    elif "활동일지" in content:
        return "3"
    else:
        return "1"  # 기본값

@app.route('/save_note', methods=['POST'])
def save_note():
    data = request.json
    요청문 = data.get("요청문", "")
    mode = determine_mode(요청문)

    payload = {
        "요청문": 요청문,
        "mode": mode,
        "allow_unregistered": True
    }

    response = requests.post(API_URL, json=payload, headers=HEADERS)
    if response.ok:
        return jsonify({"status": "success", "message": "저장 완료"})
    else:
        return jsonify({"status": "error", "message": response.text})
        




# ✅ 시트 저장 함수 (Google Sheets 연동 및 중복 확인)
def save_to_sheet(sheet_name, member_name, content):
    try:
        sheet = get_worksheet(sheet_name)
        if sheet is None:
            print(f"[오류] '{sheet_name}' 시트를 찾을 수 없습니다.")
            return False

        existing = sheet.get_all_values()
        contents = [row[2] if len(row) > 2 else "" for row in existing]  # 내용은 3열 기준
        if content in contents:
            print(f"[중복] 이미 같은 내용이 '{sheet_name}'에 존재합니다.")
            return False

        now = datetime.now(pytz.timezone("Asia/Seoul"))
        time_str = now.strftime("%Y-%m-%d %H:%M")

        sheet.insert_row([time_str, member_name, content], index=2)
        print(f"[저장완료] '{sheet_name}' 시트에 저장 완료")
        return True

    except Exception as e:
        print(f"[시트 저장 오류: {sheet_name}] {e}")
        return False


# ✅ /add_counseling 처리 API (자연어 입력 기반 저장 + mode 분기)
@app.route('/add_counseling', methods=['POST'])
def add_counseling():
    try:
        data = request.get_json()
        text = data.get("요청문", "")

        sheet_keywords = ["상담일지", "개인메모", "활동일지", "직접입력"]
        action_keywords = ["저장", "기록", "입력"]

        if not any(kw in text for kw in sheet_keywords) or not any(kw in text for kw in action_keywords):
            return jsonify({"message": "저장하려면 '상담일지', '개인메모', '활동일지', '직접입력' 중 하나와 '저장', '기록', '입력' 같은 동작어를 함께 포함해 주세요."})

        match = re.search(r'([가-힣]{2,3})\s*(상담일지|개인메모|활동일지|직접입력)', text)
        if not match:
            return jsonify({"message": "회원명을 인식할 수 없습니다."})
        member_name = match.group(1)
        matched_sheet = match.group(2)

        for kw in sheet_keywords + action_keywords:
            text = text.replace(f"{member_name}{kw}", "")
            text = text.replace(f"{member_name} {kw}", "")
            text = text.replace(kw, "")
        text = text.strip()

        if matched_sheet not in ["상담일지", "개인메모", "활동일지"]:
            return jsonify({"message": "저장할 시트를 인식할 수 없습니다."})

        if save_to_sheet(matched_sheet, member_name, text):
            return jsonify({"message": f"{member_name}님의 {matched_sheet} 저장이 완료되었습니다."})
        else:
            return jsonify({"message": f"같은 내용이 이미 '{matched_sheet}' 시트에 저장되어 있습니다."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



    
    
    
    
    




    












@app.route("/search_memo_by_tags", methods=["POST"])
def search_memo_by_tags():
    try:
        data = request.get_json()
        input_tags = data.get("tags", [])
        limit = int(data.get("limit", 10))
        sort_by = data.get("sort_by", "date").lower()
        min_match = int(data.get("min_match", 1))

        if not input_tags:
            return jsonify({"error": "태그 리스트가 비어 있습니다."}), 400
        if sort_by not in ["date", "tag"]:
            return jsonify({"error": "sort_by는 'date' 또는 'tag'만 가능합니다."}), 400

        sheet = get_mymemo_sheet()
        values = sheet.get_all_values()[1:]  # 헤더 제외
        results = []

        for row in values:
            if len(row) < 3:
                continue
            member, date_str, content = row[0], row[1], row[2]

            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue  # 날짜 형식 오류시 건너뜀

            memo_tags = extract_nouns(content)
            similarity = len(set(input_tags) & set(memo_tags))
            if similarity >= min_match:
                results.append({
                    "회원명": member,
                    "날짜": date_str,
                    "내용": content,
                    "일치_태그수": similarity,
                    "날짜_obj": parsed_date
                })

        # 정렬 조건 적용
        if sort_by == "tag":
            results.sort(key=lambda x: (x["일치_태그수"], x["날짜_obj"]), reverse=True)
        else:  # 기본: 날짜순
            results.sort(key=lambda x: (x["날짜_obj"], x["일치_태그수"]), reverse=True)

        # 날짜 객체 제거
        for r in results:
            del r["날짜_obj"]

        return jsonify({"검색결과": results[:limit]}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500








@app.route("/debug_sheets")
def debug_sheets():
    try:
        keyfile_dict = json.loads(os.getenv("GOOGLE_SHEET_KEY"))
        keyfile_dict["private_key"] = keyfile_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
        client = gspread.authorize(creds)  # ✅ 이 줄 추가
        sheet = client.open("members_list_main")
        titles = [ws.title for ws in sheet.worksheets()]
        return jsonify({"시트목록": titles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500











# 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


