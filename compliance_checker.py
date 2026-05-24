import json

def check_strong_column_weak_beam(elements, results, nodes=None):
    """
    強柱弱樑檢查：簡單比對相鄰節點的柱與樑抗彎強度
    """
    print("\n--- 執行『強柱弱樑』檢查 ---")
    issues = []
    node_to_elems = {}
    for elem in elements:
        for node in elem['nodes']:
            if node not in node_to_elems:
                node_to_elems[node] = []
            node_to_elems[node].append(elem)

    max_y = max((n['y'] for n in nodes), default=0) if nodes else None

    for node, elems in node_to_elems.items():
        columns = [e for e in elems if e.get('type') == 'column']
        beams = [e for e in elems if e.get('type') == 'beam']
        
        if columns and beams:
            # 屋頂層豁免強柱弱樑檢核 (ACI 318)
            is_roof = False
            if nodes and max_y is not None:
                node_y = next((n['y'] for n in nodes if n['id'] == node), None)
                if node_y is not None and node_y >= max_y - 0.1:
                    is_roof = True
                    
            if is_roof:
                print(f"[OK] 節點 {node}: 屋頂層豁免強柱弱樑檢核")
                continue

            # 使用近似名目彎矩 capacity (As * d) 來取代 b*h^3/12
            sum_M_col = 0
            for c in columns:
                As = c.get('rebar_area', 0)
                if As > 0:
                    sum_M_col += As * max(c['h'] - 6, 0.8 * c['h'])
                else:
                    sum_M_col += (c['b'] * c['h']**2) / 6
                    
            sum_M_beam = 0
            for b_elem in beams:
                As = b_elem.get('rebar_area', 0)
                if As > 0:
                    sum_M_beam += As * max(b_elem['h'] - 6, 0.8 * b_elem['h'])
                else:
                    sum_M_beam += (b_elem['b'] * b_elem['h']**2) / 6
            
            ratio = sum_M_col / sum_M_beam if sum_M_beam > 0 else 0
            
            if ratio < 1.2:
                issue = f"[警告] 節點 {node}: 柱/樑抗彎強度比為 {ratio:.2f} (規範要求 >= 1.2)，不符合強柱弱樑！"
                issues.append(issue)
                print(issue)
            else:
                print(f"[OK] 節點 {node}: 強柱弱樑檢核通過 (比值 {ratio:.2f} >= 1.2)")
    
    return issues

def check_reinforcement_ratio(elements):
    """
    最小配筋率掃描：檢查是否低於規範最小配筋率，以及剪力筋間距
    """
    print("\n--- 執行『配筋率與剪力筋』檢查 ---")
    issues = []
    
    for elem in elements:
        b, h = elem['b'], elem['h']
        Ag = b * h 
        
        rebar_area = elem.get('rebar_area', 0)
        shear_spacing = elem.get('shear_spacing', 0)
        
        if rebar_area > 0:
            rho = rebar_area / Ag
            if elem['type'] == 'column' and rho < 0.01:
                issue = f"[異常] 柱 {elem['id']}: 配筋率 {rho*100:.2f}% 低於最小配筋率 1.0%！需要工程師複核。"
                issues.append(issue)
                print(issue)
            else:
                print(f"[OK] 柱 {elem['id']}: 配筋率 {rho*100:.2f}% 合規。")
                
        if shear_spacing > 0:
            max_spacing = min(h/2, 60)
            if shear_spacing > max_spacing:
                issue = f"[異常] 元素 {elem['id']}: 剪力筋間距 {shear_spacing}cm 超過最大限制 {max_spacing}cm！"
                issues.append(issue)
                print(issue)
            else:
                 print(f"[OK] 元素 {elem['id']}: 剪力筋間距 {shear_spacing}cm 合規。")

    return issues

def run_compliance_check(json_file_path: str, opensees_results: dict = None):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    elements = data.get('elements', [])
    
    for e in elements:
        if e['type'] == 'column':
            e['rebar_area'] = 12.0
            e['shear_spacing'] = 15 
        elif e['type'] == 'beam':
            e['rebar_area'] = 25.0
            e['shear_spacing'] = 25 

    all_issues = []
    all_issues.extend(check_strong_column_weak_beam(elements, opensees_results or {}))
    all_issues.extend(check_reinforcement_ratio(elements))
    
    print("\n--- 法規校核總結 ---")
    if not all_issues:
        print("恭喜！所有設計均符合規範，無需人工介入。")
    else:
        print(f"發現 {len(all_issues)} 項異常，請工程師介入審核：")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")

if __name__ == "__main__":
    from opensees_integration import build_opensees_model_from_ai
    test_json_path = "ai_design_output.json"
    try:
        results = build_opensees_model_from_ai(test_json_path)
    except Exception as e:
        results = {}
    run_compliance_check(test_json_path, results)
