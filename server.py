from flask import Flask, request, jsonify, send_file
import json
import os
from opensees_integration import build_opensees_model_from_ai
from compliance_checker import check_strong_column_weak_beam, check_reinforcement_ratio
from geometry_generator import generate_geometry
from dxf_parser import parse_multi_dxf_to_geometry
from rebar_calculator import calculate_rebar, calculate_element_materials, calculate_stair_materials
from dxf_generator import generate_dxf_from_geometry

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/generate_design', methods=['POST'])
def generate_design():
    params = request.json
    length = params.get('length', 10.0)
    width = params.get('width', 8.0)
    height = params.get('height', 3.2)
    floors = params.get('floors', 3)
    has_stairs = params.get('has_stairs', False)
    stair_width = params.get('stair_width', 1.2)
    stair_tread = params.get('stair_tread', 25)
    stair_thickness = params.get('stair_thickness', 15)
    
    # 1. 根據尺寸生成 3D 結構幾何
    data = generate_geometry(length, width, height, floors, has_stairs, stair_width, stair_tread, stair_thickness)
    return process_design_data(data)

@app.route('/api/upload_dxf_multi', methods=['POST'])
def upload_dxf_multi():
    dxf_files = request.files.getlist('dxf_files')
    heights_str = request.form.get('heights', '[]')
    is_single_file = request.form.get('is_single_file', 'false').lower() == 'true'
    
    try:
        heights = json.loads(heights_str)
    except:
        heights = [3.2] * len(dxf_files)
        
    if not dxf_files:
        return jsonify({"error": "No files uploaded"}), 400
        
    # 解析多層 DXF 取得結構幾何
    data = parse_multi_dxf_to_geometry(dxf_files, heights, is_single_file=is_single_file)
    
    return process_design_data(data)

def process_design_data(data):
    
    import uuid
    session_id = str(uuid.uuid4())
    
    # 使用 uuid 避免多人同時存取時檔案被覆蓋
    test_json_path = f"ai_design_{session_id}.json"
    with open(test_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    # 2. 建立 2D 框架模型以供 OpenSees 運算 (過濾出 Z=0 的節點與元素)
    # 為了不改動原有 2D opensees_integration，我們提取主框架
    frame_nodes = [n for n in data['nodes'] if n['z'] == 0.0]
    frame_node_ids = {n['id'] for n in frame_nodes}
    frame_elements = [e for e in data['elements'] if e['nodes'][0] in frame_node_ids and e['nodes'][1] in frame_node_ids]
    
    frame_data = {
        "material": data['material'],
        "nodes": frame_nodes,
        "elements": frame_elements
    }
    frame_json_path = f"frame_output_{session_id}.json"
    with open(frame_json_path, 'w', encoding='utf-8') as f:
        json.dump(frame_data, f, indent=4)

    # 3. 執行力學分析
    try:
        results = build_opensees_model_from_ai(frame_json_path)
    except Exception as e:
        results = {}
        print("力學分析失敗:", e)
        
    # 4. 配筋與材料數量計算 (對所有 3D 構件)
    elements = data.get('elements', [])
    total_concrete_volume = 0.0
    total_rebar_weight = 0.0
    
    for e in elements:
        if e['type'] in ['stair', 'stair_landing']:
            # 呼叫樓梯版專屬的材料計算 (單層鋼筋)
            mat_data = calculate_stair_materials(
                b_cm=e['b'],
                h_cm=e['h'],
                length_m=e['length']
            )
            # 給前端顯示用的假資料或實際計算結果
            e['rebar_area'] = mat_data['rebar_area_cm2']
            e['num_bars'] = "單層雙向"
            total_concrete_volume += mat_data['volume_m3']
            total_rebar_weight += mat_data['rebar_weight_kg']
        else:
            # 一般柱樑計算
            forces = results.get(e['id'], [0, 0, 1500000, 0, 20000, 0])
            Vu = forces[4] if len(forces) > 4 else 20000  
            Mu = forces[5] if len(forces) > 5 else 1500000 
            
            rebar_data = calculate_rebar(b=e['b'], h=e['h'], Mu_kgf_cm=Mu, Vu_kgf=Vu, elem_type=e['type'])
            
            e['rebar_area'] = rebar_data['As_req']
            e['shear_spacing'] = rebar_data['shear_spacing']
            e['num_bars'] = rebar_data['num_bars']
            e['lap_length'] = rebar_data['lap_length']
            
            mat_data = calculate_element_materials(
                b_cm=e['b'], 
                h_cm=e['h'], 
                length_m=e['length'], 
                num_bars=e['num_bars'], 
                shear_spacing_cm=e['shear_spacing']
            )
            total_concrete_volume += mat_data['volume_m3']
            total_rebar_weight += mat_data['rebar_weight_kg']

    # 5. 執行法規校核
    issues = []
    issues.extend(check_strong_column_weak_beam(elements, results, data.get('nodes', [])))
    issues.extend(check_reinforcement_ratio(elements))
    
    # 6. 產生 DXF 檔案
    dxf_path = f"structure_{session_id}.dxf"
    generate_dxf_from_geometry(data, dxf_path)
    
    # 讀取 DXF 檔案並轉換為 Base64
    with open(dxf_path, 'rb') as f:
        dxf_bytes = f.read()
    import base64
    dxf_b64 = base64.b64encode(dxf_bytes).decode('utf-8')
    
    # 轉為噸
    total_rebar_weight_ton = total_rebar_weight / 1000.0
    
    # 清理暫存檔案 (避免伺服器硬碟爆滿或多人衝突)
    import os
    for p in [test_json_path, frame_json_path, dxf_path]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except:
                pass
    
    return jsonify({
        "elements": elements,
        "issues": issues,
        "total_concrete_volume": total_concrete_volume,
        "total_rebar_weight_ton": total_rebar_weight_ton,
        "dxf_base64": dxf_b64
    })

if __name__ == '__main__':
    print("Antigravity Structure Design Server Started!")
    print("Please open your browser to: http://localhost:5000")
    app.run(port=5000, debug=True)
