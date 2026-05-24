import ezdxf
import math
import os
import tempfile

def round_coord(val):
    return round(val, 2)

def parse_multi_dxf_to_geometry(dxf_files, heights, is_single_file=False):
    """
    解析 DXF 檔案，合併成一個 3D 結構的 nodes 與 elements 字典
    :param dxf_files: 上傳的 file_stream 列表
    :param heights: 樓高列表
    :param is_single_file: 是否為單一檔案包含多層樓的模式
    """
    nodes = []
    elements = []
    
    node_id_counter = 1
    elem_id_counter = 1
    floor_node_maps = []
    current_y = 0.0
    
    # 若為單一檔案模式，先解析該檔案並找出基準點
    single_doc = None
    single_msp = None
    base_points = []
    
    if is_single_file and len(dxf_files) > 0:
        dxf_stream = dxf_files[0]
        fd, temp_path = tempfile.mkstemp(suffix='.dxf')
        with os.fdopen(fd, 'wb') as f:
            dxf_stream.seek(0)
            f.write(dxf_stream.read())
        single_doc = ezdxf.readfile(temp_path)
        single_msp = single_doc.modelspace()
        
        # 尋找所有 BASE_POINT 圓圈，依 X 座標排序
        for e in single_msp.query('CIRCLE[layer=="BASE_POINT"]'):
            base_points.append(e.dxf.center)
        base_points.sort(key=lambda p: p[0])
    
    scale_to_m = 1.0
    scale_detected = False
    
    for floor_idx, floor_height in enumerate(heights):
        
        if is_single_file:
            msp = single_msp
            col_layer = f"{floor_idx+1}F_COLUMNS"
            beam_layer = f"{floor_idx+1}F_BEAMS"
            if floor_idx < len(base_points):
                offset_x = base_points[floor_idx][0]
                offset_z = base_points[floor_idx][1]
            else:
                offset_x, offset_z = 0.0, 0.0
        else:
            # 多檔案模式
            dxf_stream = dxf_files[floor_idx]
            fd, temp_path = tempfile.mkstemp(suffix='.dxf')
            with os.fdopen(fd, 'wb') as f:
                dxf_stream.seek(0)
                f.write(dxf_stream.read())
            doc = ezdxf.readfile(temp_path)
            msp = doc.modelspace()
            col_layer = "COLUMNS"
            beam_layer = "BEAMS"
            offset_x, offset_z = 0.0, 0.0
            
        # 1. 抓取柱子
        floor_nodes_2d = {}
        columns_2d = []
        
        for e in msp.query(f'LWPOLYLINE[layer=="{col_layer}"]'):
            pts = e.get_points()
            if len(pts) >= 4:
                xs = [p[0] for p in pts]
                zs = [p[1] for p in pts]
                min_x, max_x = min(xs), max(xs)
                min_z, max_z = min(zs), max(zs)
                
                raw_width = max_x - min_x
                if not scale_detected and raw_width > 0:
                    if raw_width > 150: # Likely mm
                        scale_to_m = 0.001
                    elif raw_width > 15: # Likely cm
                        scale_to_m = 0.01
                    else: # Likely m
                        scale_to_m = 1.0
                    scale_detected = True
                
                cx = (min_x + max_x) / 2.0 - offset_x
                cz = (min_z + max_z) / 2.0 - offset_z
                
                cx_m = cx * scale_to_m
                cz_m = cz * scale_to_m
                
                b_cm = raw_width * scale_to_m * 100
                h_cm = (max_z - min_z) * scale_to_m * 100
                
                rx, rz = round_coord(cx_m), round_coord(cz_m)
                floor_nodes_2d[(rx, rz)] = {'b': b_cm, 'h': h_cm}
                columns_2d.append((rx, rz, b_cm, h_cm))

        # 基礎層建立 (只在 1F 時做一次)
        if floor_idx == 0:
            base_node_map = {}
            for (rx, rz) in floor_nodes_2d.keys():
                nodes.append({
                    "id": node_id_counter,
                    "x": rx, "y": 0.0, "z": rz,
                    "support": [1, 1, 1]
                })
                base_node_map[(rx, rz)] = node_id_counter
                node_id_counter += 1
            floor_node_maps.append(base_node_map)
            
        current_y += floor_height
        
        # 建立本層的 3D 節點
        current_node_map = {}
        for (rx, rz) in floor_nodes_2d.keys():
            nodes.append({
                "id": node_id_counter,
                "x": rx, "y": current_y, "z": rz,
                "support": [0, 0, 0]
            })
            current_node_map[(rx, rz)] = node_id_counter
            node_id_counter += 1
            
        # 建立柱元素 (從下層連到本層)
        prev_node_map = floor_node_maps[floor_idx]
        for (rx, rz, b_cm, h_cm) in columns_2d:
            if (rx, rz) in prev_node_map:
                n1 = prev_node_map[(rx, rz)]
                n2 = current_node_map[(rx, rz)]
                elements.append({
                    "id": elem_id_counter,
                    "type": "column",
                    "b": max(b_cm, 30),
                    "h": max(h_cm, 30),
                    "length": floor_height,
                    "nodes": [n1, n2]
                })
                elem_id_counter += 1
                
        def find_closest_node(x, z, node_map):
            best_dist = float('inf')
            best_node = None
            for (nx, nz), node_id in node_map.items():
                d = math.sqrt((x - nx)**2 + (z - nz)**2)
                if d < best_dist:
                    best_dist = d
                    best_node = node_id
            if best_dist <= 1.0: # 容許 1 米的誤差 (樑端點沒接準柱心)
                return best_node
            return None

        # 2. 抓取樑
        for e in msp.query(f'LINE[layer=="{beam_layer}"]'):
            p1 = e.dxf.start
            p2 = e.dxf.end
            
            x1_m = (p1[0] - offset_x) * scale_to_m
            z1_m = (p1[1] - offset_z) * scale_to_m
            x2_m = (p2[0] - offset_x) * scale_to_m
            z2_m = (p2[1] - offset_z) * scale_to_m
            
            n1 = find_closest_node(x1_m, z1_m, current_node_map)
            n2 = find_closest_node(x2_m, z2_m, current_node_map)
            
            if n1 and n2 and n1 != n2:
                # 計算實際節點之間的距離做為樑長度
                n1_data = next(n for n in nodes if n['id'] == n1)
                n2_data = next(n for n in nodes if n['id'] == n2)
                length_m = math.sqrt((n2_data['x']-n1_data['x'])**2 + (n2_data['z']-n1_data['z'])**2)
                
                if length_m > 0.1:
                    beam_h = min(max(int(length_m * 100 / 12), 40), 150)
                    beam_b = min(max(int(beam_h / 2), 30), 80)
                    
                    elements.append({
                        "id": elem_id_counter,
                        "type": "beam",
                        "b": beam_b,
                        "h": beam_h,
                        "length": length_m,
                        "nodes": [n1, n2],
                        "load_w": -0.05 * (beam_b/100) * (beam_h/100) * 2400
                    })
                    elem_id_counter += 1
                    
        floor_node_maps.append(current_node_map)

    return {
        "material": {"fc": 280, "fy": 4200},
        "nodes": nodes,
        "elements": elements
    }
