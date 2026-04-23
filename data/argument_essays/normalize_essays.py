import os
import json
import re

def parse_ann_file(ann_path):
    nodes = []
    arguments = []
    
    # Map T_id to node index
    tid_to_idx = {}
    
    with open(ann_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # First pass: collect nodes
    for line in lines:
        if line.startswith('T'):
            parts = line.strip().split('\t')
            if len(parts) < 3: continue
            tid = parts[0]
            meta = parts[1].split(' ')
            node_type = meta[0]
            # text = parts[2] # Some files might have different tab structure
            # Re-parse more robustly
            match = re.match(r'(T\d+)\t(\w+)\s\d+\s\d+\t(.*)', line.strip())
            if not match: continue
            tid, raw_type, text = match.groups()
            
            idx = len(nodes)
            tid_to_idx[tid] = idx
            
            nodes.append({
                "idx": idx,
                "text": text,
                "type": raw_type
            })
            
    # Second pass: collect relations
    for line in lines:
        if line.startswith('R'):
            parts = line.strip().split('\t')
            if len(parts) < 2: continue
            meta = parts[1].split(' ')
            rel_type = meta[0] # supports or attacks
            arg1_part = meta[1] # Arg1:T4
            arg2_part = meta[2] # Arg2:T3
            
            tid1 = arg1_part.split(':')[1]
            tid2 = arg2_part.split(':')[1]
            
            if tid1 in tid_to_idx and tid2 in tid_to_idx:
                idx1 = tid_to_idx[tid1]
                idx2 = tid_to_idx[tid2]
                
                # In visgraph: claim is the target, premises are the sources
                # Arg1 is premise, Arg2 is claim
                
                # Find existing argument for this claim
                found = False
                for arg in arguments:
                    if arg['claim'] == idx2 and arg['type'] == rel_type:
                        arg['premises'].append(idx1)
                        found = True
                        break
                
                if not found:
                    arguments.append({
                        "claim": idx2,
                        "premises": [idx1],
                        "type": "support" if rel_type == "supports" else "attack"
                    })
                    
    return nodes, arguments

def normalize_essays(input_dir, output_path):
    all_graphs = []
    files = [f for f in os.listdir(input_dir) if f.endswith('.ann')]
    files.sort()
    
    for filename in files:
        essay_id = filename.replace('.ann', '')
        ann_path = os.path.join(input_dir, filename)
        
        try:
            nodes, arguments = parse_ann_file(ann_path)
            
            item = {
                "id": essay_id,
                "image_filename": "", # No images for essays
                "image_md5": "",
                "data": {
                    "graph": {
                        "nodes": nodes,
                        "arguments": arguments
                    }
                }
            }
            all_graphs.append(item)
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_graphs, f, indent=2)

if __name__ == "__main__":
    input_dir = r"c:\Users\boden\Documents\Coding\research\graph-represent\data\argument_essays\raw\extracted_essays\brat_data\brat-project-final"
    output_file = r"c:\Users\boden\Documents\Coding\research\graph-represent\data\argument_essays\graphs\essays_normalized.json"
    normalize_essays(input_dir, output_file)
    print(f"Normalized essays to {output_file}")
