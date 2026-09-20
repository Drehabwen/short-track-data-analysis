import io
path = r'C:\Users\labops\.codex\config.toml'
with io.open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'model = "deepseek-v4-pro"\nmodel_reasoning_effort = "high"'
new = 'model = "deepseek-v4-pro"\nmodel_provider = "deepseek"\nmodel_reasoning_effort = "high"'

if 'model_provider = "deepseek"' in content:
    print('ALREADY PRESENT - no change')
elif old in content:
    content = content.replace(old, new, 1)
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('INSERTED model_provider = deepseek')
else:
    print('PATTERN NOT FOUND - no change')
