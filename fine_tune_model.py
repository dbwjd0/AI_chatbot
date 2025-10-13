import openai
import os
from dotenv import load_dotenv
import time

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# OpenAI API 키를 환경 변수에서 가져옵니다.
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("오류: OPENAI_API_KEY가 설정되지 않았습니다.")
    print("프로젝트 루트에 '.env' 파일을 만들고 다음 내용을 추가하세요:")
    print("OPENAI_API_KEY='your_api_key_here'")
else:
    try:
        client = openai.OpenAI(api_key=api_key)

        # 1. 파일 업로드
        print("학습 파일을 업로드하는 중...")
        training_file = client.files.create(
            file=open("C:\\Users\\Admin\\project3\\finetuning_snapshot.jsonl", "rb"),
            purpose="fine-tune"
        )
        print(f"파일 업로드 완료. 파일 ID: {training_file.id}")

        # 2. 파인튜닝 작업 생성
        print("파인튜닝 작업을 생성하는 중...")
        job = client.fine_tuning.jobs.create(
            training_file=training_file.id,
            model="gpt-3.5-turbo"
        )
        print(f"파인튜닝 작업 생성 완료. 작업 ID: {job.id}")
        print("OpenAI 웹사이트에서 작업 상태를 확인하거나, 아래 명령어로 상태를 확인할 수 있습니다.")
        print(f"openai api fine_tuning.jobs.retrieve -i {job.id}")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
