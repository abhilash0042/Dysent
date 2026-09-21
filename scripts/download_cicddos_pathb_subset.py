"""
Download only the Path-B CICDDoS2019 CSV subset from Kaggle.

Does NOT touch existing data/processed artifacts.
Saves into data/raw/cicddos2019_subset/.

Requires: pip install kaggle  +  %USERPROFILE%\\.kaggle\\kaggle.json
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
OUT = project_root / 'data' / 'raw' / 'cicddos2019_subset'

# Attack types that matter for SDN demo. Each official CIC file also mixes
# a small amount of BENIGN background traffic — there is no separate BENIGN.csv.
WANTED = [
    'Syn.csv',
    'DrDoS_UDP.csv',
    'DrDoS_DNS.csv',
    'DrDoS_NTP.csv',
    'UDPLag.csv',
    'DrDoS_LDAP.csv',
    'DrDoS_MSSQL.csv',
    'DrDoS_NetBIOS.csv',
    'TFTP.csv',
]

DATASET = 'neonboy19/cicddos-2019-stratified-sampled-dataset'


def main():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        print('Install kaggle first: pip install kaggle')
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()

    available = {f.name for f in api.dataset_list_files(DATASET).files}
    for name in WANTED:
        if name not in available:
            print(f'SKIP missing remotely: {name}')
            continue
        dest = OUT / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f'EXISTS {name} ({dest.stat().st_size/1e6:.1f} MB) — skipping')
            continue
        print(f'Downloading {name}...')
        api.dataset_download_file(DATASET, name, path=str(OUT), quiet=False, force=True)
        # kaggle sometimes writes a .zip
        zipped = OUT / f'{name}.zip'
        if zipped.exists():
            import zipfile
            with zipfile.ZipFile(zipped) as zf:
                zf.extractall(OUT)
            zipped.unlink()
        print(f'  -> {dest} ({dest.stat().st_size/1e6:.1f} MB)' if dest.exists() else '  FAILED')

    print('Done stratified. Files:', sorted(p.name for p in OUT.glob('*.csv')))
    download_portmap_official()


def download_portmap_official():
    """
    Official 03-11 Portmap.csv (~79 MB) is the smallest full CIC day-2 file.
    Stream it and keep only BENIGN rows so we don't store 79 MB of Portmap flood.
    """
    import urllib.request

    dest = OUT / 'BENIGN_from_Portmap.csv'
    if dest.exists() and dest.stat().st_size > 10_000:
        print(f'EXISTS {dest.name} ({dest.stat().st_size/1e6:.2f} MB) — skipping')
        return

    url = (
        'https://huggingface.co/datasets/baalajimaestro/CICDDoS2019/'
        'resolve/main/03-11/Portmap.csv'
    )
    print(f'Streaming official Portmap.csv from Hugging Face, keeping BENIGN only...')
    tmp = OUT / '_portmap_full.csv'
    try:
        urllib.request.urlretrieve(url, tmp)
        print(f'  downloaded {tmp.stat().st_size/1e6:.1f} MB, filtering BENIGN...')
        import pandas as pd
        import sys
        sys.path.insert(0, str(project_root / 'scripts'))
        from cicddos_column_contract import normalize_columns, LABEL_TO_CONTRACT

        chunks = []
        for chunk in pd.read_csv(tmp, chunksize=50_000, low_memory=False):
            mapping = normalize_columns(chunk.columns)
            chunk = chunk.rename(columns=mapping)
            if chunk.columns.duplicated().any():
                chunk = chunk.loc[:, ~chunk.columns.duplicated()]
            if 'Label' not in chunk.columns:
                raise RuntimeError(f'Portmap.csv has no Label after rename: {list(chunk.columns)[:20]}')
            labels = chunk['Label'].astype(str).str.strip().map(
                lambda x: LABEL_TO_CONTRACT.get(x, x)
            )
            keep = chunk.loc[labels.eq('Benign')].copy()
            keep['Label'] = 'Benign'
            if len(keep):
                chunks.append(keep)
        if not chunks:
            print('  WARNING: no BENIGN rows in Portmap.csv')
            return
        out = pd.concat(chunks, ignore_index=True)
        out.to_csv(dest, index=False)
        print(f'  wrote {dest.name}: {len(out):,} BENIGN rows ({dest.stat().st_size/1e6:.2f} MB)')
    finally:
        if tmp.exists():
            tmp.unlink()
            print('  deleted full Portmap.csv to save disk')


if __name__ == '__main__':
    main()
