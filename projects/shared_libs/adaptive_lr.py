"""
Phase 7: Adaptive Learning Rate Module

Dynamically adjusts learning rates based on training performance.
Implements per-node LR customization and convergence detection.
"""

import numpy as np
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdaptiveLearningRate:
    """
    Adaptive LR scheduler for Federated Learning
    
    Features:
    - Performance-based LR adjustment
    - Per-node customization
    - Plateau detection
    - Warmup + decay schedules
    """
    
    def __init__(
        self,
        initial_lr: float = 0.01,
        min_lr: float = 0.0001,
        max_lr: float = 0.1,
        patience: int = 3,
        reduction_factor: float = 0.5
    ):
        self.initial_lr = initial_lr
        self.min_lr = min_lr
        self.max_lr = max_lr
        self.patience = patience
        self.reduction_factor = reduction_factor
        
        # Track performance history
        self.performance_history = []
        self.no_improvement_count = 0
        self.best_performance = 0.0
        
        # Per-node LRs
        self.node_lrs = {}
        
        logger.info(f"Adaptive LR initialized: {initial_lr} → [{min_lr}, {max_lr}]")
    
    def get_lr(self, node_id: str = 'global') -> float:
        """Get current LR for a node"""
        if node_id not in self.node_lrs:
            self.node_lrs[node_id] = self.initial_lr
        return self.node_lrs[node_id]
    
    def update(self, performance: float, node_id: str = 'global'):
        """
        Update LR based on performance
        
        Args:
            performance: Current performance metric (accuracy)
            node_id: Node identifier
        """
        current_lr = self.get_lr(node_id)
        
        # Check for improvement
        if performance > self.best_performance:
            self.best_performance = performance
            self.no_improvement_count = 0
            logger.info(f"✓ Performance improved: {performance:.4f}")
        else:
            self.no_improvement_count += 1
            
            # Reduce LR if plateau detected
            if self.no_improvement_count >= self.patience:
                new_lr = max(self.min_lr, current_lr * self.reduction_factor)
                self.node_lrs[node_id] = new_lr
                self.no_improvement_count = 0
                logger.info(f"📉 Plateau detected - reducing LR: {current_lr:.6f} → {new_lr:.6f}")
        
        self.performance_history.append(performance)
    
    def warmup_schedule(self, current_round: int, warmup_rounds: int = 5) -> float:
        """Warmup schedule: gradually increase LR"""
        if current_round < warmup_rounds:
            factor = current_round / warmup_rounds
            return self.initial_lr * factor
        return self.initial_lr
    
    def cosine_annealing(self, current_round: int, total_rounds: int) -> float:
        """Cosine annealing schedule"""
        progress = current_round / total_rounds
        lr = self.min_lr + (self.initial_lr - self.min_lr) * 0.5 * (1 + np.cos(np.pi * progress))
        return lr


def test_adaptive_lr():
    """Test adaptive LR"""
    print("="*70)
    print("TESTING ADAPTIVE LEARNING RATE")
    print("="*70)
    
    alr = AdaptiveLearningRate(initial_lr=0.01, patience=2)
    
    # Simulate training
    accuracies = [0.5, 0.7, 0.85, 0.87, 0.87, 0.87, 0.90, 0.92]
    
    for round_num, acc in enumerate(accuracies, 1):
        print(f"\nRound {round_num}:")
        print(f"  Accuracy: {acc:.4f}")
        print(f"  LR before: {alr.get_lr():.6f}")
        
        alr.update(acc)
        
        print(f"  LR after: {alr.get_lr():.6f}")
    
    print(f"\n✓ Adaptive LR test complete!")
    print(f"  Final LR: {alr.get_lr():.6f}")
    print(f"  Best performance: {alr.best_performance:.4f}")


if __name__ == "__main__":
    test_adaptive_lr()
