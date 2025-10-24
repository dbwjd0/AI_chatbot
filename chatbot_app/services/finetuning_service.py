import json
from ..models import UserAttribute, UserRelationship
from .prompt_service import build_persona_system_prompt

def log_for_finetuning(system_prompt, user_message, assistant_message, filename="finetuning_dataset.jsonl"):
    """
    대화 턴을 파인튜닝을 위한 JSONL 파일에 추가합니다.
    """
    try:
        # OpenAI의 파인튜닝 형식에 맞는 데이터 구조
        training_example = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message}
            ]
        }

        # JSONL 형식으로 파일에 추가하며, UTF-8 인코딩을 보장합니다.
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(json.dumps(training_example, ensure_ascii=False) + '\n')

    except Exception as e:
        # 메인 애플리케이션을 중단시키지 않고 콘솔에 오류를 기록합니다.
        print(f"--- Could not write to fine-tuning log: {e} ---")

def anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text, explanation):
    """
    데이터를 익명화한 후 파인튜닝을 위해 기록합니다.
    """
    user = request.user
    finetuning_system_prompt = build_persona_system_prompt(user)
    
    names_to_replace = {user.username}
    try:
        preferred_name_obj = UserAttribute.objects.filter(user=user, fact_type='이름').last()
        if preferred_name_obj and preferred_name_obj.content:
            names_to_replace.add(preferred_name_obj.content)
    except Exception as e:
        print(f"--- 로깅을 위한 선호 이름 검색 중 오류 발생: {e} ---")
        pass

    generic_finetuning_prompt = finetuning_system_prompt
    generic_bot_message = bot_message_text
    generic_explanation = explanation # 익명화를 위해 설명 복사

    for name in names_to_replace:
        if name:
            generic_finetuning_prompt = generic_finetuning_prompt.replace(f"{name}님", '사용자님').replace(name, '사용자')
            generic_bot_message = generic_bot_message.replace(f"{name}님", '사용자님').replace(name, '사용자')
            generic_explanation = generic_explanation.replace(f"{name}님", '사용자님').replace(name, '사용자')

    try:
        relationships = UserRelationship.objects.filter(user=user)
        if relationships.exists():
            sorted_relationships = sorted(relationships, key=lambda r: len(r.name), reverse=True)
            for rel in sorted_relationships:
                if rel.name:
                    placeholder = f"[{rel.relationship_type}]"
                    generic_bot_message = generic_bot_message.replace(rel.name, placeholder)
                    generic_explanation = generic_explanation.replace(rel.name, placeholder) # 설명도 익명화
    except Exception as e:
        print(f"--- 로깅을 위한 제3자 이름 대체 중 오류 발생: {e} ---")
        pass

    # 어시스턴트의 최종 콘텐츠를 JSON 형식으로 구성
    assistant_content = {
        "answer": generic_bot_message,
        "explanation": generic_explanation
    }
    assistant_content_str = json.dumps(assistant_content, ensure_ascii=False)

    log_for_finetuning(generic_finetuning_prompt, user_message_text, assistant_content_str)