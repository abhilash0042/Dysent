"""
Differential Privacy for Federated Learning

Implements differential privacy mechanisms to provide formal privacy guarantees
for FL participants' training data.
"""

import numpy as np
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DifferentialPrivacy:
    """
    Differential Privacy mechanisms for FL.
    
    Implements Gaussian mechanism with gradient clipping for (ε, δ)-DP.
    """
    
    def __init__(
        self,
        epsilon: float = 1.0,
        delta: float = 1e-5,
        sensitivity: float = 1.0,
        clip_norm: float = 1.0
    ):
        """
        Initialize DP parameters.
        
        Args:
            epsilon: Privacy budget (lower = more private)
            delta: Failure probability
            sensitivity: L2 sensitivity of the function
            clip_norm: Gradient clipping threshold
        """
        self.epsilon = epsilon
        self.delta = delta
        self.sensitivity = sensitivity
        self.clip_norm = clip_norm
        
        # Calculate noise scale from ε and δ
        self.noise_scale = self._calculate_noise_scale()
        
        logger.info(f"Differential Privacy initialized:")
        logger.info(f"  ε (epsilon): {epsilon}")
        logger.info(f"  δ (delta): {delta}")
        logger.info(f"  Noise scale: {self.noise_scale:.4f}")
        logger.info(f"  Clip norm: {clip_norm}")
    
    def _calculate_noise_scale(self) -> float:
        """
        Calculate Gaussian noise scale for (ε, δ)-DP.
        
        Formula: σ = (sensitivity / ε) * sqrt(2 * ln(1.25/δ))
        
        Returns:
            Noise standard deviation
        """
        if self.epsilon == 0:
            return float('inf')  # Infinite noise for ε=0
        
        sigma = (self.sensitivity / self.epsilon) * np.sqrt(2 * np.log(1.25 / self.delta))
        return sigma
    
    def clip_gradients(
        self,
        weights: List[np.ndarray],
        clip_norm: float = None
    ) -> List[np.ndarray]:
        """
        Clip gradients to bounded L2 norm.
        
        Args:
            weights: Model weights
            clip_norm: Clipping threshold
            
        Returns:
            Clipped weights
        """
        if clip_norm is None:
            clip_norm = self.clip_norm
        
        # Flatten all weights
        flat_weights = np.concatenate([w.flatten() for w in weights])
        
        # Calculate L2 norm
        norm = np.linalg.norm(flat_weights)
        
        # Clip if necessary
        if norm > clip_norm:
            scale = clip_norm / norm
            clipped_weights = [w * scale for w in weights]
            logger.debug(f"Gradient clipped: {norm:.4f} → {clip_norm:.4f}")
            return clipped_weights
        else:
            return weights
    
    def add_noise(
        self,
        weights: List[np.ndarray],
        noise_scale: float = None
    ) -> List[np.ndarray]:
        """
        Add Gaussian noise to weights for DP.
        
        Args:
            weights: Model weights
            noise_scale: Noise standard deviation
            
        Returns:
            Noisy weights
        """
        if noise_scale is None:
            noise_scale = self.noise_scale
        
        noisy_weights = []
        for w in weights:
            noise = np.random.normal(0, noise_scale, w.shape).astype(w.dtype)
            noisy_weights.append(w + noise)
        
        return noisy_weights
    
    def privatize_weights(
        self,
        weights: List[np.ndarray]
    ) -> List[np.ndarray]:
        """
        Apply full DP mechanism: clip + add noise.
        
        Args:
            weights: Model weights
            
        Returns:
            Differentially private weights
        """
        # Step 1: Clip gradients
        clipped = self.clip_gradients(weights)
        
        # Step 2: Add Gaussian noise
        private = self.add_noise(clipped)
        
        return private
    
    def privatize_batch(
        self,
        weights_list: List[List[np.ndarray]]
    ) -> List[List[np.ndarray]]:
        """
        Apply DP to a batch of weight updates.
        
        Args:
            weights_list: List of weight updates from multiple nodes
            
        Returns:
            List of privatized weights
        """
        return [self.privatize_weights(weights) for weights in weights_list]
    
    def get_privacy_spent(self, num_rounds: int) -> Tuple[float, float]:
        """
        Calculate total privacy budget spent after num_rounds.
        
        Uses composition theorem for multiple queries.
        
        Args:
            num_rounds: Number of FL rounds
            
        Returns:
            (total_epsilon, total_delta)
        """
        # Simple composition: ε scales linearly, δ accumulates
        total_epsilon = self.epsilon * num_rounds
        total_delta = self.delta * num_rounds
        
        logger.info(f"Privacy spent after {num_rounds} rounds:")
        logger.info(f"  Total ε: {total_epsilon:.4f}")
        logger.info(f"  Total δ: {total_delta:.6f}")
        
        return total_epsilon, total_delta


class PrivacyAccountant:
    """
    Track and manage privacy budget throughout FL training.
    """
    
    def __init__(
        self,
        epsilon_budget: float = 10.0,
        delta_budget: float = 1e-4
    ):
        """
        Initialize privacy accountant.
        
        Args:
            epsilon_budget: Total privacy budget
            delta_budget: Total delta budget
        """
        self.epsilon_budget = epsilon_budget
        self.delta_budget = delta_budget
        self.epsilon_spent = 0.0
        self.delta_spent = 0.0
        self.rounds = 0
    
    def spend(self, epsilon: float, delta: float):
        """Record privacy spending for one round"""
        self.epsilon_spent += epsilon
        self.delta_spent += delta
        self.rounds += 1
    
    def remaining(self) -> Tuple[float, float]:
        """Get remaining privacy budget"""
        eps_remaining = max(0, self.epsilon_budget - self.epsilon_spent)
        delta_remaining = max(0, self.delta_budget - self.delta_spent)
        return eps_remaining, delta_remaining
    
    def can_continue(self) -> bool:
        """Check if budget allows more rounds"""
        eps_rem, delta_rem = self.remaining()
        return eps_rem > 0 and delta_rem > 0
    
    def summary(self) -> dict:
        """Get privacy accounting summary"""
        eps_rem, delta_rem = self.remaining()
        return {
            'rounds': self.rounds,
            'epsilon_budget': self.epsilon_budget,
            'epsilon_spent': self.epsilon_spent,
            'epsilon_remaining': eps_rem,
            'delta_budget': self.delta_budget,
            'delta_spent': self.delta_spent,
            'delta_remaining': delta_rem
        }


def test_differential_privacy():
    """Test DP mechanisms"""
    
    print("\n" + "="*70)
    print("DIFFERENTIAL PRIVACY TEST")
    print("="*70 + "\n")
    
    # Create sample weights
    weights = [
        np.random.randn(10, 5).astype(np.float32),
        np.random.randn(5).astype(np.float32)
    ]
    
    # Test different privacy levels
    privacy_levels = [
        (0.1, "Strong privacy"),
        (1.0, "Moderate privacy"),
        (10.0, "Weak privacy")
    ]
    
    for epsilon, desc in privacy_levels:
        print(f"\n{desc} (ε={epsilon}):")
        print("-" * 50)
        
        dp = DifferentialPrivacy(epsilon=epsilon, delta=1e-5, clip_norm=1.0)
        
        # Original norm
        orig_norm = np.linalg.norm(np.concatenate([w.flatten() for w in weights]))
        print(f"Original norm: {orig_norm:.4f}")
        
        # Apply DP
        private_weights = dp.privatize_weights(weights)
        private_norm = np.linalg.norm(np.concatenate([w.flatten() for w in private_weights]))
        print(f"Private norm: {private_norm:.4f}")
        
        # Calculate noise level
        noise_norm = np.linalg.norm(
            np.concatenate([w.flatten() for w in private_weights]) - 
            np.concatenate([w.flatten() for w in weights])
        )
        print(f"Noise added: {noise_norm:.4f}")
    
    # Test privacy accounting
    print("\n" + "="*70)
    print("PRIVACY ACCOUNTING TEST")
    print("="*70 + "\n")
    
    accountant = PrivacyAccountant(epsilon_budget=10.0, delta_budget=1e-4)
    
    for round_num in range(1, 21):
        accountant.spend(0.5, 1e-5)  # ε=0.5 per round
        
        if round_num % 5 == 0:
            summary = accountant.summary()
            print(f"Round {round_num}:")
            print(f"  ε spent: {summary['epsilon_spent']:.2f}/{summary['epsilon_budget']}")
            print(f"  ε remaining: {summary['epsilon_remaining']:.2f}")
            print(f"  Can continue: {accountant.can_continue()}")
    
    print("\n✓ Differential Privacy tests complete!\n")


if __name__ == "__main__":
    test_differential_privacy()
