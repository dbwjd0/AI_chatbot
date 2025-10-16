import json
from ..models import UserAttribute, UserRelationship
from .chat_service import build_persona_system_prompt

def log_for_finetuning(system_prompt, user_message, assistant_message, filename="finetuning_dataset.jsonl"):
    """
    Appends a conversation turn to a JSONL file for fine-tuning.
    """
    try:
        # The data structure for OpenAI's fine-tuning format
        training_example = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message}
            ]
        }

        # Append to the file in JSONL format, ensuring UTF-8 encoding
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(json.dumps(training_example, ensure_ascii=False) + '\n')

    except Exception as e:
        # Log errors to the console without crashing the main application
        print(f"--- Could not write to fine-tuning log: {e} ---")

def anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text):
    """
    Prepares the data by anonymizing it, then logs it for fine-tuning.
    """
    user = request.user
    finetuning_system_prompt = build_persona_system_prompt(user)
    
    names_to_replace = {user.username}
    try:
        preferred_name_obj = UserAttribute.objects.filter(user=user, fact_type='이름').last()
        if preferred_name_obj and preferred_name_obj.content:
            names_to_replace.add(preferred_name_obj.content)
    except Exception as e:
        print(f"--- Error retrieving preferred name for logging: {e} ---")
        pass

    generic_finetuning_prompt = finetuning_system_prompt
    generic_bot_message = bot_message_text
    for name in names_to_replace:
        if name:
            generic_finetuning_prompt = generic_finetuning_prompt.replace(f"{name}님", '사용자님').replace(name, '사용자')
            generic_bot_message = generic_bot_message.replace(f"{name}님", '사용자님').replace(name, '사용자')

    try:
        relationships = UserRelationship.objects.filter(user=user)
        if relationships.exists():
            sorted_relationships = sorted(relationships, key=lambda r: len(r.name), reverse=True)
            for rel in sorted_relationships:
                if rel.name:
                    placeholder = f"[{rel.relationship_type}]"
                    generic_bot_message = generic_bot_message.replace(rel.name, placeholder)
    except Exception as e:
        print(f"--- Error replacing third-party names for logging: {e} ---")
        pass

    log_for_finetuning(generic_finetuning_prompt, user_message_text, generic_bot_message)