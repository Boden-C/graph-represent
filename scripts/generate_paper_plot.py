#!/usr/bin/env python3
import json
import os
from glob import glob
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(__file__))
OUTROOT = os.path.join(ROOT, 'output', '20260423_021542')
PAPER_DIR = os.path.join(ROOT, 'paper')
os.makedirs(PAPER_DIR, exist_ok=True)

def load_manifest(run_dir):
    path = os.path.join(run_dir, 'run_manifest.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

def load_item_value(output_path):
    try:
        with open(output_path, 'r') as f:
            j = json.load(f)
    except Exception:
        return None
    vals = []
    for v in j.get('variants', []):
        s = v.get('scores', {}).get('scores', {})
        if 'overall_quality_mean' in s:
            vals.append(s['overall_quality_mean'])
    if not vals:
        return None
    return float(np.mean(vals))

def process_run(run_name, run_dir):
    manifest = load_manifest(run_dir)
    if manifest is None:
        return None
    items = []
    for item_id, meta in manifest.get('items', {}).items():
        updated = meta.get('updated_at')
        output_path = meta.get('output_path')
        if output_path and updated:
            val = load_item_value(output_path)
            if val is None:
                continue
            # parse timestamp
            try:
                ts = datetime.fromisoformat(updated.replace('Z', '+00:00'))
            except Exception:
                ts = datetime.now()
            items.append((ts, item_id, val))
    if not items:
        return None
    # sort by time
    items.sort(key=lambda x: x[0])
    times = [t for t,_,_ in items]
    values = [v for _,_,v in items]
    # running stats
    running_mean = []
    running_ci = []
    for i in range(1, len(values)+1):
        arr = np.array(values[:i], dtype=float)
        mean = arr.mean()
        if i > 1:
            sd = arr.std(ddof=1)
            half = 1.96 * sd / np.sqrt(i)
        else:
            half = float('inf')
        running_mean.append(mean)
        running_ci.append(half)
    # convergence: first index where half <= 0.01
    conv_idx = None
    for idx, half in enumerate(running_ci, start=1):
        if np.isfinite(half) and half <= 0.01:
            conv_idx = idx
            break
    conv_time = times[conv_idx-1].isoformat() if conv_idx else None
    return {
        'run_name': run_name,
        'times': [t.isoformat() for t in times],
        'values': values,
        'running_mean': running_mean,
        'running_ci': running_ci,
        'convergence_index': conv_idx,
        'convergence_time': conv_time,
        'final_mean': running_mean[-1],
        'final_ci_halfwidth': running_ci[-1],
    }

def main():
    runs = {}
    for entry in os.listdir(OUTROOT):
        path = os.path.join(OUTROOT, entry)
        if os.path.isdir(path):
            r = process_run(entry, path)
            if r:
                runs[entry] = r

    # plot
    plt.figure(figsize=(10,6))
    for name, data in runs.items():
        x = np.arange(1, len(data['running_mean'])+1)
        mean = np.array(data['running_mean'])
        ci = np.array(data['running_ci'])
        plt.plot(x, mean, label=name)
        lower = mean - ci
        upper = mean + ci
        plt.fill_between(x, lower, upper, alpha=0.15)
        if data['convergence_index']:
            plt.axvline(data['convergence_index'], linestyle='--', alpha=0.6)
    plt.xlabel('items processed')
    plt.ylabel('running mean overall_quality')
    plt.title('Score over time by run (running mean ± 95% CI)')
    plt.legend()
    png_path = os.path.join(PAPER_DIR, '2026-04-23.png')
    plt.tight_layout()
    plt.savefig(png_path)

    # write summary
    summary_path = os.path.join(PAPER_DIR, '2026-04-23-summary.json')
    with open(summary_path, 'w') as f:
        json.dump(runs, f, indent=2)
    print('wrote', png_path, summary_path)

if __name__ == '__main__':
    main()
