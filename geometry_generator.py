def generate_geometry(length_m, width_m, floor_height_m, floors, has_stairs=False, stair_width=1.2, stair_tread=25, stair_thickness=15):
    """
    根據空間尺寸生成 3D 結構的節點與元素。
    假設為 1跨(X向) x 1跨(Z向) 的簡單框架。
    支援 U 型雙跑樓梯的節點與板元素生成。
    """
    nodes = []
    elements = []
    
    # 決定斷面尺寸 (簡單經驗法則與合理上限)
    max_span = max(length_m, width_m)
    # 樑深 = 跨度/12 (cm)，上限 150cm (超過此跨距一般不使用純 RC 矩形樑)
    beam_h = min(max(int(max_span * 100 / 12), 40), 150) 
    # 樑寬 = 深/2 (cm)，上限 80cm
    beam_b = min(max(int(beam_h / 2), 30), 80)
    
    # 柱尺寸：必須大於等於樑寬以利鋼筋錨定，這裡設定為樑寬+20cm 或 樑深的 0.8 倍，取大者，上限 150cm
    col_size = min(max(int(beam_b + 20), int(beam_h * 0.8), 50), 150)
    
    node_id_counter = 1
    elem_id_counter = 1
    
    # 建立 Node 網格
    # z=0 和 z=width_m
    # x=0 和 x=length_m
    # y=0, h, 2h ...
    node_map = {} # (x, y, z) -> id
    
    for f in range(floors + 1):
        y = f * floor_height_m
        for z in [0.0, width_m]:
            for x in [0.0, length_m]:
                # 底層給 support
                support = [1, 1, 1, 1, 1, 1] if f == 0 else [0, 0, 0, 0, 0, 0]
                
                # 為了跟原先 2D Opensees 相容，這裡 support 只列 3 個自由度，
                # 但既然我們是 3D 結構，先定義完整的 3D 資訊。
                node = {
                    "id": node_id_counter,
                    "x": x,
                    "y": y,
                    "z": z,
                    "support": [1, 1, 1] if f == 0 else [0, 0, 0] # 簡化配合原 opensees_integration
                }
                nodes.append(node)
                node_map[(x, y, z)] = node_id_counter
                node_id_counter += 1
                
        # 如果有樓梯，而且不是最高層，我們在 y + h/2 建立休息平台節點
        if has_stairs and f < floors:
            y_mid = y + floor_height_m / 2.0
            # 假設樓梯在 z=0 這一側，從 x=0 走到 x=landing_x
            # 建立兩個休息平台節點 (x=landing_x, z=0, y=y_mid) 和 (x=landing_x, z=stair_width*2, y=y_mid)
            # 簡單一點，就在 (x=length_m/2) 建立平台節點
            node1 = {"id": node_id_counter, "x": length_m/2, "y": y_mid, "z": 0.0, "support": [0,0,0]}
            nodes.append(node1)
            node_map[(length_m/2, y_mid, 0.0)] = node_id_counter
            node_id_counter += 1
            
            node2 = {"id": node_id_counter, "x": length_m/2, "y": y_mid, "z": stair_width*2, "support": [0,0,0]}
            nodes.append(node2)
            node_map[(length_m/2, y_mid, stair_width*2)] = node_id_counter
            node_id_counter += 1

    # 建立 Elements (Columns)
    for f in range(floors):
        y1 = f * floor_height_m
        y2 = (f + 1) * floor_height_m
        for z in [0.0, width_m]:
            for x in [0.0, length_m]:
                n1 = node_map[(x, y1, z)]
                n2 = node_map[(x, y2, z)]
                elements.append({
                    "id": elem_id_counter,
                    "type": "column",
                    "b": col_size,
                    "h": col_size,
                    "length": floor_height_m,
                    "nodes": [n1, n2]
                })
                elem_id_counter += 1

    # 建立 Elements (Beams)
    for f in range(1, floors + 1):
        y = f * floor_height_m
        # X 向樑
        for z in [0.0, width_m]:
            n1 = node_map[(0.0, y, z)]
            n2 = node_map[(length_m, y, z)]
            elements.append({
                "id": elem_id_counter,
                "type": "beam",
                "b": beam_b,
                "h": beam_h,
                "length": length_m,
                "nodes": [n1, n2],
                "load_w": -0.05 * (beam_b/100) * (beam_h/100) * 2400 # 自重模擬
            })
            elem_id_counter += 1
            
        # Z 向樑
        for x in [0.0, length_m]:
            n1 = node_map[(x, y, 0.0)]
            n2 = node_map[(x, y, width_m)]
            elements.append({
                "id": elem_id_counter,
                "type": "beam",
                "b": beam_b,
                "h": beam_h,
                "length": width_m,
                "nodes": [n1, n2],
                "load_w": -0.05 * (beam_b/100) * (beam_h/100) * 2400
            })
            elem_id_counter += 1

    # 建立 Elements (Stairs)
    if has_stairs:
        for f in range(floors):
            y_base = f * floor_height_m
            y_mid = y_base + floor_height_m / 2.0
            y_top = (f + 1) * floor_height_m
            
            # 第一跑：從 (0, y_base, 0) 上到 (length/2, y_mid, 0)
            n_start_1 = node_map[(0.0, y_base, 0.0)]
            n_mid_1 = node_map[(length_m/2, y_mid, 0.0)]
            
            elements.append({
                "id": elem_id_counter,
                "type": "stair",
                "b": stair_width * 100, # cm
                "h": stair_thickness,   # cm
                "tread": stair_tread,   # cm
                "length": ((length_m/2)**2 + (floor_height_m/2)**2)**0.5, # 斜邊長
                "nodes": [n_start_1, n_mid_1]
            })
            elem_id_counter += 1
            
            # 休息平台：從 (length/2, y_mid, 0) 到 (length/2, y_mid, stair_width*2)
            n_mid_2 = node_map[(length_m/2, y_mid, stair_width*2)]
            elements.append({
                "id": elem_id_counter,
                "type": "stair_landing",
                "b": stair_width * 2 * 100,
                "h": stair_thickness,
                "length": length_m/2,
                "nodes": [n_mid_1, n_mid_2]
            })
            elem_id_counter += 1
            
            # 第二跑：從 (length/2, y_mid, stair_width*2) 上到 (0, y_top, width) ... 
            # 假設回到 (0, y_top, 0)，稍微偏一邊
            # 這裡為了簡化 DXF 和幾何，第二跑回到 (0, y_top, stair_width*2) 如果 width_m 夠寬的話
            # 但是原本網格可能沒有 (0, y_top, stair_width*2) 這個節點。
            # 我們就把他接回 (0.0, y_top, 0.0) 代表一個抽象的雙跑梯
            n_top_1 = node_map[(0.0, y_top, 0.0)]
            elements.append({
                "id": elem_id_counter,
                "type": "stair",
                "b": stair_width * 100,
                "h": stair_thickness,
                "tread": stair_tread,
                "length": ((length_m/2)**2 + (floor_height_m/2)**2)**0.5,
                "nodes": [n_mid_2, n_top_1]
            })
            elem_id_counter += 1

    return {
        "material": {"fc": 280, "fy": 4200},
        "nodes": nodes,
        "elements": elements
    }

if __name__ == "__main__":
    import json
    data = generate_geometry(10, 8, 3.2, 3)
    print(json.dumps(data, indent=2))
