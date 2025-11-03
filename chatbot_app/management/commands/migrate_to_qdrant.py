import chromadb
import openai
import os
from django.core.management.base import BaseCommand
from qdrant_client import QdrantClient, models

# 기존 ChromaDB 및 새로운 Qdrant 클라이언트 설정
CHROMA_PATH = "./chroma_db"
QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333
COLLECTION_NAME = "chat_history"

# OpenAI API 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

def get_embedding(text):
    """주어진 텍스트에 대한 임베딩을 생성합니다."""
    response = openai.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return response.data[0].embedding

class Command(BaseCommand):
    help = 'Migrates chat history from ChromaDB to Qdrant.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- ChromaDB to Qdrant 마이그레이션을 시작합니다. ---'))

        try:
            # 1. 클라이언트 연결
            chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            self.stdout.write(self.style.SUCCESS('ChromaDB 및 Qdrant에 성공적으로 연결했습니다.'))

            # 2. ChromaDB에서 컬렉션 가져오기
            try:
                chroma_collection = chroma_client.get_collection(name=COLLECTION_NAME)
            except ValueError as e:
                self.stdout.write(self.style.WARNING(f'{COLLECTION_NAME} 컬렉션을 찾을 수 없습니다: {e}. 마이그레이션할 데이터가 없습니다.'))
                return

            # 3. Qdrant 컬렉션 확인 및 생성
            try:
                qdrant_client.get_collection(collection_name=COLLECTION_NAME)
                self.stdout.write(self.style.SUCCESS(f"Qdrant에 '{COLLECTION_NAME}' 컬렉션이 이미 존재합니다."))
            except Exception:
                self.stdout.write(self.style.NOTICE(f"Qdrant에 '{COLLECTION_NAME}' 컬렉션이 없어 새로 생성합니다."))
                qdrant_client.recreate_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
                )

            # 4. ChromaDB에서 모든 데이터 가져오기
            self.stdout.write('ChromaDB에서 모든 데이터를 가져오는 중...')
            all_data = chroma_collection.get(include=["documents", "metadatas"])
            count = len(all_data['ids'])
            self.stdout.write(self.style.SUCCESS(f'총 {count}개의 데이터를 가져왔습니다.'))

            if count == 0:
                self.stdout.write(self.style.WARNING('마이그레이션할 데이터가 없습니다.'))
                return

            # 5. Qdrant로 데이터 이전
            self.stdout.write('Qdrant로 데이터 이전을 시작합니다...')
            points_to_upsert = []
            for i in range(count):
                doc_id = all_data['ids'][i]
                document = all_data['documents'][i]
                metadata = all_data['metadatas'][i]

                if not document:
                    self.stdout.write(self.style.WARNING(f'ID {doc_id}의 document가 비어 있어 건너뜁니다.'))
                    continue

                # 임베딩 생성
                vector = get_embedding(document)

                # Qdrant PointStruct 생성
                # 기존 메타데이터에 원본 document 추가
                payload = metadata
                payload['document'] = document

                points_to_upsert.append(
                    models.PointStruct(
                        id=doc_id,
                        vector=vector,
                        payload=payload
                    )
                )
                
                if (i + 1) % 10 == 0 or (i + 1) == count:
                    self.stdout.write(f'{i + 1}/{count}개 데이터 처리 중...')

            # 배치로 Qdrant에 업로드
            if points_to_upsert:
                qdrant_client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points_to_upsert,
                    wait=True
                )

            self.stdout.write(self.style.SUCCESS(f'--- 총 {len(points_to_upsert)}개의 데이터를 Qdrant로 성공적으로 이전했습니다. ---'))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'마이그레이션 중 오류가 발생했습니다: {e}'))
