"""
Reinforcement Learning-Based Feature Selection

Uses an RL agent to learn optimal feature subset selection
by maximizing downstream model performance.

The agent learns a policy π(a|s) where:
- State s: current feature subset
- Action a: add/remove a feature
- Reward r: model performance improvement
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import random
from typing import List, Tuple, Optional
import logging
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger(__name__)


class FeatureSelectionEnvironment:
    """Environment for RL-based feature selection"""
    
    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        max_features: int = 40,
        evaluator_model=None
    ):
        """
        Initialize feature selection environment
        
        Args:
            X: Features
            y: Labels
            max_features: Maximum features to select
            evaluator_model: Model to evaluate feature subsets (default: RandomForest)
        """
        self.X = X
        self.y = y
        self.num_features = X.shape[1]
        self.max_features = max_features
        
        # Evaluator model
        if evaluator_model is None:
            self.evaluator = RandomForestClassifier(
                n_estimators=50,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        else:
            self.evaluator = evaluator_model
        
        # State: binary mask of selected features
        self.selected_features = np.zeros(self.num_features, dtype=bool)
        self.baseline_score = None
        
        logger.info(f"Environment: {self.num_features} features, max {max_features}")
    
    def reset(self) -> np.ndarray:
        """Reset environment to initial state"""
        # Start with random feature subset
        initial_count = min(10, self.max_features)
        initial_indices = np.random.choice(
            self.num_features,
            initial_count,
            replace=False
        )
        self.selected_features = np.zeros(self.num_features, dtype=bool)
        self.selected_features[initial_indices] = True
        
        # Compute baseline with all features
        if self.baseline_score is None:
            self.baseline_score = self._evaluate_features(
                np.ones(self.num_features, dtype=bool)
            )
            logger.info(f"Baseline score (all features): {self.baseline_score:.4f}")
        
        return self.selected_features.astype(np.float32)
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool]:
        """
        Take action (toggle feature)
        
        Args:
            action: Feature index to toggle
            
        Returns:
            Tuple of (next_state, reward, done)
        """
        # Toggle feature
        self.selected_features[action] = not self.selected_features[action]
        
        num_selected = np.sum(self.selected_features)
        
        # Check if within limits
        if num_selected == 0:
            # Can't have zero features
            self.selected_features[action] = True
            reward = -1.0
            done = False
        elif num_selected > self.max_features:
            # Too many features
            self.selected_features[action] = False
            reward = -0.5
            done = False
        else:
            # Evaluate current feature subset
            score = self._evaluate_features(self.selected_features)
            
            # Reward: improvement over baseline + penalty for too many features
            reward = (score - self.baseline_score) * 10
            reward -= (num_selected / self.num_features) * 0.5  # Sparsity bonus
            
            # Done if reached max features or good enough
            done = (num_selected >= self.max_features) or (score > 0.95)
        
        return self.selected_features.astype(np.float32), reward, done
    
    def _evaluate_features(self, feature_mask: np.ndarray) -> float:
        """
        Evaluate performance with selected features
        
        Args:
            feature_mask: Boolean mask of selected features
            
        Returns:
            Cross-validation score
        """
        if np.sum(feature_mask) == 0:
            return 0.0
        
        X_selected = self.X[:, feature_mask]
        
        # Use subset for faster evaluation
        sample_size = min(5000, len(self.X))
        sample_idx = np.random.choice(len(self.X), sample_size, replace=False)
        
        try:
            scores = cross_val_score(
                self.evaluator,
                X_selected[sample_idx],
                self.y[sample_idx],
                cv=3,
                n_jobs=-1,
                scoring='accuracy'
            )
            return np.mean(scores)
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return 0.0


class DQNAgent(nn.Module):
    """Deep Q-Network for feature selection"""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 128
    ):
        """
        Initialize DQN agent
        
        Args:
            state_dim: Dimension of state (number of features)
            action_dim: Dimension of action space (number of features)
            hidden_dim: Hidden layer dimension
        """
        super(DQNAgent, self).__init__()
        
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, action_dim)
        )
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Forward pass"""
        return self.network(state)


class RLFeatureSelector:
    """Reinforcement Learning-based feature selector"""
    
    def __init__(
        self,
        num_features: int,
        max_features: int = 40,
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995
    ):
        """
        Initialize RL feature selector
        
        Args:
            num_features: Total number of features
            max_features: Maximum features to select
            learning_rate: Learning rate
            gamma: Discount factor
            epsilon_start: Initial exploration rate
            epsilon_end: Final exploration rate
            epsilon_decay: Epsilon decay rate
        """
        self.num_features = num_features
        self.max_features = max_features
        
        # DQN
        self.policy_net = DQNAgent(num_features, num_features)
        self.target_net = DQNAgent(num_features, num_features)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        
        # Hyperparameters
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        
        # Replay buffer
        self.memory = deque(maxlen=10000)
        self.batch_size = 32
        
        logger.info(f"Initialized RL Feature Selector (DQN)")
    
    def select_action(self, state: np.ndarray) -> int:
        """
        Select action using epsilon-greedy policy
        
        Args:
            state: Current state (feature mask)
            
        Returns:
            Action (feature index to toggle)
        """
        if random.random() < self.epsilon:
            # Explore: random action
            return random.randint(0, self.num_features - 1)
        else:
            # Exploit: best action
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                q_values = self.policy_net(state_tensor)
                return q_values.argmax().item()
    
    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Store transition in replay buffer"""
        self.memory.append((state, action, reward, next_state, done))
    
    def train_step(self):
        """Train DQN with experience replay"""
        if len(self.memory) < self.batch_size:
            return
        
        # Sample batch
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        states = torch.FloatTensor(np.array(states))
        actions = torch.LongTensor(actions)
        rewards = torch.FloatTensor(rewards)
        next_states = torch.FloatTensor(np.array(next_states))
        dones = torch.FloatTensor(dones)
        
        # Current Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1))
        
        # Target Q values
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            target_q = rewards + (1 - dones) * self.gamma * next_q
        
        # Loss
        loss = self.criterion(current_q.squeeze(), target_q)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
    
    def update_target_network(self):
        """Update target network"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
    
    def decay_epsilon(self):
        """Decay exploration rate"""
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
    
    def train(
        self,
        env: FeatureSelectionEnvironment,
        num_episodes: int = 100,
        update_freq: int = 10
    ) -> List[int]:
        """
        Train RL agent to select features
        
        Args:
            env: Feature selection environment
            num_episodes: Number of training episodes
            update_freq: Frequency to update target network
            
        Returns:
            List of selected feature indices
        """
        logger.info(f"Training RL agent for {num_episodes} episodes...")
        
        best_reward = -float('inf')
        best_features = None
        
        for episode in range(num_episodes):
            state = env.reset()
            episode_reward = 0
            step = 0
            
            while step < 50:  # Max steps per episode
                # Select and take action
                action = self.select_action(state)
                next_state, reward, done = env.step(action)
                
                # Store transition
                self.store_transition(state, action, reward, next_state, done)
                
                # Train
                loss = self.train_step()
                
                episode_reward += reward
                state = next_state
                step += 1
                
                if done:
                    break
            
            # Update target network
            if episode % update_freq == 0:
                self.update_target_network()
            
            # Decay epsilon
            self.decay_epsilon()
            
            # Track best
            if episode_reward > best_reward:
                best_reward = episode_reward
                best_features = np.where(state > 0.5)[0]
            
            if episode % 10 == 0:
                logger.info(
                    f"Episode {episode}/{num_episodes} | "
                    f"Reward: {episode_reward:.2f} | "
                    f"Features: {np.sum(state):.0f} | "
                    f"Epsilon: {self.epsilon:.3f}"
                )
        
        logger.info(f"Training complete! Best reward: {best_reward:.2f}")
        logger.info(f"Best feature subset: {len(best_features)} features")
        
        return best_features.tolist()


def train_rl_feature_selector(
    X: np.ndarray,
    y: np.ndarray,
    max_features: int = 40,
    num_episodes: int = 100
) -> Tuple[List[int], RLFeatureSelector]:
    """
    Train RL-based feature selector
    
    Args:
        X: Features
        y: Labels
        max_features: Maximum features to select
        num_episodes: Number of training episodes
        
    Returns:
        Tuple of (selected feature indices, trained agent)
    """
    logger.info("="*70)
    logger.info("RL-Based Feature Selection (Deep Q-Learning)")
    logger.info("="*70)
    
    # Sample for faster training
    if len(X) > 20000:
        logger.info("Sampling 20,000 records for training...")
        sample_idx = np.random.choice(len(X), 20000, replace=False)
        X_sample, y_sample = X[sample_idx], y[sample_idx]
    else:
        X_sample, y_sample = X, y
    
    # Create environment
    env = FeatureSelectionEnvironment(X_sample, y_sample, max_features)
    
    # Create agent
    agent = RLFeatureSelector(
        num_features=X.shape[1],
        max_features=max_features
    )
    
    # Train
    selected_indices = agent.train(env, num_episodes=num_episodes)
    
    return selected_indices, agent
