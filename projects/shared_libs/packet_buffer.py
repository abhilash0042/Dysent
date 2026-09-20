"""
Sliding Window Packet Buffer
Manages temporal sequences of packets for model input
Converts stream of individual packets into fixed-size windows
"""

import logging
from typing import List, Optional
import numpy as np
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SlidingWindowBuffer:
    """
    Maintains sliding window of packet features for temporal models
    
    Accumulates individual packet features into sequences
    Required for CNN-BiLSTM and Transformer models that expect (timesteps, features)
    """
    
    def __init__(
        self,
        window_size: int = 10,
        feature_dim: int = 40,
        stride: int = 1,
        fill_mode: str = 'zeros'
    ):
        """
        Initialize sliding window buffer
        
        Args:
            window_size: Number of timesteps (packets) per window
            feature_dim: Number of features per packet
            stride: How many packets to slide window (1 = overlapping)
            fill_mode: How to fill incomplete windows ('zeros', 'repeat', 'skip')
        """
        self.window_size = window_size
        self.feature_dim = feature_dim
        self.stride = stride
        self.fill_mode = fill_mode
        
        # Buffer for accumulating packets
        self.buffer = deque(maxlen=window_size)
        
        # Statistics
        self.packets_added = 0
        self.windows_generated = 0
        
        logger.info(f"SlidingWindowBuffer initialized")
        logger.info(f"  Window size: {window_size} timesteps")
        logger.info(f"  Feature dim: {feature_dim}")
        logger.info(f"  Stride: {stride}")
        logger.info(f"  Fill mode: {fill_mode}")
    
    def add_packet(self, features: np.ndarray):
        """
        Add packet features to buffer
        
        Args:
            features: Feature vector (feature_dim,)
        """
        if features.shape[0] != self.feature_dim:
            raise ValueError(
                f"Feature dimension mismatch: expected {self.feature_dim}, got {features.shape[0]}"
            )
        
        self.buffer.append(features)
        self.packets_added += 1
    
    def is_full(self) -> bool:
        """Check if buffer has enough packets for a window"""
        return len(self.buffer) >= self.window_size
    
    def can_generate_window(self) -> bool:
        """Check if we can generate a valid window"""
        if self.fill_mode == 'skip':
            return len(self.buffer) >= self.window_size
        else:
            return len(self.buffer) > 0
    
    def get_window(self, remove_from_buffer: bool = False) -> Optional[np.ndarray]:
        """
        Get current window as array
        
        Args:
            remove_from_buffer: If True, slide window by stride amount
            
        Returns:
            Window array (window_size, feature_dim) or None if can't generate
        """
        if not self.can_generate_window():
            return None
        
        buffer_size = len(self.buffer)
        
        if buffer_size >= self.window_size:
            # Full window available
            window = np.array(list(self.buffer)[-self.window_size:])
            
        else:
            # Partial window - need filling
            if self.fill_mode == 'skip':
                return None
            
            elif self.fill_mode == 'zeros':
                # Pad with zeros
                window = np.zeros((self.window_size, self.feature_dim), dtype=np.float32)
                window[-buffer_size:] = np.array(list(self.buffer))
            
            elif self.fill_mode == 'repeat':
                # Repeat last packet
                packets = list(self.buffer)
                window = np.array([
                    packets[min(i, buffer_size-1)] for i in range(self.window_size)
                ])
            
            else:
                raise ValueError(f"Unknown fill_mode: {self.fill_mode}")
        
        # Optionally slide window
        if remove_from_buffer:
            for _ in range(min(self.stride, len(self.buffer))):
                self.buffer.popleft()
        
        self.windows_generated += 1
        return window
    
    def get_batch(self, batch_size: int = 32) -> Optional[np.ndarray]:
        """
        Generate batch of windows
        
        Args:
            batch_size: Number of windows to generate
            
        Returns:
            Batch array (batch_size, window_size, feature_dim) or None
        """
        windows = []
        
        for _ in range(batch_size):
            window = self.get_window(remove_from_buffer=True)
            if window is None:
                break
            windows.append(window)
        
        if len(windows) == 0:
            return None
        
        return np.array(windows)
    
    def reset(self):
        """Clear buffer and reset statistics"""
        self.buffer.clear()
        self.packets_added = 0
        self.windows_generated = 0
    
    def get_statistics(self) -> dict:
        """Get buffer statistics"""
        return {
            'packets_added': self.packets_added,
            'windows_generated': self.windows_generated,
            'current_buffer_size': len(self.buffer),
            'is_full': self.is_full()
        }


class StreamToModelAdapter:
    """
    Combines StreamProcessor and SlidingWindowBuffer
    Provides single interface for packet stream → model input
    """
    
    def __init__(
        self,
        stream_processor,
        window_size: int = 10,
        feature_dim: int = 40
    ):
        """
        Initialize adapter
        
        Args:
            stream_processor: Instance of PacketStreamProcessor
            window_size: Window size for buffer
            feature_dim: Feature dimension
        """
        self.stream_processor = stream_processor
        self.buffer = SlidingWindowBuffer(
            window_size=window_size,
            feature_dim=feature_dim,
            stride=1,  # Overlapping windows
            fill_mode='zeros'
        )
        
        logger.info("StreamToModelAdapter initialized")
    
    def stream_windows(self):
        """
        Stream model-ready windows from live packets
        
        Yields:
            Window arrays (1, window_size, feature_dim) ready for model.predict()
        """
        for features in self.stream_processor.stream_features():
            self.buffer.add_packet(features)
            
            if self.buffer.is_full():
                window = self.buffer.get_window(remove_from_buffer=False)
                if window is not None:
                    # Add batch dimension for model
                    yield np.expand_dims(window, axis=0)
    
    def stream_batches(self, batch_size: int = 32):
        """
        Stream batches of windows
        
        Args:
            batch_size: Number of windows per batch
            
        Yields:
            Batch arrays (batch_size, window_size, feature_dim)
        """
        for features in self.stream_processor.stream_features():
            self.buffer.add_packet(features)
            
            if self.buffer.is_full():
                batch = self.buffer.get_batch(batch_size)
                if batch is not None:
                    yield batch
    
    def get_statistics(self) -> dict:
        """Get combined statistics"""
        return {
            'stream': self.stream_processor.get_statistics(),
            'buffer': self.buffer.get_statistics()
        }


def test_sliding_window():
    """Test sliding window buffer"""
    logger.info("\n" + "="*70)
    logger.info("Testing Sliding Window Buffer")
    logger.info("="*70 + "\n")
    
    # Create buffer
    buffer = SlidingWindowBuffer(
        window_size=10,
        feature_dim=40,
        stride=1,
        fill_mode='zeros'
    )
    
    # Simulate adding packets
    logger.info("Adding 15 packets...")
    for i in range(15):
        features = np.random.randn(40).astype(np.float32)
        buffer.add_packet(features)
        
        if buffer.is_full():
            window = buffer.get_window(remove_from_buffer=False)
            logger.info(f"  Packet {i+1}: Window shape {window.shape}")
    
    # Get statistics
    stats = buffer.get_statistics()
    logger.info(f"\n✓ Statistics:")
    logger.info(f"  Packets added: {stats['packets_added']}")
    logger.info(f"  Windows generated: {stats['windows_generated']}")
    logger.info(f"  Buffer size: {stats['current_buffer_size']}")
    logger.info(f"  Is full: {stats['is_full']}")
    
    logger.info("\n✅ Sliding window buffer working!")


if __name__ == "__main__":
    test_sliding_window()
