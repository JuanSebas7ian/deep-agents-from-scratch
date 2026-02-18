import json

NOTEBOOK_PATH = '/home/juansebas7ian/deep-agents-from-scratch/notebooks/4_full_neuro_agent.ipynb'

def fix_dynamo_import():
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        cells = nb.get('cells', [])
        
        target_cell_index = -1
        for i, cell in enumerate(cells):
            source = "".join(cell.get('source', []))
            if "Initialize DynamoDB Checkpointer (Strict)" in source:
                target_cell_index = i
                break
        
        if target_cell_index != -1:
            print("Found Checkpointer configuration cell. Fixing import...")
            
            new_source = [
                "# --- CONFIGURACIÓN DE CHECKPOINTER ---\n",
                "# Using custom ChunkedDynamoDBSaver from shared kernel\n",
                "from neuro_agent.src.shared.dynamo_checkpointer import DynamoDBSaver\n",
                "\n",
                "# Initialize DynamoDB Checkpointer (Strict)\n",
                "checkpointer = DynamoDBSaver(table_name=\"LangGraphCheckpoints\")\n",
                "print(f\"✅ DynamoDB Checkpointer Initialized\")\n"
            ]
            
            cells[target_cell_index]['source'] = new_source
            
            with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
                json.dump(nb, f, indent=1)
            print(f"Successfully fixed DynamoDB import in {NOTEBOOK_PATH}")
            
        else:
            print("Could not find Checkpointer configuration cell.")

    except Exception as e:
        print(f"Error processing notebook: {e}")

if __name__ == "__main__":
    fix_dynamo_import()
