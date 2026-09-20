import json
with open(r'C:\Users\labops\.codex\models.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
for m in data.get('models', []):
    slug = m.get('slug')
    print(f'{slug}: prefer_websockets={m.get("prefer_websockets")} wire_api={m.get("wire_api")} provider={m.get("model_provider") or m.get("provider")}')
