import json
import os

def normalize_memeargs(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    normalized = []
    for item in data:
        # The structure is already very close
        # We just need to flatten some fields to match the visgraph example
        
        # Original: item['id'], item['data']['image'], item['data']['graph']
        # Target: item['id'], item['image_filename'], item['data']['graph']
        
        id_val = item.get('id')
        data_block = item.get('data', {})
        image_filename = data_block.get('image')
        graph = data_block.get('graph', {})
        
        # Ensure nodes have correct fields
        nodes = graph.get('nodes', [])
        for node in nodes:
            # Already has idx, text, type
            pass
            
        # Ensure arguments have correct fields
        arguments = graph.get('arguments', [])
        for arg in arguments:
            # Already has claim, premises, type
            pass
            
        new_item = {
            "id": id_val,
            "image_filename": image_filename,
            "image_md5": "", # Placeholder
            "data": {
                "graph": {
                    "nodes": nodes,
                    "arguments": arguments
                }
            }
        }
        normalized.append(new_item)
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, indent=2)

if __name__ == "__main__":
    input_file = r"c:\Users\boden\Documents\Coding\research\graph-represent\data\memeargs\raw\memeargs_0329_fixed_v1.json"
    output_file = r"c:\Users\boden\Documents\Coding\research\graph-represent\data\memeargs\graphs\memeargs_normalized.json"
    normalize_memeargs(input_file, output_file)
    print(f"Normalized {input_file} to {output_file}")
