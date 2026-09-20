"""
Deep Neural Network-Based Feature Selection

Uses attention mechanisms and learnable gates to automatically
select important features during training.

Two approaches:
1. Attention-based: Learn attention weights for each feature
2. Concrete Selector: Learnable binary gates with gradient estimation
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


class AttentionFeatureSelector(nn.Module):
    """Feature selector using attention mechanism"""
    
    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        hidden_dim: int = 128,
        attention_dim: int = 64
    ):
        """
        Initialize attention-based feature selector
        
        Args:
            input_dim: Number of input features
            num_classes: Number of output classes
            hidden_dim: Hidden layer dimension
            attention_dim: Attention mechanism dimension
        """
        super(AttentionFeatureSelector, self).__init__()
        
        self.input_dim = input_dim
        
        # Attention mechanism (per-feature)
        self.attention = nn.Sequential(
            nn.Linear(input_dim, attention_dim),
            nn.Tanh(),
            nn.Linear(attention_dim, input_dim),
            nn.Sigmoid()  # Attention weights in [0, 1]
        )
        
        # Classification network
        self.classifier = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim // 2, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with attention
        
        Args:
            x: Input features (batch_size, input_dim)
            
        Returns:
            Tuple of (predictions, attention_weights)
        """
        # Compute attention weights
        attention_weights = self.attention(x)
        
        # Apply attention (element-wise multiplication)
        x_attended = x * attention_weights
        
        # Classify
        logits = self.classifier(x_attended)
        
        return logits, attention_weights
    
    def get_feature_importance(self) -> np.ndarray:
        """
        Get learned feature importance
        
        Returns:
            Feature importance scores
        """
        # Average attention weights across samples would be ideal,
        # but we can extract the attention layer weights as proxy
        with torch.no_grad():
            # Use identity input to get base attention
            identity = torch.eye(self.input_dim)
            _, attention = self.forward(identity)
            importance = attention.mean(dim=0).cpu().numpy()
        
        return importance


class ConcreteSelector(nn.Module):
    """
    Concrete Feature Selector with Gumbel-Softmax
    
    Learns binary feature selection masks using continuous relaxation.
    Based on "Learning to Select" paper.
    """
    
    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        hidden_dim: int = 128,
        temperature: float = 0.5
    ):
        """
        Initialize Concrete Selector
        
        Args:
            input_dim: Number of input features
            num_classes: Number of output classes
            hidden_dim: Hidden layer dimension
            temperature: Gumbel-Softmax temperature
        """
        super(ConcreteSelector, self).__init__()
        
        self.input_dim = input_dim
        self.temperature = temperature
        
        # Learnable selection logits (one per feature)
        self.selection_logits = nn.Parameter(torch.zeros(input_dim))
        
        # Classification network
        self.classifier = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim // 2, num_classes)
        )
    
    def sample_gumbel(self, shape: tuple) -> torch.Tensor:
        """Sample from Gumbel(0, 1)"""
        u = torch.rand(shape)
        return -torch.log(-torch.log(u + 1e-20) + 1e-20)
    
    def gumbel_softmax_sample(self, logits: torch.Tensor) -> torch.Tensor:
        """Sample from Gumbel-Softmax distribution"""
        gumbel_noise = self.sample_gumbel(logits.shape).to(logits.device)
        y = logits + gumbel_noise
        return torch.sigmoid(y / self.temperature)
    
    def forward(self, x: torch.Tensor, hard: bool = False) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with feature selection
        
        Args:
            x: Input features (batch_size, input_dim)
            hard: If True, use hard thresholding (inference mode)
            
        Returns:
            Tuple of (predictions, selection_mask)
        """
        if self.training and not hard:
            # Soft selection during training
            selection_mask = self.gumbel_softmax_sample(self.selection_logits)
        else:
            # Hard selection during inference
            selection_mask = (torch.sigmoid(self.selection_logits) > 0.5).float()
        
        # Broadcast mask to batch
        mask = selection_mask.unsqueeze(0).expand(x.size(0), -1)
        
        # Apply mask
        x_selected = x * mask
        
        # Classify
        logits = self.classifier(x_selected)
        
        return logits, selection_mask
    
    def get_selected_features(self, threshold: float = 0.5) -> List[int]:
        """
        Get indices of selected features
        
        Args:
            threshold: Selection threshold
            
        Returns:
            List of selected feature indices
        """
        with torch.no_grad():
            probs = torch.sigmoid(self.selection_logits)
            selected = (probs > threshold).cpu().numpy()
            return np.where(selected)[0].tolist()


class DNNFeatureSelector:
    """Wrapper for DNN-based feature selection"""
    
    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        method: str = 'attention',
        hidden_dim: int = 128,
        learning_rate: float = 0.001,
        l1_lambda: float = 0.001
    ):
        """
        Initialize DNN feature selector
        
        Args:
            input_dim: Number of input features
            num_classes: Number of output classes
            method: 'attention' or 'concrete'
            hidden_dim: Hidden layer dimension
            learning_rate: Learning rate
            l1_lambda: L1 regularization weight (for sparsity)
        """
        self.input_dim = input_dim
        self.num_classes = num_classes
        self.method = method
        self.l1_lambda = l1_lambda
        
        # Create model
        if method == 'attention':
            self.model = AttentionFeatureSelector(input_dim, num_classes, hidden_dim)
        elif method == 'concrete':
            self.model = ConcreteSelector(input_dim, num_classes, hidden_dim)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.CrossEntropyLoss()
        
        # Move to GPU if available
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = self.model.to(self.device)
        
        logger.info(f"Initialized DNN Feature Selector ({method}) on {self.device}")
    
    def train_epoch(
        self,
        X: np.ndarray,
        y: np.ndarray,
        batch_size: int = 64
    ) -> Tuple[float, float]:
        """
        Train for one epoch
        
        Args:
            X: Features
            y: Labels
            batch_size: Batch size
            
        Returns:
            Tuple of (loss, accuracy)
        """
        self.model.train()
        
        # Shuffle data
        indices = np.random.permutation(len(X))
        X, y = X[indices], y[indices]
        
        total_loss = 0
        correct = 0
        total = 0
        
        for i in range(0, len(X), batch_size):
            batch_X = torch.FloatTensor(X[i:i+batch_size]).to(self.device)
            batch_y = torch.LongTensor(y[i:i+batch_size]).to(self.device)
            
            # Forward pass
            logits, mask = self.model(batch_X)
            
            # Classification loss
            loss = self.criterion(logits, batch_y)
            
            # L1 regularization for sparsity (encourage feature selection)
            if self.method == 'attention':
                l1_reg = self.l1_lambda * torch.mean(mask)
            elif self.method == 'concrete':
                l1_reg = self.l1_lambda * torch.sum(torch.sigmoid(self.model.selection_logits))
            
            total_loss_batch = loss + l1_reg
            
            # Backward pass
            self.optimizer.zero_grad()
            total_loss_batch.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            
            # Accuracy
            _, predicted = torch.max(logits, 1)
            total += batch_y.size(0)
            correct += (predicted == batch_y).sum().item()
        
        avg_loss = total_loss / (len(X) / batch_size)
        accuracy = correct / total
        
        return avg_loss, accuracy
    
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """Evaluate model"""
        self.model.eval()
        
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            y_tensor = torch.LongTensor(y).to(self.device)
            
            # Call forward with hard=True only for concrete method
            if self.method == 'concrete':
                logits, _ = self.model(X_tensor, hard=True)
            else:
                logits, _ = self.model(X_tensor)
            
            loss = self.criterion(logits, y_tensor).item()
            
            _, predicted = torch.max(logits, 1)
            accuracy = (predicted == y_tensor).float().mean().item()
        
        return loss, accuracy

    
    def get_selected_features(
        self,
        X_sample: Optional[np.ndarray] = None,
        top_k: Optional[int] = None,
        threshold: float = 0.5
    ) -> List[int]:
        """
        Get selected feature indices
        
        Args:
            X_sample: Sample data to compute importance (for attention method)
            top_k: Number of top features to select (alternative to threshold)
            threshold: Selection threshold
            
        Returns:
            List of selected feature indices
        """
        self.model.eval()
        
        if self.method == 'concrete':
            # Concrete selector has explicit selection
            return self.model.get_selected_features(threshold)
        
        elif self.method == 'attention':
            # Attention-based: use average attention weights
            if X_sample is None:
                # Use feature importance from model
                importance = self.model.get_feature_importance()
            else:
                # Compute on sample
                with torch.no_grad():
                    X_tensor = torch.FloatTensor(X_sample).to(self.device)
                    _, attention = self.model(X_tensor)
                    importance = attention.mean(dim=0).cpu().numpy()
            
            if top_k:
                # Select top k by importance
                return np.argsort(importance)[-top_k:][::-1].tolist()
            else:
                # Threshold-based selection
                return np.where(importance > threshold)[0].tolist()


def train_dnn_feature_selector(
    X: np.ndarray,
    y: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    method: str = 'concrete',
    num_epochs: int = 30,
    top_k: Optional[int] = 40
) -> Tuple[List[int], DNNFeatureSelector]:
    """
    Train DNN-based feature selector
    
    Args:
        X: Training features
        y: Training labels
        X_val: Validation features
        y_val: Validation labels
        method: 'attention' or 'concrete'
        num_epochs: Number of training epochs
        top_k: Number of features to select
        
    Returns:
        Tuple of (selected feature indices, trained selector)
    """
    logger.info("="*70)
    logger.info(f"DNN-Based Feature Selection ({method.upper()})")
    logger.info("="*70)
    
    # Initialize selector
    selector = DNNFeatureSelector(
        input_dim=X.shape[1],
        num_classes=len(np.unique(y)),
        method=method,
        hidden_dim=256,
        learning_rate=0.001,
        l1_lambda=0.01  # Encourage sparsity
    )
    
    # Training loop
    logger.info(f"Training for {num_epochs} epochs...")
    
    best_val_acc = 0
    
    for epoch in range(num_epochs):
        train_loss, train_acc = selector.train_epoch(X, y)
        val_loss, val_acc = selector.evaluate(X_val, y_val)
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
        
        if epoch % 5 == 0:
            logger.info(
                f"Epoch {epoch}/{num_epochs} | "
                f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}"
            )
    
    # Get selected features
    if method == 'concrete':
        selected_indices = selector.get_selected_features(threshold=0.5)
    else:
        selected_indices = selector.get_selected_features(X_val, top_k=top_k)
    
    logger.info(f"\nSelected {len(selected_indices)} features")
    logger.info(f"Best validation accuracy: {best_val_acc:.4f}")
    
    return selected_indices, selector
