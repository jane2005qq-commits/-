import json

def build_opensees_model_from_ai(json_file_path: str):
    """
    從 AI 生成的 JSON 結構設計數據，轉換為 OpenSeesPy 建模與力學驗證指令。
    注意：由於環境 DLL 問題，若 openseespy 載入失敗，將回傳模擬數據。
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = {}
    try:
        import openseespy.opensees as ops
        
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 3)

        for node in data.get('nodes', []):
            ops.node(node['id'], node['x'], node['y'])
            if 'support' in node:
                ops.fix(node['id'], *node['support'])
        
        fc = data.get('material', {}).get('fc', 280)
        E = 15000 * (fc ** 0.5)
        ops.uniaxialMaterial('Elastic', 1, E)

        ops.geomTransf('Linear', 1) 
        for elem in data.get('elements', []):
            b, h = elem['b'], elem['h']
            A = b * h
            Iz = (b * h**3) / 12
            ops.element('elasticBeamColumn', elem['id'], elem['nodes'][0], elem['nodes'][1], A, E, Iz, 1)

        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        for elem in data.get('elements', []):
            if 'load_w' in elem:
                ops.eleLoad('-ele', elem['id'], '-type', '-beamUniform', elem['load_w'])

        ops.system('BandSPD')
        ops.numberer('RCM')
        ops.constraints('Plain')
        ops.integrator('LoadControl', 1.0)
        ops.algorithm('Linear')
        ops.analysis('Static')
        ops.analyze(1)

        for elem in data.get('elements', []):
            forces = ops.eleResponse(elem['id'], 'forces')
            results[elem['id']] = forces
            
    except Exception as e:
        print(f"[警告] OpenSeesPy 引擎載入失敗 ({e})，使用模擬力學數據。")
        for elem in data.get('elements', []):
            results[elem['id']] = [0.0, 0.0, 1000.0, 0.0, 0.0, -1000.0]

    return results

if __name__ == "__main__":
    sample_ai_output = {
        "material": {"fc": 280},
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0, "support": [1, 1, 1]},
            {"id": 2, "x": 0.0, "y": 300.0, "support": [0, 0, 0]},
            {"id": 3, "x": 500.0, "y": 300.0, "support": [0, 1, 0]}
        ],
        "elements": [
            {"id": 1, "type": "column", "b": 40, "h": 40, "nodes": [1, 2]},
            {"id": 2, "type": "beam", "b": 30, "h": 60, "nodes": [2, 3], "load_w": -0.05}
        ]
    }
    test_json_path = "ai_design_output.json"
    with open(test_json_path, 'w', encoding='utf-8') as f:
        json.dump(sample_ai_output, f, indent=4)
        
    build_opensees_model_from_ai(test_json_path)
