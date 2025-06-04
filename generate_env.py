import json

# 1. JSON 파일 열기
with open('memberslist-461116-d4758d31db08.json', 'r', encoding='utf-8') as json_file:
    data = json.load(json_file)

# 2. 문자열로 변환 (이스케이프 포함)
env_value = json.dumps(data)

# 3. .env 형식으로 작성
env_line = f'GOOGLE_SHEET_KEY={env_value}'

# 4. .env 파일에 쓰기
with open('.env', 'w', encoding='utf-8') as env_file:
    env_file.write(env_line)

print("✅ .env 파일이 생성되었습니다.")
