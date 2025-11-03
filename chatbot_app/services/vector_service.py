
import openai
import os
from qdrant_client import QdrantClient, models
from django.conf import settings

# Qdrant 클라이언트 초기화
# docker-compose.yml에 정의된 서비스 이름을 호스트로 사용합니다.
client = QdrantClient(
    host=settings.QDRANT_HOST,
    port=settings.QDRANT_PORT,
    #api_key=settings.QDRANT_API_KEY or None,
    #https=settings.QDRANT_USE_HTTPS,
)


# OpenAI API 키 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

def get_embedding(text):
    """주어진 텍스트에 대한 임베딩을 OpenAI API를 통해 생성합니다."""
    response = openai.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return response.data[0].embedding

def get_or_create_collection(name="chat_history"):
    """
    지정된 이름의 컬렉션을 가져오거나, 없으면 새로 생성합니다.
    OpenAI 임베딩 모델에 맞는 벡터 파라미터로 설정합니다.
    """
    try:
        client.get_collection(collection_name=name)
    except Exception:
        client.recreate_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
        )
    return name

def upsert_message(collection_name, chat_message):
    """
    ChatMessage 객체 하나를 받아 Qdrant에 벡터화하여 저장(upsert)합니다.
    """
    try:
        print(f"--- [Qdrant Debug] Upserting message ID: {chat_message.id}, Speaker: {'user' if chat_message.is_user else 'ai'}, User ID: {chat_message.user.id}, Message: {chat_message.message[:50]}... ---")
        
        # 1. 메시지 내용으로 임베딩 생성
        vector = get_embedding(chat_message.message)
        
        # 2. Qdrant에 데이터(Point) 업로드
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=str(chat_message.id),
                    vector=vector,
                    payload={
                        "speaker": "user" if chat_message.is_user else "ai",
                        "user_id": chat_message.user.id,
                        "timestamp": chat_message.timestamp.isoformat(),
                        "document": chat_message.message # 원본 메시지도 payload에 저장
                    }
                )
            ],
            wait=True # 데이터가 완전히 저장될 때까지 대기
        )
        print(f"--- [Qdrant Debug] Successfully upserted message ID: {chat_message.id} ---")
    except Exception as e:
        print(f"--- [Qdrant] Error upserting message ID {chat_message.id}: {e} ---")

def query_similar_messages(collection_name, query_text, user_id, n_results=3, score_threshold=0.75):
    """
    주어진 텍스트와 가장 유사한 대화 내용을 Qdrant에서 검색합니다.
    특정 사용자의 대화 내용만 검색하도록 메타데이터 필터링을 사용합니다.
    유사도 점수 임계값을 적용하여 충분히 유사한 결과만 반환합니다.
    """
    try:
        # 1. 검색어에 대한 임베딩 생성
        query_vector = get_embedding(query_text)

        # 2. Qdrant에서 유사도 검색 실행
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id)
                    )
                ]
            ),
            limit=n_results,
            score_threshold=score_threshold, # 코사인 유사도 점수 임계값 (높을수록 유사)
            with_payload=True # payload 데이터도 함께 반환
        )

        # 3. 결과 형식 변환 (기존 코드와 호환되도록)
        filtered_results = {
            'ids': [hit.id for hit in search_results],
            'documents': [hit.payload.get('document', '') for hit in search_results],
            'metadatas': [{k: v for k, v in hit.payload.items() if k != 'document'} for hit in search_results],
            'scores': [hit.score for hit in search_results] # Qdrant는 score를 반환 (distance가 아님)
        }
        
        return filtered_results
    except Exception as e:
        print(f"--- [Qdrant] Error querying collection: {e} ---")
        return None
