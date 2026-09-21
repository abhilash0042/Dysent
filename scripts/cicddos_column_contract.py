"""
Column-name contract for CICDDoS2019 CSV variants.

The leak-free pipeline uses spaced CICFlowMeter-V3 names
(e.g. 'Flow Duration'). Stratified Kaggle CSVs often remove spaces
(e.g. 'FlowDuration'). This map is the single source of truth so
raw downloads never silently mismatch training features.
"""

from __future__ import annotations

# Raw CSV / spaced-stripped name  ->  contract name used by leak-free pipeline
CSV_TO_CONTRACT: dict[str, str] = {
    # Identifiers (kept for Path-B windowing, never fed to the model)
    'Unnamed:0': 'Unnamed: 0',
    'Unnamed: 0': 'Unnamed: 0',
    'FlowID': 'Flow ID',
    'Flow ID': 'Flow ID',
    'SourceIP': 'Source IP',
    'Source IP': 'Source IP',
    'SourcePort': 'Source Port',
    'Source Port': 'Source Port',
    'DestinationIP': 'Destination IP',
    'Destination IP': 'Destination IP',
    'DestinationPort': 'Destination Port',
    'Destination Port': 'Destination Port',
    'Protocol': 'Protocol',
    'Timestamp': 'Timestamp',

    # Flow stats
    'FlowDuration': 'Flow Duration',
    'Flow Duration': 'Flow Duration',
    'TotalFwdPackets': 'Total Fwd Packets',
    'Total Fwd Packets': 'Total Fwd Packets',
    'Total BackwardPackets': 'Total Backward Packets',
    'TotalBackwardPackets': 'Total Backward Packets',
    'Total Backward Packets': 'Total Backward Packets',
    'TotalLengthofFwdPackets': 'Fwd Packets Length Total',
    'Total Length of Fwd Packets': 'Fwd Packets Length Total',
    'Fwd Packets Length Total': 'Fwd Packets Length Total',
    'TotalLengthofBwdPackets': 'Bwd Packets Length Total',
    'Total Length of Bwd Packets': 'Bwd Packets Length Total',
    'Bwd Packets Length Total': 'Bwd Packets Length Total',

    'FwdPacketLengthMax': 'Fwd Packet Length Max',
    'Fwd Packet Length Max': 'Fwd Packet Length Max',
    'FwdPacketLengthMin': 'Fwd Packet Length Min',
    'Fwd Packet Length Min': 'Fwd Packet Length Min',
    'FwdPacketLengthMean': 'Fwd Packet Length Mean',
    'Fwd Packet Length Mean': 'Fwd Packet Length Mean',
    'FwdPacketLengthStd': 'Fwd Packet Length Std',
    'Fwd Packet Length Std': 'Fwd Packet Length Std',

    'BwdPacketLengthMax': 'Bwd Packet Length Max',
    'Bwd Packet Length Max': 'Bwd Packet Length Max',
    'BwdPacketLengthMin': 'Bwd Packet Length Min',
    'Bwd Packet Length Min': 'Bwd Packet Length Min',
    'BwdPacketLengthMean': 'Bwd Packet Length Mean',
    'Bwd Packet Length Mean': 'Bwd Packet Length Mean',
    'BwdPacketLengthStd': 'Bwd Packet Length Std',
    'Bwd Packet Length Std': 'Bwd Packet Length Std',

    'FlowBytes/s': 'Flow Bytes/s',
    'Flow Bytes/s': 'Flow Bytes/s',
    'FlowPackets/s': 'Flow Packets/s',
    'Flow Packets/s': 'Flow Packets/s',

    'FlowIATMean': 'Flow IAT Mean',
    'Flow IAT Mean': 'Flow IAT Mean',
    'FlowIATStd': 'Flow IAT Std',
    'Flow IAT Std': 'Flow IAT Std',
    'FlowIATMax': 'Flow IAT Max',
    'Flow IAT Max': 'Flow IAT Max',
    'FlowIATMin': 'Flow IAT Min',
    'Flow IAT Min': 'Flow IAT Min',

    'FwdIATTotal': 'Fwd IAT Total',
    'Fwd IAT Total': 'Fwd IAT Total',
    'FwdIATMean': 'Fwd IAT Mean',
    'Fwd IAT Mean': 'Fwd IAT Mean',
    'FwdIATStd': 'Fwd IAT Std',
    'Fwd IAT Std': 'Fwd IAT Std',
    'FwdIATMax': 'Fwd IAT Max',
    'Fwd IAT Max': 'Fwd IAT Max',
    'FwdIATMin': 'Fwd IAT Min',
    'Fwd IAT Min': 'Fwd IAT Min',

    'BwdIATTotal': 'Bwd IAT Total',
    'Bwd IAT Total': 'Bwd IAT Total',
    'BwdIATMean': 'Bwd IAT Mean',
    'Bwd IAT Mean': 'Bwd IAT Mean',
    'BwdIATStd': 'Bwd IAT Std',
    'Bwd IAT Std': 'Bwd IAT Std',
    'BwdIATMax': 'Bwd IAT Max',
    'Bwd IAT Max': 'Bwd IAT Max',
    'BwdIATMin': 'Bwd IAT Min',
    'Bwd IAT Min': 'Bwd IAT Min',

    'FwdHeaderLength': 'Fwd Header Length',
    'Fwd Header Length': 'Fwd Header Length',
    'FwdHeaderLength.1': 'Fwd Header Length',
    'BwdHeaderLength': 'Bwd Header Length',
    'Bwd Header Length': 'Bwd Header Length',

    'FwdPackets/s': 'Fwd Packets/s',
    'Fwd Packets/s': 'Fwd Packets/s',
    'BwdPackets/s': 'Bwd Packets/s',
    'Bwd Packets/s': 'Bwd Packets/s',

    'MinPacketLength': 'Packet Length Min',
    'Packet Length Min': 'Packet Length Min',
    'MaxPacketLength': 'Packet Length Max',
    'Packet Length Max': 'Packet Length Max',
    'PacketLengthMean': 'Packet Length Mean',
    'Packet Length Mean': 'Packet Length Mean',
    'PacketLengthStd': 'Packet Length Std',
    'Packet Length Std': 'Packet Length Std',
    'PacketLengthVariance': 'Packet Length Variance',
    'Packet Length Variance': 'Packet Length Variance',

    'ACKFlagCount': 'ACK Flag Count',
    'ACK Flag Count': 'ACK Flag Count',
    'SYNFlagCount': 'SYN Flag Count',
    'SYN Flag Count': 'SYN Flag Count',
    'FINFlagCount': 'FIN Flag Count',
    'FIN Flag Count': 'FIN Flag Count',
    'RSTFlagCount': 'RST Flag Count',
    'RST Flag Count': 'RST Flag Count',
    'PSHFlagCount': 'PSH Flag Count',
    'PSH Flag Count': 'PSH Flag Count',
    'URGFlagCount': 'URG Flag Count',
    'URG Flag Count': 'URG Flag Count',

    'AveragePacketSize': 'Avg Packet Size',
    'Avg Packet Size': 'Avg Packet Size',
    'AvgFwdSegmentSize': 'Avg Fwd Segment Size',
    'Avg Fwd Segment Size': 'Avg Fwd Segment Size',
    'AvgBwdSegmentSize': 'Avg Bwd Segment Size',
    'Avg Bwd Segment Size': 'Avg Bwd Segment Size',

    'SubflowFwdPackets': 'Subflow Fwd Packets',
    'Subflow Fwd Packets': 'Subflow Fwd Packets',
    'SubflowFwdBytes': 'Subflow Fwd Bytes',
    'Subflow Fwd Bytes': 'Subflow Fwd Bytes',
    'SubflowBwdPackets': 'Subflow Bwd Packets',
    'Subflow Bwd Packets': 'Subflow Bwd Packets',
    'SubflowBwdBytes': 'Subflow Bwd Bytes',
    'Subflow Bwd Bytes': 'Subflow Bwd Bytes',

    'Init_Win_bytes_forward': 'Init Fwd Win Bytes',
    'Init Fwd Win Bytes': 'Init Fwd Win Bytes',
    'Init_Win_bytes_backward': 'Init Bwd Win Bytes',
    'Init Bwd Win Bytes': 'Init Bwd Win Bytes',
    'act_data_pkt_fwd': 'Fwd Act Data Packets',
    'Fwd Act Data Packets': 'Fwd Act Data Packets',
    'min_seg_size_forward': 'Fwd Seg Size Min',
    'Fwd Seg Size Min': 'Fwd Seg Size Min',

    'IdleMean': 'Idle Mean',
    'Idle Mean': 'Idle Mean',
    'IdleStd': 'Idle Std',
    'Idle Std': 'Idle Std',
    'IdleMax': 'Idle Max',
    'Idle Max': 'Idle Max',
    'IdleMin': 'Idle Min',
    'Idle Min': 'Idle Min',
    'ActiveMean': 'Active Mean',
    'Active Mean': 'Active Mean',
    'ActiveStd': 'Active Std',
    'Active Std': 'Active Std',
    'ActiveMax': 'Active Max',
    'Active Max': 'Active Max',
    'ActiveMin': 'Active Min',
    'Active Min': 'Active Min',

    'Label': 'Label',
    'Class': 'Class',
}

# Label strings in raw CSVs -> label encoder classes used by the trained model
LABEL_TO_CONTRACT: dict[str, str] = {
    'BENIGN': 'Benign',
    'Benign': 'Benign',
    'DrDoS_DNS': 'DrDoS_DNS',
    'DrDoS_LDAP': 'DrDoS_LDAP',
    'DrDoS_MSSQL': 'DrDoS_MSSQL',
    'DrDoS_NTP': 'DrDoS_NTP',
    'DrDoS_NetBIOS': 'DrDoS_NetBIOS',
    'DrDoS_SNMP': 'DrDoS_SNMP',
    'DrDoS_SSDP': 'DrDoS_UDP',  # no SSDP class in contract; nearest volumetric UDP-family
    'DrDoS_UDP': 'DrDoS_UDP',
    'LDAP': 'LDAP',
    'MSSQL': 'MSSQL',
    'NetBIOS': 'NetBIOS',
    'Portmap': 'Portmap',
    'Syn': 'Syn',
    'TFTP': 'TFTP',
    'UDP': 'UDP',
    'UDP-lag': 'UDP-lag',
    'UDPLag': 'UDPLag',
    'WebDDoS': 'WebDDoS',
}

# Columns that must never enter the feature matrix
LEAKY_COLUMNS = {'Unnamed: 0', 'Label', 'Class'}

# Columns needed only for Path-B temporal grouping (not model inputs)
PATHB_KEY_COLUMNS = [
    'Timestamp',
    'Source IP',
    'Destination IP',
    'Destination Port',
    'Protocol',
    'Flow ID',
]


def _collapse(name: str) -> str:
    """Strip separators so Source_IP / SourceIP / Source IP all match."""
    return (
        name.strip()
        .replace(' ', '')
        .replace('_', '')
        .replace('-', '')
        .replace('.', '')
        .lower()
    )


def normalize_columns(columns) -> dict[str, str]:
    """Return {raw_col: contract_col} for columns we know how to map.

    Handles three common CICDDoS2019 CSV dialects in one shot:
      spaced        'Source IP' / 'Flow Duration'
      glued         'SourceIP'  / 'FlowDuration'
      underscored   'Source_IP' / 'Flow_Duration'
    """
    collapsed_lookup = {_collapse(k): v for k, v in CSV_TO_CONTRACT.items()}
    # Prefer the spaced contract name itself when several keys collapse together
    for contract_name in set(CSV_TO_CONTRACT.values()):
        collapsed_lookup[_collapse(contract_name)] = contract_name

    mapping = {}
    for c in columns:
        key = c.strip() if isinstance(c, str) else str(c)
        if key in CSV_TO_CONTRACT:
            mapping[c] = CSV_TO_CONTRACT[key]
            continue
        # underscore -> space form, then exact
        spaced = key.replace('_', ' ')
        if spaced in CSV_TO_CONTRACT:
            mapping[c] = CSV_TO_CONTRACT[spaced]
            continue
        hit = collapsed_lookup.get(_collapse(key))
        if hit:
            mapping[c] = hit
    return mapping
