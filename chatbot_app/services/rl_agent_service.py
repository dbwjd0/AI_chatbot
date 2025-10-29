"""
 강화학습(RL) 에이전트 서비스
이 서비스는 채팅 응답 생성을 위해 어떤 컨텍스트와 페르소나를 사용할지 결정합니다.
"""
import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from transformers import AutoTokenizer, AutoModel
from django.contrib.auth.models import User
from django.conf import settings
from ..services import prompt_service

# --- 1. 행동(Action) 공간 정의 ---
ACTION_MAP = {
    # --- 1. 가벼운 대화 (일상, 잡담) ---
    0: {'name': 'Chit-Chat (Tsundere)', 
        'contexts': ['attributes'], 
        'persona': '츤데레'},
    
    # --- 2. 관계 형성 (사용자 개인사에 관심 표현) ---
    1: {'name': 'Daily_Check-in (Friend)', 
        'contexts': ['attributes', 'activity', 'schedule'], 
        'persona': '친구'},
    2: {'name': 'Social_Inquiry (Friend)', 
        'contexts': ['attributes', 'relationship', 'vector_search'], 
        'persona': '친구'},

    # --- 3. 정보 검색 및 추천 ---
    3: {'name': 'Simple_Search (Advisor)', 
        'contexts': ['attributes', 'vector_search'], 
        'persona': '조언가'},
    4: {'name': 'Location_Search (Friend)', 
        'contexts': ['attributes', 'activity', 'vector_search', 'location'], 
        'persona': '친구'},

    # --- 4. 종합 분석 및 조언 (깊은 대화) ---
    5: {'name': 'Deep_Analysis_Advisor', 
        'contexts': ['schedule', 'location', 'vector_search', 'attributes', 'activity', 'analytics', 'relationship'], 
        'persona': '조언가'},
    6: {'name': 'Deep_Analysis_Friend', 
        'contexts': ['schedule', 'location', 'vector_search', 'attributes', 'activity', 'analytics', 'relationship'], 
        'persona': '친구'},

    # --- 5. 일반적인 중간 전략 (범용) ---
    7: {'name': 'Standard_Tsundere', 
        'contexts': ['attributes', 'activity', 'vector_search'], 
        'persona': '츤데레'},

    # --- 6. 새로운 관계 기반 스타일 ---
    8: {'name': 'Deep_Analysis_Senior',
        'contexts': ['schedule', 'location', 'vector_search', 'attributes', 'activity', 'analytics', 'relationship'],
        'persona': '선배'},
    9: {'name': 'Chit_Chat_Younger_Sibling',
        'contexts': ['attributes'],
        'persona': '동생'},

    # --- 7. 사용자 정의 스타일 ---
    10: {'name': 'User_Defined_Style',
         'contexts': ['schedule', 'location', 'vector_search', 'attributes', 'activity', 'analytics', 'relationship'],
         'persona': '사용자 정의'}
}
NUM_ACTIONS = len(ACTION_MAP)

# --- 2. 정책 신경망(Policy Network) 정의 ---
class PolicyNetwork(nn.Module):
    def __init__(self, state_dim):
        super(PolicyNetwork, self).__init__()
        self.layer1 = nn.Linear(state_dim, 128)
        self.layer2 = nn.Linear(128, NUM_ACTIONS)
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax(dim=-1)

    def forward(self, state):
        x = self.relu(self.layer1(state))
        action_probabilities = self.softmax(self.layer2(x))
        return action_probabilities

# --- 3. 강화학습 에이전트 클래스 정의 (오류 수정) ---
class RLAgent:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RLAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            model_name = "jhgan/ko-sbert-sts"
            print(f"--- 사용자 인식 RL 에이전트 초기화 시작 (모델: {model_name}) ---")
            
            self.model_dir = os.path.join(settings.BASE_DIR, 'trained_models')
            self.model_path = os.path.join(self.model_dir, 'rl_agent_policy.pth')
            os.makedirs(self.model_dir, exist_ok=True)

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            
            self.max_users = 1000
            self.user_embedding_dim = 16
            self.user_embedding = nn.Embedding(self.max_users, self.user_embedding_dim)

            self.state_dim = self.user_embedding_dim + (self.model.config.hidden_size * 2) + 1
            
            self.policy_network = PolicyNetwork(self.state_dim)
            self.optimizer = optim.Adam(self.policy_network.parameters(), lr=0.001)
            
            self._load_model()
            self.initialized = True
            print(f"--- RL 에이전트 초기화 완료 (상태 차원: {self.state_dim}) ---")

    def _save_model(self):
        try:
            torch.save(self.policy_network.state_dict(), self.model_path)
            print(f"--- RL 에이전트 모델 저장 완료: {self.model_path} ---")
        except Exception as e:
            print(f"--- RL 에이전트 모델 저장 오류: {e} ---")

    def _load_model(self):
        if not os.path.exists(self.model_path):
            print(f"--- 저장된 모델 없음: {self.model_path}. 새 모델로 시작합니다. ---")
            return
        try:
            self.policy_network.load_state_dict(torch.load(self.model_path))
            print(f"--- RL 에이전트 모델 로드 완료: {self.model_path} ---")
        except Exception as e:
            print(f"--- RL 에이전트 모델 로드 오류: {e}. 새 모델로 시작합니다. ---")

    def _get_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1)

    def _build_state_vector(self, user, user_message_text, history):
        user_index = user.id % self.max_users
        user_id_tensor = torch.tensor([user_index], dtype=torch.long)
        user_embed = self.user_embedding(user_id_tensor)

        user_message_embedding = self._get_embedding(user_message_text)
        last_ai_message = history.filter(is_user=False).first()
        if last_ai_message:
            last_ai_embedding = self._get_embedding(last_ai_message.message)
        else:
            last_ai_embedding = torch.zeros_like(user_message_embedding)
        affinity_score = user.profile.affinity_score / 100.0
        affinity_tensor = torch.tensor([[affinity_score]], dtype=torch.float32)
        state_vector = torch.cat((user_embed, user_message_embedding, last_ai_embedding, affinity_tensor), dim=1)
        return state_vector

    def select_action(self, state_vector):
        probabilities = self.policy_network(state_vector)
        action_id = torch.argmax(probabilities).item()
        return action_id

    def learn(self, state, action, reward):
        print(f"--- [RL 에이전트] 학습 시작. 행동: {action}, 보상: {reward} ---")
        self.optimizer.zero_grad()
        probabilities = self.policy_network(state.squeeze(0))
        log_prob = torch.log(probabilities[action])
        loss = -log_prob * reward
        loss.backward()
        self.optimizer.step()
        print(f"--- [RL 에이전트] 학습 완료. 손실: {loss.item()} ---")
        self._save_model()

# --- 4. 서비스 메인 함수 ---
agent = RLAgent()

def decide_action(user, user_message_text: str, history, has_image: bool):
    state_vector = agent._build_state_vector(user, user_message_text, history)
    action_id = agent.select_action(state_vector)
    chosen_action_info = ACTION_MAP.get(action_id)

    print(f"--- [RL 에이전트] 상태 생성됨. 선택된 행동 ID: {action_id} ({chosen_action_info['name']}) ---")

    contexts_to_use = chosen_action_info['contexts']
    if has_image and 'vector_search' in contexts_to_use:
        contexts_to_use.remove('vector_search')

    chosen_persona_name = chosen_action_info['persona']
    persona_prompt = prompt_service.build_persona_system_prompt(user, persona_name=chosen_persona_name)
    
    action = {
        'contexts_to_use': contexts_to_use,
        'persona_prompt': persona_prompt,
        'action_id': action_id,
        'state_vector': state_vector
    }
    
    return action



