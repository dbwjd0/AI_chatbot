import re

def parse_emoticon(user_message_text: str) -> str:
    """
    사용자 메시지에서 이모티콘 태그를 파싱하여 LLM이 이해할 수 있는 텍스트로 변환합니다.

    Args:
        user_message_text (str): 사용자가 입력한 원본 메시지.

    Returns:
        str: 이모티콘이 텍스트로 변환되었거나, 변환이 필요 없는 경우 원본 메시지.
    """
    user_message_for_llm = user_message_text
    emoticon_match = re.search(r'<img src="/static/img/(.*?)" class="chat-emoticon".*?>', user_message_text)

    if emoticon_match:
        emoticon_filename = emoticon_match.group(1)
        # 메시지에서 HTML 이미지 태그 제거
        user_message_for_llm = re.sub(r'<img.*?>', '', user_message_text).strip()

        emoticon_meanings = {
            '결제_이모티콘.png': '구매 또는 구매 충동을 느끼며',
            '계략_이모티콘.png': '음흉한 계획을 꾸미는 듯한 표정으로',
            '돌_이모티콘.png': '당황하거나 어이없다는 듯',
            '따봉_이모티콘.png': '칭찬 또는 격려의 의미로',
            '밥_이모티콘.png': '밥을 먹고 싶다는 듯',
            '슬픔_이모티콘.png': '슬프거나 억울하다는 듯',
            '의기양양_이모티콘.png': '자신감이 넘치거나 기분 좋은 표정으로',
            '주라_이모티콘.png': '무언가를 원한다는 눈빛으로',
            '짜증_이모티콘.png': '짜증이나 화가 난다는 듯',
            '팝콘_이모티콘.png': '흥미롭게 지켜보며',
            '하트눈_이모티콘.png': '애정을 표현하며'
        }
        meaning_phrase = emoticon_meanings.get(emoticon_filename, '알 수 없는 표정으로')

        if not user_message_for_llm:
            # 텍스트 없이 이모티콘만 보낸 경우, 행동 묘사로 변환
            user_message_for_llm = f"(사용자가 '{emoticon_filename.split('_')[0]}' 이모티콘으로 {meaning_phrase} 바라본다.)"
        else:
            # 텍스트와 함께 보낸 경우, 괄호 안에 이모티콘 정보 추가
            user_message_for_llm = f"{user_message_for_llm} (사용자는 '{emoticon_filename.split('_')[0]}' 이모티콘도 함께 보냈다.)"
        
        print(f"--- [디버그] LLM 전달 메시지 변환: {user_message_for_llm} ---")

    return user_message_for_llm
