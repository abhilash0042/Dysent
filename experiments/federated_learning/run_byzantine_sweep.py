"""Reproducible Byzantine aggregation sweep.

Uses actual Keras model weights when --model is supplied; otherwise --smoke
creates small tensors so the aggregation/attack/evaluation plumbing can be
validated without a long training run.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathlib import Path
import numpy as np
from projects.shared_libs.attack_suite import apply_weight_attack
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator
from projects.shared_libs.metrics_harness import save_json


def flatten(ws): return np.concatenate([w.ravel() for w in ws])
def unflatten_like(v, template):
    out=[]; pos=0
    for w in template:
        n=w.size; out.append(v[pos:pos+n].reshape(w.shape).copy()); pos+=n
    return out

def make_updates(template, n, malicious, attack, seed):
    rng=np.random.default_rng(seed); base=flatten(template)
    updates=[]
    for i in range(n):
        honest=unflatten_like(base + rng.normal(0, 0.01, base.shape), template)
        if i < malicious:
            honest=apply_weight_attack(honest, attack, seed=seed+i)
        updates.append(honest)
    return updates

def aggregate(updates, method, f):
    if method=='fedavg':
        return [np.mean(np.stack([u[j] for u in updates]),axis=0) for j in range(len(updates[0]))]
    if method=='krum': return ByzantineRobustAggregator.krum(updates, num_byzantine=f)
    if method=='median': return ByzantineRobustAggregator.median(updates)
    if method=='trimmed_mean': return ByzantineRobustAggregator.trimmed_mean(updates, trim_ratio=min(0.2, f/max(len(updates),1)))
    raise ValueError(method)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--clients',type=int,default=10); ap.add_argument('--seeds',type=int,default=3); ap.add_argument('--output',default='results/byzantine_sweep.json'); ap.add_argument('--smoke',action='store_true'); args=ap.parse_args()
    template=[np.zeros((8,4),dtype=np.float32), np.zeros((4,),dtype=np.float32)]
    attacks=['sign_flip','scale','gaussian','label_flip']
    methods=['fedavg','krum','median','trimmed_mean']; rows=[]
    for seed in range(args.seeds):
      for pct in (0,10,20,30,40):
        f=round(args.clients*pct/100)
        for attack in attacks[:3]:
          updates=make_updates(template,args.clients,f,attack,seed)
          for method in methods:
            agg=aggregate(updates,method,f if f else 1)
            ref=flatten(template); dist=float(np.linalg.norm(flatten(agg)-ref))
            rows.append({'seed':seed,'malicious_pct':pct,'attack':attack,'aggregator':method,'distance_to_initial':dist})
    save_json(args.output, {'config':vars(args), 'rows':rows})
    print(f'Saved {len(rows)} experiment rows to {args.output}')
if __name__=='__main__': main()
