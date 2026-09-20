"""
Data Processing Module for DDoS Detection System

Handles loading, preprocessing, and partitioning of CICDDoS2019 and NSLKDD datasets
for federated learning across multiple nodes.
"""

import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Load and cache DDoS/IDS datasets"""
    
    SUPPORTED_DATASETS = ['cicddos2019', 'nslkdd']
    
    def __init__(self, dataset_path: str):
        """
        Initialize dataset loader
        
        Args:
            dataset_path: Base path to datasets directory
        """
        self.dataset_path = Path(dataset_path)
        self.cache = {}
        
    def load_cicddos2019(self) -> pd.DataFrame:
        """Load CICDDoS2019 dataset"""
        logger.info("Loading CICDDoS2019 dataset...")
        
        # CICDDoS2019 typically contains multiple CSV files
        csv_files = list(self.dataset_path.glob("**/CIC*.csv"))
        
        if not csv_files:
            raise FileNotFoundError(
                f"No CICDDoS2019 CSV files found in {self.dataset_path}"
            )
        
        logger.info(f"Found {len(csv_files)} CSV files")
        
        # Load and concatenate all CSV files
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, encoding='utf-8', low_memory=False)
                dfs.append(df)
                logger.info(f"Loaded {csv_file.name}: {len(df)} records")
            except Exception as e:
                logger.warning(f"Failed to load {csv_file.name}: {e}")
        
        if not dfs:
            raise ValueError("No valid CSV files could be loaded")
        
        # Concatenate all dataframes
        df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Total records: {len(df)}")
        
        return df
    
    def load_nslkdd(self) -> pd.DataFrame:
        """Load NSLKDD dataset"""
        logger.info("Loading NSLKDD dataset...")
        
        # NSLKDD typically has KDDTrain+.txt and KDDTest+.txt
        train_files = list(self.dataset_path.glob("**/KDDTrain*.txt")) + \
                      list(self.dataset_path.glob("**/KDDTrain*.csv"))
        test_files = list(self.dataset_path.glob("**/KDDTest*.txt")) + \
                     list(self.dataset_path.glob("**/KDDTest*.csv"))
        
        # NSLKDD column names (standard 41 features + label)
        column_names = [
            'duration', 'protocol_type', 'service', 'flag', 'src_bytes',
            'dst_bytes', 'land', 'wrong_fragment', 'urgent', 'hot',
            'num_failed_logins', 'logged_in', 'num_compromised', 'root_shell',
            'su_attempted', 'num_root', 'num_file_creations', 'num_shells',
            'num_access_files', 'num_outbound_cmds', 'is_host_login',
            'is_guest_login', 'count', 'srv_count', 'serror_rate',
            'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate', 'same_srv_rate',
            'diff_srv_rate', 'srv_diff_host_rate', 'dst_host_count',
            'dst_host_srv_count', 'dst_host_same_srv_rate',
            'dst_host_diff_srv_rate', 'dst_host_same_src_port_rate',
            'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
            'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
            'dst_host_srv_rerror_rate', 'label', 'difficulty_level'
        ]
        
        dfs = []
        
        # Load training files
        for file in train_files:
            try:
                if file.suffix == '.csv':
                    df = pd.read_csv(file)
                else:
                    df = pd.read_csv(file, header=None, names=column_names)
                dfs.append(df)
                logger.info(f"Loaded {file.name}: {len(df)} records")
            except Exception as e:
                logger.warning(f"Failed to load {file.name}: {e}")
        
        # Load test files
        for file in test_files:
            try:
                if file.suffix == '.csv':
                    df = pd.read_csv(file)
                else:
                    df = pd.read_csv(file, header=None, names=column_names)
                dfs.append(df)
                logger.info(f"Loaded {file.name}: {len(df)} records")
            except Exception as e:
                logger.warning(f"Failed to load {file.name}: {e}")
        
        if not dfs:
            raise FileNotFoundError(
                f"No NSLKDD files found in {self.dataset_path}"
            )
        
        df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Total records: {len(df)}")
        
        return df
    
    def load_dataset(self, dataset_name: str) -> pd.DataFrame:
        """
        Load specified dataset
        
        Args:
            dataset_name: Name of dataset ('cicddos2019' or 'nslkdd')
            
        Returns:
            Loaded DataFrame
        """
        dataset_name = dataset_name.lower()
        
        if dataset_name not in self.SUPPORTED_DATASETS:
            raise ValueError(
                f"Unsupported dataset: {dataset_name}. "
                f"Supported: {self.SUPPORTED_DATASETS}"
            )
        
        # Check cache
        if dataset_name in self.cache:
            logger.info(f"Loading {dataset_name} from cache")
            return self.cache[dataset_name]
        
        # Load dataset
        if dataset_name == 'cicddos2019':
            df = self.load_cicddos2019()
        elif dataset_name == 'nslkdd':
            df = self.load_nslkdd()
        
        # Cache it
        self.cache[dataset_name] = df
        
        return df


class FeatureExtractor:
    """Extract and engineer features for DDoS detection"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.categorical_encoders = {}
        self.feature_names = []
        
    def _identify_label_column(self, df: pd.DataFrame) -> str:
        """Identify the label column from common names"""
        possible_labels = ['label', 'Label', 'class', 'Class', 'attack', 'Attack']
        
        for col in possible_labels:
            if col in df.columns:
                return col
        
        # If not found, assume last column is label
        logger.warning("Label column not found, using last column")
        return df.columns[-1]
    
    def preprocess(self, df: pd.DataFrame, fit: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess dataset: handle missing values, encode categoricals, normalize
        
        Args:
            df: Input DataFrame
            fit: Whether to fit encoders/scalers (True for training data)
            
        Returns:
            Tuple of (features, labels)
        """
        logger.info(f"Preprocessing dataset with {len(df)} records...")
        
        # Make a copy
        df = df.copy()
        
        # Identify label column
        label_col = self._identify_label_column(df)
        logger.info(f"Using '{label_col}' as label column")
        
        # Separate features and labels
        y = df[label_col].values
        X = df.drop(columns=[label_col])
        
        # Drop difficulty_level if exists (NSLKDD specific)
        if 'difficulty_level' in X.columns:
            X = X.drop(columns=['difficulty_level'])
        
        # Handle infinity and missing values
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0)
        
        # Identify numeric and categorical columns
        numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = X.select_dtypes(include=['object']).columns.tolist()
        
        logger.info(f"Numeric features: {len(numeric_cols)}")
        logger.info(f"Categorical features: {len(categorical_cols)}")
        
        # Encode categorical features
        for col in categorical_cols:
            if fit:
                # Create and fit encoder
                encoder = LabelEncoder()
                X[col] = encoder.fit_transform(X[col].astype(str))
                self.categorical_encoders[col] = encoder
            else:
                # Use existing encoder
                if col in self.categorical_encoders:
                    # Handle unseen categories
                    encoder = self.categorical_encoders[col]
                    X[col] = X[col].astype(str).apply(
                        lambda x: encoder.transform([x])[0] 
                        if x in encoder.classes_ else -1
                    )
                else:
                    logger.warning(f"No encoder for {col}, setting to 0")
                    X[col] = 0
        
        # Convert to numpy array
        X = X.values.astype(np.float32)
        
        # Normalize features
        if fit:
            X = self.scaler.fit_transform(X)
            self.feature_names = list(df.drop(columns=[label_col]).columns)
        else:
            X = self.scaler.transform(X)
        
        # Encode labels
        if fit:
            y = self.label_encoder.fit_transform(y)
        else:
            # Handle unseen labels
            y = np.array([
                self.label_encoder.transform([label])[0] 
                if label in self.label_encoder.classes_ else -1
                for label in y
            ])
        
        logger.info(f"Processed features shape: {X.shape}")
        logger.info(f"Number of classes: {len(np.unique(y))}")
        
        return X, y
    
    def save(self, filepath: str):
        """Save encoders and scaler"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'scaler': self.scaler,
                'label_encoder': self.label_encoder,
                'categorical_encoders': self.categorical_encoders,
                'feature_names': self.feature_names
            }, f)
        logger.info(f"Saved feature extractor to {filepath}")
    
    def load(self, filepath: str):
        """Load encoders and scaler"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.scaler = data['scaler']
            self.label_encoder = data['label_encoder']
            self.categorical_encoders = data['categorical_encoders']
            self.feature_names = data['feature_names']
        logger.info(f"Loaded feature extractor from {filepath}")


class DataPartitioner:
    """Partition data for federated learning across nodes"""
    
    def __init__(self, num_nodes: int, iid: bool = True):
        """
        Initialize data partitioner
        
        Args:
            num_nodes: Number of FL nodes
            iid: Whether to create IID (True) or non-IID (False) partitions
        """
        self.num_nodes = num_nodes
        self.iid = iid
        
    def partition(self, X: np.ndarray, y: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Partition data across nodes
        
        Args:
            X: Features
            y: Labels
            
        Returns:
            List of (X_node, y_node) tuples for each node
        """
        logger.info(f"Partitioning data for {self.num_nodes} nodes (IID={self.iid})...")
        
        num_samples = len(X)
        indices = np.arange(num_samples)
        
        if self.iid:
            # IID: Random shuffle and split
            np.random.shuffle(indices)
            partitions = np.array_split(indices, self.num_nodes)
        else:
            # Non-IID: Sort by label and split
            # This creates heterogeneous data distributions
            sorted_indices = indices[np.argsort(y)]
            partitions = np.array_split(sorted_indices, self.num_nodes)
        
        # Create node datasets
        node_datasets = []
        for i, partition_indices in enumerate(partitions):
            X_node = X[partition_indices]
            y_node = y[partition_indices]
            node_datasets.append((X_node, y_node))
            
            logger.info(
                f"Node {i}: {len(X_node)} samples, "
                f"classes: {np.unique(y_node, return_counts=True)}"
            )
        
        return node_datasets


# Utility functions
def split_data(
    X: np.ndarray, 
    y: np.ndarray, 
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    stratify: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Split data into train/val/test sets
    
    Args:
        X: Features
        y: Labels
        train_ratio: Training set ratio
        val_ratio: Validation set ratio
        test_ratio: Test set ratio
        stratify: Whether to stratify by labels
        
    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6
    
    stratify_y = y if stratify else None
    
    # First split: train vs (val + test)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, 
        test_size=(val_ratio + test_ratio),
        stratify=stratify_y,
        random_state=42
    )
    
    # Second split: val vs test
    val_test_ratio = test_ratio / (val_ratio + test_ratio)
    stratify_temp = y_temp if stratify else None
    
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp,
        test_size=val_test_ratio,
        stratify=stratify_temp,
        random_state=42
    )
    
    logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    
    return X_train, X_val, X_test, y_train, y_val, y_test
