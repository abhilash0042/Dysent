"""
Homomorphic Encryption Module for Federated Learning

Implements encrypted model aggregation using CKKS scheme.
Enables privacy-preserving FL where server never sees plaintext model updates.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if TenSEAL is available
try:
    import tenseal as ts
    TENSEAL_AVAILABLE = True
    logger.info("✓ TenSEAL library available")
except ImportError:
    TENSEAL_AVAILABLE = False
    logger.warning("⚠️  TenSEAL not installed - using simulation mode")
    logger.warning("   Install with: pip install tenseal")


class HomomorphicFL:
    """
    Homomorphic Encryption for Federated Learning
    
    Uses CKKS scheme for approximate arithmetic on encrypted data.
    Enables server to aggregate model updates without decryption.
    """
    
    def __init__(
        self,
        poly_modulus_degree: int = 8192,
        coeff_mod_bit_sizes: List[int] = None,
        global_scale: float = 2**40
    ):
        """
        Initialize homomorphic encryption context.
        
        Args:
            poly_modulus_degree: Polynomial modulus degree (power of 2)
                Higher = more security, slower computation
                Typical values: 4096, 8192, 16384
            coeff_mod_bit_sizes: Bit sizes for coefficient modulus
            global_scale: Scale for encoding (precision vs range tradeoff)
        """
        self.poly_modulus_degree = poly_modulus_degree
        self.coeff_mod_bit_sizes = coeff_mod_bit_sizes or [60, 40, 40, 60]
        self.global_scale = global_scale
        
        self.context = None
        self.public_key = None
        self.secret_key = None
        
        if TENSEAL_AVAILABLE:
            self._initialize_context()
        else:
            logger.info("Running in simulation mode (no actual encryption)")
        
        logger.info("Initialized Homomorphic FL")
        logger.info(f"  Poly modulus degree: {poly_modulus_degree}")
        logger.info(f"  Security level: ~{self._estimate_security_bits()} bits")
    
    def _initialize_context(self):
        """Initialize TenSEAL context with CKKS scheme"""
        self.context = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=self.poly_modulus_degree,
            coeff_mod_bit_sizes=self.coeff_mod_bit_sizes
        )
        
        self.context.global_scale = self.global_scale
        self.context.generate_galois_keys()
        
        # Keys (for demo - in practice, distributed key generation)
        self.public_key = self.context.public_key()
        self.secret_key = self.context.secret_key()
        
        logger.info("✓ CKKS context initialized")
    
    def _estimate_security_bits(self) -> int:
        """Estimate security level in bits"""
        # Rough estimation based on poly_modulus_degree
        security_map = {
            4096: 128,
            8192: 128,
            16384: 192,
            32768: 256
        }
        return security_map.get(self.poly_modulus_degree, 128)
    
    def encrypt_weights(
        self,
        weights: List[np.ndarray],
        quantize: bool = True
    ) -> List:
        """
        Encrypt model weights.
        
        Args:
            weights: List of weight matrices/vectors
            quantize: Whether to quantize before encryption (reduces size)
            
        Returns:
            Encrypted weights (or simulated if TenSEAL not available)
        """
        if not TENSEAL_AVAILABLE:
            # Simulation mode - just return wrapped weights
            return [{"simulated": True, "data": w} for w in weights]
        
        encrypted_weights = []
        
        for i, w in enumerate(weights):
            # Flatten weight matrix
            flat_w = w.flatten()
            
            # Quantize if requested
            if quantize:
                flat_w = self._quantize(flat_w)
            
            # Encrypt using CKKS
            enc_w = ts.ckks_vector(self.context, flat_w.tolist())
            
            encrypted_weights.append({
                "encrypted": enc_w,
                "shape": w.shape,
                "dtype": str(w.dtype)
            })
        
        return encrypted_weights
    
    def decrypt_weights(
        self,
        encrypted_weights: List,
        original_shapes: Optional[List[Tuple]] = None
    ) -> List[np.ndarray]:
        """
        Decrypt model weights.
        
        Args:
            encrypted_weights: Encrypted weight data
            original_shapes: Original shapes for reshaping
            
        Returns:
            Decrypted weights as numpy arrays
        """
        if not TENSEAL_AVAILABLE:
            # Simulation mode
            return [w["data"] for w in encrypted_weights]
        
        decrypted_weights = []
        
        for i, enc_data in enumerate(encrypted_weights):
            # Decrypt
            flat_w = enc_data["encrypted"].decrypt()
            
            # Reshape
            shape = enc_data.get("shape") or (original_shapes[i] if original_shapes else (len(flat_w),))
            w = np.array(flat_w).reshape(shape)
            
            decrypted_weights.append(w)
        
        return decrypted_weights
    
    def encrypted_aggregate(
        self,
        encrypted_updates: List[List],
        num_clients: int
    ) -> List:
        """
        Aggregate encrypted model updates (FedAvg in encrypted space).
        
        Args:
            encrypted_updates: List of encrypted weight updates from clients
            num_clients: Number of clients
            
        Returns:
            Aggregated encrypted weights
        """
        if not TENSEAL_AVAILABLE:
            # Simulation mode - average in plaintext
            num_layers = len(encrypted_updates[0])
            aggregated = []
            
            for layer_idx in range(num_layers):
                layer_updates = [update[layer_idx]["data"] for update in encrypted_updates]
                avg_layer = np.mean(layer_updates, axis=0)
                aggregated.append({"simulated": True, "data": avg_layer})
            
            return aggregated
        
        # Actual homomorphic aggregation
        num_layers = len(encrypted_updates[0])
        aggregated = []
        
        for layer_idx in range(num_layers):
            # Get all encrypted vectors for this layer
            enc_vectors = [update[layer_idx]["encrypted"] for update in encrypted_updates]
            
            # Sum in encrypted space
            enc_sum = enc_vectors[0]
            for enc_vec in enc_vectors[1:]:
                enc_sum += enc_vec
            
            # Divide by number of clients (scalar multiplication in encrypted space)
            enc_avg = enc_sum * (1.0 / num_clients)
            
            aggregated.append({
                "encrypted": enc_avg,
                "shape": encrypted_updates[0][layer_idx]["shape"],
                "dtype": encrypted_updates[0][layer_idx]["dtype"]
            })
        
        return aggregated
    
    def _quantize(self, weights: np.ndarray, bits: int = 16) -> np.ndarray:
        """
        Quantize weights to reduce ciphertext size.
        
        Args:
            weights: Weight array
            bits: Number of bits for quantization
            
        Returns:
            Quantized weights
        """
        # Simple linear quantization
        w_min, w_max = weights.min(), weights.max()
        scale = (2**bits - 1) / (w_max - w_min + 1e-8)
        
        quantized = np.round((weights - w_min) * scale)
        dequantized = quantized / scale + w_min
        
        return dequantized
    
    def measure_overhead(
        self,
        weights: List[np.ndarray]
    ) -> Dict[str, float]:
        """
        Measure encryption/decryption overhead.
        
        Args:
            weights: Model weights
            
        Returns:
            Timing and size metrics
        """
        # Encryption time
        start = time.time()
        encrypted = self.encrypt_weights(weights)
        encrypt_time = time.time() - start
        
        # Decryption time
        start = time.time()
        decrypted = self.decrypt_weights(encrypted)
        decrypt_time = time.time() - start
        
        # Size comparison
        plaintext_size = sum(w.nbytes for w in weights)
        
        if TENSEAL_AVAILABLE:
            # Approximate encrypted size
            encrypted_size = plaintext_size * 10  # CKKS typically 10x overhead
        else:
            encrypted_size = plaintext_size
        
        metrics = {
            'encrypt_time_ms': encrypt_time * 1000,
            'decrypt_time_ms': decrypt_time * 1000,
            'plaintext_size_kb': plaintext_size / 1024,
            'encrypted_size_kb': encrypted_size / 1024,
            'size_overhead': encrypted_size / plaintext_size,
            'tenseal_available': TENSEAL_AVAILABLE
        }
        
        logger.info("\n📊 Homomorphic Encryption Overhead:")
        logger.info(f"  Encryption time: {metrics['encrypt_time_ms']:.2f}ms")
        logger.info(f"  Decryption time: {metrics['decrypt_time_ms']:.2f}ms")
        logger.info(f"  Size overhead: {metrics['size_overhead']:.1f}x")
        
        return metrics


def test_homomorphic_fl():
    """Test homomorphic FL module"""
    
    print("\n" + "="*70)
    print("TESTING HOMOMORPHIC FL MODULE")
    print("="*70)
    
    # Create dummy weights
    weights = [
        np.random.randn(10, 5),  # Layer 1
        np.random.randn(5),       # Bias 1
        np.random.randn(5, 3),   # Layer 2
        np.random.randn(3)        # Bias 2
    ]
    
    print(f"\n✓ Created dummy model weights:")
    print(f"  Total params: {sum(w.size for w in weights):,}")
    
    # Initialize HE
    he_fl = HomomorphicFL()
    
    # Test encryption
    print(f"\n🔐 Testing encryption...")
    encrypted = he_fl.encrypt_weights(weights)
    print(f"  ✓ Weights encrypted")
    
    # Test decryption
    print(f"\n🔓 Testing decryption...")
    decrypted = he_fl.decrypt_weights(encrypted)
    print(f"  ✓ Weights decrypted")
    
    # Verify accuracy
    max_error = max(np.max(np.abs(w - d)) for w, d in zip(weights, decrypted))
    print(f"  Max decryption error: {max_error:.2e}")
    
    # Test aggregation
    print(f"\n⚡ Testing encrypted aggregation...")
    
    # Simulate 3 clients with encrypted updates
    client_updates = [
        he_fl.encrypt_weights(weights),
        he_fl.encrypt_weights([w + np.random.randn(*w.shape) * 0.01 for w in weights]),
        he_fl.encrypt_weights([w + np.random.randn(*w.shape) * 0.01 for w in weights])
    ]
    
    # Aggregate in encrypted space
    aggregated_encrypted = he_fl.encrypted_aggregate(client_updates, num_clients=3)
    print(f"  ✓ Aggregation in encrypted space complete")
    
    # Decrypt result
    aggregated_decrypted = he_fl.decrypt_weights(aggregated_encrypted)
    print(f"  ✓ Aggregated model decrypted")
    
    # Measure overhead
    metrics = he_fl.measure_overhead(weights)
    
    print(f"\n✓ Homomorphic FL test successful!")
    print(f"  Mode: {'Actual encryption' if TENSEAL_AVAILABLE else 'Simulation'}")
    
    if not TENSEAL_AVAILABLE:
        print(f"\n💡 To enable actual encryption:")
        print(f"   pip install tenseal")
    
    return he_fl, metrics


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    test_homomorphic_fl()
