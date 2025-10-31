"""
 강화학습(RL) 에이전트 서비스 (PPO, Multi-Discrete Action Space 기반)
이 서비스는 채팅 응답 생성을 위해 페르소나와 컨텍스트 조합을 동적으로 결정합니다.
"""
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from transformers import AutoTokenizer, AutoModel
from django.contrib.auth.models import User
from django.conf import settings
from ..services import prompt_service, emotion_service

# --- 1. 행동(Action) 공간 재설계 (Multi-Discrete) ---
PERSONA_MAP = {0: '친구', 1: '조언가', 2: '선배', 3: '츤데레', 4: '동생', 5: '사용자 정의'}
CONTEXT_LIST = ['schedule', 'location', 'vector_search', 'attributes', 'activity', 'analytics', 'relationship']
SPECIAL_ACTION_MAP = {0: 'None', 1: 'Ask_Question'}

# 감정 및 토픽 정의
EMOTION_TO_INDEX = {'공포': 0, '놀람': 1, '분노': 2, '슬픔': 3, '중립': 4, '행복': 5, '혐오': 6}
NUM_EMOTIONS = len(EMOTION_TO_INDEX)
TOPIC_TO_INDEX = {'일상': 0, '정보': 1, '감정': 2, '기타': 3}
NUM_TOPICS = len(TOPIC_TO_INDEX)

# --- 2. Actor-Critic 신경망 재설계 (Multi-Head) ---
class ActorCriticNetwork(nn.Module):
    def __init__(self, state_dim, persona_dim, context_dim, special_dim):
        super(ActorCriticNetwork, self).__init__()
        self.shared_layer = nn.Linear(state_dim, 128)
        
        # Heads for each action dimension
        self.persona_head = nn.Linear(128, persona_dim)
        self.context_head = nn.Linear(128, context_dim)
        self.special_head = nn.Linear(128, special_dim)
        self.critic_head = nn.Linear(128, 1)

    def forward(self, state):
        x = F.relu(self.shared_layer(state))
        
        # Probabilities for categorical actions
        persona_probs = F.softmax(self.persona_head(x), dim=-1)
        special_probs = F.softmax(self.special_head(x), dim=-1)
        
        # Logits for binary (on/off) context actions
        context_logits = self.context_head(x)
        
        state_value = self.critic_head(x)
        return persona_probs, torch.sigmoid(context_logits), special_probs, state_value

    def evaluate(self, state, persona_action, context_actions, special_action):
        x = F.relu(self.shared_layer(state))
        
        # Persona evaluation
        persona_probs = F.softmax(self.persona_head(x), dim=-1)
        persona_dist = torch.distributions.Categorical(persona_probs)
        persona_log_probs = persona_dist.log_prob(persona_action)
        persona_entropy = persona_dist.entropy()

        # Context evaluation (Bernoulli for on/off)
        context_logits = self.context_head(x)
        context_dist = torch.distributions.Bernoulli(logits=context_logits)
        context_log_probs = context_dist.log_prob(context_actions).sum(dim=-1) # Sum log_probs across contexts
        context_entropy = context_dist.entropy().sum(dim=-1)

        # Special action evaluation
        special_probs = F.softmax(self.special_head(x), dim=-1)
        special_dist = torch.distributions.Categorical(special_probs)
        special_log_probs = special_dist.log_prob(special_action)
        special_entropy = special_dist.entropy()

        state_value = self.critic_head(x)

        # Combine log_probs and entropies
        total_log_probs = persona_log_probs + context_log_probs + special_log_probs
        total_entropy = persona_entropy + context_entropy + special_entropy

        return total_log_probs, torch.squeeze(state_value), total_entropy

# --- 3. PPO 기반 강화학습 에이전트 클래스 정의 ---
class RLAgent:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RLAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            model_name = "jhgan/ko-sbert-sts"
            print(f"--- PPO 에이전트(Multi-Discrete) 초기화 시작 (모델: {model_name}) ---")
            
            self.model_dir = os.path.join(settings.BASE_DIR, 'trained_models')
            self.model_path = os.path.join(self.model_dir, 'ppo_agent_multidiscrete.pth')
            os.makedirs(self.model_dir, exist_ok=True)

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.sbert_model = AutoModel.from_pretrained(model_name)
            
            self.user_embedding_dim = 16
            self.user_embedding = nn.Embedding(1000, self.user_embedding_dim)

            sbert_dim = self.sbert_model.config.hidden_size
            self.state_dim = self.user_embedding_dim + sbert_dim * 2 + 1 + 1 + NUM_TOPICS
            
            self.ac_network = ActorCriticNetwork(self.state_dim, len(PERSONA_MAP), len(CONTEXT_LIST), len(SPECIAL_ACTION_MAP))
            self.optimizer = optim.Adam(self.ac_network.parameters(), lr=0.0003)
            
            self.gamma = 0.99
            self.eps_clip = 0.2
            self.K_epochs = 4
            self.gae_lambda = 0.95 # GAE 람다 값 추가

            # 확신도 기반 질문을 위한 하이퍼파라미터
            self.CONFIDENCE_THRESHOLD = -0.5 # 이 값보다 낮으면 질문을 강제
            self.ENTROPY_WEIGHT = 0.01 # 엔트로피가 확신도에 미치는 영향

            self._load_model()
            self.initialized = True
            print(f"--- PPO 에이전트(Multi-Discrete) 초기화 완료 (상태 차원: {self.state_dim}) ---")

    def _save_model(self):
        torch.save(self.ac_network.state_dict(), self.model_path)

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.ac_network.load_state_dict(torch.load(self.model_path))

    def _get_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            return self.sbert_model(**inputs).last_hidden_state.mean(dim=1)

    def _get_topic(self, user_message_text: str) -> str:
        if "추천" in user_message_text or "알려줘" in user_message_text: return "정보"
        if "기분" in user_message_text or "슬퍼" in user_message_text or "행복" in user_message_text: return "감정"
        return "일상"

    def _build_state_vector(self, user, user_message_text, history, user_emotion: str):
        user_embed = self.user_embedding(torch.tensor([user.id % 1000], dtype=torch.long))
        user_message_embedding = self._get_embedding(user_message_text)
        recent_history = history[:3]
        history_embedding = torch.mean(torch.cat([self._get_embedding(msg.message) for msg in recent_history]), dim=0, keepdim=True) if recent_history else torch.zeros_like(user_message_embedding)
        affinity_tensor = torch.tensor([[user.profile.affinity_score / 100.0]], dtype=torch.float32)
        emotion_tensor = torch.tensor([[EMOTION_TO_INDEX.get(user_emotion, 4) / (NUM_EMOTIONS - 1)]], dtype=torch.float32)
        topic_tensor = F.one_hot(torch.tensor([TOPIC_TO_INDEX.get(self._get_topic(user_message_text), 3)]), num_classes=NUM_TOPICS).float()
        return torch.cat((user_embed, user_message_embedding, history_embedding, affinity_tensor, emotion_tensor, topic_tensor), dim=1)

    def learn(self, trajectory):
        # 1. Trajectory 데이터를 텐서로 변환
        old_states = torch.squeeze(torch.tensor([exp['state'] for exp in trajectory], dtype=torch.float32), 1)
        old_actions = [exp['action'] for exp in trajectory]
        old_log_probs = torch.tensor([exp['log_prob'] for exp in trajectory], dtype=torch.float32)
        old_values = torch.tensor([exp['value'] for exp in trajectory], dtype=torch.float32)
        rewards = torch.tensor([exp['reward'] for exp in trajectory], dtype=torch.float32)
        dones = torch.tensor([exp['done'] for exp in trajectory], dtype=torch.float32)

        # 2. GAE (Generalized Advantage Estimation) 및 Returns 계산
        advantages = torch.zeros_like(rewards)
        returns = torch.zeros_like(rewards)
        last_advantage = 0
        last_return = 0
        # 마지막 턴의 next_value는 0으로 간주 (done=True이므로)
        last_value = 0 
        for i in reversed(range(len(rewards))):
            # done 플래그에 따라 다음 상태의 가치를 결정
            mask = 1.0 - dones[i]
            
            # GAE 계산
            delta = rewards[i] + self.gamma * last_value * mask - old_values[i]
            last_advantage = delta + self.gamma * self.gae_lambda * last_advantage * mask
            advantages[i] = last_advantage

            # Returns 계산
            last_return = rewards[i] + self.gamma * last_return * mask
            returns[i] = last_return

            last_value = old_values[i]

        # Advantage 정규화
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-7)

        old_persona_actions = torch.tensor([a['persona'] for a in old_actions], dtype=torch.long)
        old_context_actions = torch.tensor([a['contexts'] for a in old_actions], dtype=torch.float)
        old_special_actions = torch.tensor([a['special'] for a in old_actions], dtype=torch.long)

        # 3. K 에포크 동안 정책 업데이트
        for _ in range(self.K_epochs):
            logprobs, state_values, dist_entropy = self.ac_network.evaluate(old_states, old_persona_actions, old_context_actions, old_special_actions)
            ratios = torch.exp(logprobs - old_log_probs.detach())

            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages
            
            # 최종 손실 계산: 정책 손실 + 가치 손실 + 엔트로피 보너스
            loss = -torch.min(surr1, surr2) + 0.5 * F.mse_loss(state_values, returns) - 0.01 * dist_entropy

            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()
        
        print(f"--- [PPO Multi-Discrete] 학습 완료. 최종 손실: {loss.mean().item()} ---")
        self._save_model()

# --- 4. 서비스 메인 함수 ---
agent = RLAgent()

def decide_action(user, user_message_text: str, history, has_image: bool, user_emotion: str):
    state_vector = agent._build_state_vector(user, user_message_text, history, user_emotion)
    
    with torch.no_grad():
        persona_probs, context_probs, special_probs, state_value = agent.ac_network(state_vector)
    
    # 각 분포에서 행동 샘플링을 위한 분포 객체 생성
    persona_dist = torch.distributions.Categorical(persona_probs)
    context_dist = torch.distributions.Bernoulli(context_probs)
    special_dist = torch.distributions.Categorical(special_probs)

    # 전체 엔트로피 계산 (확신도 측정용)
    total_entropy = persona_dist.entropy() + context_dist.entropy().sum() + special_dist.entropy()

    # 확신도 점수 계산: 상태 가치 - 엔트로피 가중치 * 전체 엔트로피
    # state_value는 스칼라, total_entropy도 스칼라
    confidence_score = state_value.item() - agent.ENTROPY_WEIGHT * total_entropy.item()

    # 'Ask_Question' 행동의 인덱스 찾기
    ask_question_idx = next((idx for idx, name in SPECIAL_ACTION_MAP.items() if name == 'Ask_Question'), None)
    if ask_question_idx is None: # 안전 장치
        raise ValueError("Ask_Question action not found in SPECIAL_ACTION_MAP")

    # 확신도 기반 게이팅 로직
    if confidence_score < agent.CONFIDENCE_THRESHOLD:
        # 확신도가 낮으면 '질문하기' 행동 강제
        special_action = torch.tensor(ask_question_idx)
        # 강제된 행동에 대한 log_prob 재계산
        # 다른 행동들은 원래대로 샘플링
        persona_action = persona_dist.sample()
        context_actions = context_dist.sample()
        log_prob = persona_dist.log_prob(persona_action) + context_dist.log_prob(context_actions).sum() + special_dist.log_prob(special_action)

    else:
        # 확신도가 높으면 '질문하기' 행동 마스킹 (선택 불가)
        masked_special_probs = special_probs.clone()
        masked_special_probs[:, ask_question_idx] = 0.0 # '질문하기' 확률을 0으로
        masked_special_probs = masked_special_probs / masked_special_probs.sum(dim=-1, keepdim=True) # 재정규화
        
        # 마스킹된 분포에서 다시 샘플링
        special_dist_masked = torch.distributions.Categorical(masked_special_probs)
        special_action = special_dist_masked.sample()

        # 다른 행동들은 원래대로 샘플링
        persona_action = persona_dist.sample()
        context_actions = context_dist.sample()

        # 마스킹된 행동에 대한 log_prob 재계산
        log_prob = persona_dist.log_prob(persona_action) + context_dist.log_prob(context_actions).sum() + special_dist_masked.log_prob(special_action)

    chosen_special_action_name = SPECIAL_ACTION_MAP[special_action.item()]

    # 특별 행동 처리 (이전 로직 유지)
    if chosen_special_action_name == 'Ask_Question':
        chosen_persona_name = 'Questioner'
        persona_prompt = ""  # 프롬프트 생성 생략
        contexts_to_use = []
    else:
        # 일반 행동 처리 (이전 로직 유지)
        chosen_persona_name = PERSONA_MAP[persona_action.item()]
        persona_prompt = prompt_service.build_persona_system_prompt(user, persona_name=chosen_persona_name)
        contexts_to_use = [CONTEXT_LIST[i] for i, val in enumerate(context_actions.squeeze().tolist()) if val == 1]
        if has_image and 'vector_search' in contexts_to_use:
            contexts_to_use.remove('vector_search')

    print(f"--- [PPO 에이전트] 페르소나: {chosen_persona_name}, 컨텍스트: {contexts_to_use}, 특별 행동: {chosen_special_action_name}, 확신도: {confidence_score:.2f} ---")

    action_data = {
        'contexts_to_use': contexts_to_use,
        'persona_prompt': persona_prompt,
        'chosen_persona_name': chosen_persona_name,
        'action': {
            'persona': persona_action.item(),
            'contexts': context_actions.squeeze().tolist(),
            'special': special_action.item()
        },
        'state_vector': state_vector.detach().numpy().tolist(),
        'log_prob': log_prob.item(),
        'state_value': state_value.item(),
        'confidence_score': confidence_score # 확신도 점수 추가
    }
    
    return action_data



