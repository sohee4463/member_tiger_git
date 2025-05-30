import os
import subprocess
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 불러오기
RENDER_API_KEY = os.getenv("RENDER_API_KEY")
RENDER_SERVICE_ID = os.getenv("RENDER_SERVICE_ID")
RENDER_DEPLOY_HOOK_URL = os.getenv("RENDER_DEPLOY_HOOK_URL")

# 1. GitHub에 코드 푸시
def push_to_github():
    try:
        subprocess.run("git add .", check=True, shell=True)
        subprocess.run('git commit -m "Auto update"', check=True, shell=True)
        subprocess.run("git push origin main", check=True, shell=True)
        print("✅ GitHub에 코드 푸시 완료")
    except subprocess.CalledProcessError:
        print("⚠️ GitHub 푸시 중 오류 발생 (변경사항 없음 등)")

# 2. Render에 배포 트리거
def trigger_render_deploy():
    try:
        response = requests.post(RENDER_DEPLOY_HOOK_URL)
        if response.status_code == 200:
            print("✅ Render 배포 트리거 성공")
        else:
            print(f"⚠️ Render 배포 실패: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Render 배포 중 예외 발생: {e}")

# 실행
if __name__ == "__main__":
    push_to_github()
    trigger_render_deploy()
