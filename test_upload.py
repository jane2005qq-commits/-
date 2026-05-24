import urllib.request, urllib.parse, json
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = []
body.extend(['--' + boundary, 'Content-Disposition: form-data; name="heights"', '', '[3.2, 3.2]'])
with open('test_plan.dxf', 'rb') as f:
    file_data = f.read()
body.extend(['--' + boundary, 'Content-Disposition: form-data; name="dxf_files"; filename="test_plan.dxf"', 'Content-Type: application/octet-stream', ''])
body_str = '\r\n'.join(body) + '\r\n'
body_bytes = body_str.encode('utf-8') + file_data + '\r\n'.encode('utf-8')
body2 = ['--' + boundary, 'Content-Disposition: form-data; name="dxf_files"; filename="test_plan.dxf"', 'Content-Type: application/octet-stream', '']
body_str2 = '\r\n'.join(body2) + '\r\n'
body_bytes += body_str2.encode('utf-8') + file_data + '\r\n'.encode('utf-8')
body_bytes += ('--' + boundary + '--\r\n').encode('utf-8')
req = urllib.request.Request('http://localhost:5000/api/upload_dxf_multi', data=body_bytes, method='POST')
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    print('Total elements:', len(data['elements']))
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code)
    print(e.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)
