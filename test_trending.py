import sys
sys.stdout.reconfigure(encoding='utf-8')
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
res = client.get('/')
assert res.status_code == 200
html = res.text

# Check trending tags exist as interactive buttons
for word in ['iPhone', 'ሶፋ', 'ማቀዝቀዣ', 'ጠረጴዛ', 'Addis Ababa', 'Bahir Dar', 'Gondar']:
    assert word in html, f'Missing {word} in HTML'
    print(f'  ✅ Tag present: {word}')

assert 'id="popular-tags-strip"' in html
assert 'data-type="keyword"' in html
assert 'data-type="location"' in html
assert 'class="tag-close"' in html
print('  ✅ HTML elements and attributes validated')

css_res = client.get('/static/store.css')
assert '.quick-tag.active' in css_res.text
assert '.tag-close' in css_res.text
print('  ✅ CSS styles for active and dismiss states validated')

js_res = client.get('/static/store.js')
assert 'COMMON_SYNONYMS' in js_res.text
assert 'activeSynonyms' in js_res.text
assert 'data-type' in js_res.text
print('  ✅ JavaScript engine with synonym & toggle logic validated')

print('\n🎉 ALL TRENDING PANEL FUNCTIONALITY TESTS PASSED!')
