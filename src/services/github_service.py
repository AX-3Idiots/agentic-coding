import os
import time
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

def get_github_app_token() -> str:
    """
    .env 파일에 저장된 GitHub App 정보를 사용하여
    1시간 동안 유효한 단기 설치 토큰(Installation Token)을 발급받습니다.
    """
    # 이제 os.environ.get()이 .env 파일에 저장된 값들을 읽어올 수 있습니다.
    app_id = os.environ.get("APP_ID")
    private_key = os.environ.get("PRIVATE_KEY")
    installation_id = os.environ.get("INSTALLATION_ID")

    if not all([app_id, private_key, installation_id]):
        raise ValueError("필수 환경 변수(YOUR_APP_ID, YOUR_APP_PRIVATE_KEY, YOUR_INSTALLATION_ID)가 설정되지 않았습니다.")

    # 1. JWT (JSON Web Token) 생성 (유효기간 10분)
    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + (10 * 60),
        "iss": app_id
    }

    generated_jwt = jwt.encode(payload, private_key, algorithm="RS256")

    # 2. JWT를 사용하여 단기 설치 토큰 요청 (유효기간 1시간)
    headers = {
        "Authorization": f"Bearer {generated_jwt}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    response = requests.post(url, headers=headers)
    response.raise_for_status()

    # 3. 최종적으로 사용할 단기 토큰 반환
    return response.json()["token"]