import ezdxf
import math

def generate_dxf_from_geometry(data, output_path="output.dxf"):
    """
    將生成的結構幾何與配筋資訊轉換為 DXF 圖檔
    包含：3D線架構、上視圖、配筋斷面詳圖、樑立面配筋圖
    """
    doc = ezdxf.new('R2010', setup=True)
    msp = doc.modelspace()
    
    # 建立圖層
    doc.layers.add("COLUMNS", color=2) # 黃色
    doc.layers.add("BEAMS", color=3)   # 綠色
    doc.layers.add("NODES", color=1)   # 紅色
    doc.layers.add("REBAR_MAIN", color=4) # 青色
    doc.layers.add("REBAR_SHEAR", color=5) # 藍色
    doc.layers.add("TEXT", color=7)    # 白色
    doc.layers.add("VIEW_BOX", color=8) # 灰色框線
    doc.layers.add("DIMENSIONS", color=6) # 洋紅色
    doc.layers.add("STAIRS", color=9)   # 淺灰色

    # --- 動態計算排版間距 ---
    # 取得結構的邊界，確保圖面不會重疊
    nodes = data.get('nodes', [])
    if not nodes:
        nodes = [{'x': 0, 'y': 0, 'z': 0}]
        
    nodes_x = [n.get('x', 0) for n in nodes]
    nodes_y = [n.get('y', 0) for n in nodes]
    nodes_z = [n.get('z', 0) for n in nodes]
    
    min_x, max_x = min(nodes_x), max(nodes_x)
    min_y, max_y = min(nodes_y), max(nodes_y)
    min_z, max_z = min(nodes_z), max(nodes_z)
    
    # 正規化所有節點座標到原點 (0,0,0)，避免 CAD 浮點數精度極限造成的卡頓與無法縮放問題
    for n in nodes:
        if 'x' in n: n['x'] -= min_x
        if 'y' in n: n['y'] -= min_y
        if 'z' in n: n['z'] -= min_z
        
    span_x = max_x - min_x
    span_z = max_z - min_z
    
    # 由於座標已經平移到原點，繪圖基準點為 0
    base_x = 0
    base_z = 0
    
    # 設定每個區塊的安全間隔 (至少 50m)
    spacing_x = max(span_x * 1.5, 50)
    spacing_y = max(span_z * 1.5, 50)

    # --- 1. 繪製 3D 模型 (原點附近) ---
    draw_3d_frame(msp, data, offset=(0, 0, 0))
    msp.add_text("3D Structure Frame", dxfattribs={'height': 1.0, 'layer': 'TEXT'}).set_placement((base_x - 2, base_z - 5))

    # --- 2. 繪製上視圖 (X向平移) ---
    draw_top_view(msp, data, offset=(spacing_x, 0, 0))
    msp.add_text("Top View (Plan)", dxfattribs={'height': 1.0, 'layer': 'TEXT'}).set_placement((base_x + spacing_x - 2, base_z - 5))

    # --- 3. 繪製配筋斷面詳圖 (X向平移 2 倍) ---
    draw_rebar_sections(msp, data, offset=(span_x + spacing_x * 2, base_z, 0))
    msp.add_text("Rebar Details", dxfattribs={'height': 1.0, 'layer': 'TEXT'}).set_placement((span_x + spacing_x * 2 - 2, base_z - 5))

    # --- 4. 繪製樑立面配筋詳圖 (Y向平移向下) ---
    final_y = draw_beam_elevation(msp, data, offset=(base_x, base_z - spacing_y, 0))

    # --- 5. 繪製樓梯單層配筋詳圖 (在樑詳圖的下方) ---
    stair_y_offset = final_y - 20 if final_y is not None else base_z - spacing_y * 1.5
    draw_stair_section(msp, data, offset=(base_x, stair_y_offset, 0))
    msp.add_text("Stair Rebar Details (Single Layer)", dxfattribs={'height': 1.0, 'layer': 'TEXT'}).set_placement((base_x - 2, stair_y_offset - 5))

    # --- 設定開啟時的預設視角與縮放 (Zoom Extents) ---
    # 計算中心點與大概的高度
    center_x = base_x + span_x / 2 + spacing_x / 2
    center_y = base_z - spacing_y / 2
    view_height = spacing_y * 2.5
    doc.set_modelspace_vport(height=view_height, center=(center_x, center_y))

    doc.saveas(output_path)
    return output_path


def draw_3d_frame(msp, data, offset=(0,0,0)):
    node_coords = {}
    for n in data.get('nodes', []):
        nx, ny, nz = n['x'] + offset[0], n['y'] + offset[1], n['z'] + offset[2]
        node_coords[n['id']] = (nx, ny, nz)
        msp.add_point((nx, ny, nz), dxfattribs={'layer': 'NODES'})

    for elem in data.get('elements', []):
        n1_id = elem['nodes'][0]
        n2_id = elem['nodes'][1]
        if n1_id in node_coords and n2_id in node_coords:
            p1 = node_coords[n1_id]
            p2 = node_coords[n2_id]
            if elem.get('type') == 'column':
                layer_name = "COLUMNS"
            elif elem.get('type') == 'beam':
                layer_name = "BEAMS"
            else:
                layer_name = "STAIRS"
            msp.add_line(p1, p2, dxfattribs={'layer': layer_name})


def draw_top_view(msp, data, offset=(20,0,0)):
    node_coords = {}
    for n in data.get('nodes', []):
        nx = n['x'] + offset[0]
        ny = n['z'] + offset[1] 
        node_coords[n['id']] = (nx, ny)

    for elem in data.get('elements', []):
        n1_id = elem['nodes'][0]
        n2_id = elem['nodes'][1]
        if n1_id not in node_coords or n2_id not in node_coords:
            continue
            
        p1 = node_coords[n1_id]
        p2 = node_coords[n2_id]
        
        if elem.get('type') == 'column':
            b_m = elem['b'] / 100.0
            h_m = elem['h'] / 100.0
            cx, cy = p1[0], p1[1]
            pts = [
                (cx - b_m/2, cy - h_m/2), (cx + b_m/2, cy - h_m/2),
                (cx + b_m/2, cy + h_m/2), (cx - b_m/2, cy + h_m/2),
                (cx - b_m/2, cy - h_m/2)
            ]
            msp.add_lwpolyline(pts, dxfattribs={'layer': 'COLUMNS'})
            
        elif elem.get('type') == 'beam':
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            b_m = elem['b'] / 100.0
            if abs(dx) > abs(dy):
                msp.add_line((p1[0], p1[1] - b_m/2), (p2[0], p2[1] - b_m/2), dxfattribs={'layer': 'BEAMS'})
                msp.add_line((p1[0], p1[1] + b_m/2), (p2[0], p2[1] + b_m/2), dxfattribs={'layer': 'BEAMS'})
            else:
                msp.add_line((p1[0] - b_m/2, p1[1]), (p2[0] - b_m/2, p2[1]), dxfattribs={'layer': 'BEAMS'})
                msp.add_line((p1[0] + b_m/2, p1[1]), (p2[0] + b_m/2, p2[1]), dxfattribs={'layer': 'BEAMS'})
                
            # Add label
            beam_label = f"B{elem.get('id', '')}"
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2
            msp.add_text(beam_label, dxfattribs={'height': 0.5, 'layer': 'TEXT'}).set_placement((mid_x, mid_y + b_m))
                
        elif elem.get('type') in ['stair', 'stair_landing']:
            # 簡單畫一條中心虛線與外框代表樓梯
            msp.add_line(p1, p2, dxfattribs={'layer': 'STAIRS', 'linetype': 'DASHED'})
            b_m = elem['b'] / 100.0
            # 簡化：只畫 X 向梯
            msp.add_line((p1[0], p1[1] - b_m/2), (p2[0], p2[1] - b_m/2), dxfattribs={'layer': 'STAIRS'})
            msp.add_line((p1[0], p1[1] + b_m/2), (p2[0], p2[1] + b_m/2), dxfattribs={'layer': 'STAIRS'})
            # 如果是樓梯段，畫幾條踏步線代表
            if elem.get('type') == 'stair':
                for i in range(1, 5):
                    step_x = p1[0] + (p2[0]-p1[0]) * (i/5.0)
                    step_y = p1[1] + (p2[1]-p1[1]) * (i/5.0)
                    msp.add_line((step_x, step_y - b_m/2), (step_x, step_y + b_m/2), dxfattribs={'layer': 'STAIRS'})


def draw_rebar_sections(msp, data, offset=(40,0,0)):
    unique_sections = {}
    for elem in data.get('elements', []):
        if elem.get('type') in ['stair', 'stair_landing']:
            continue
            
        if 'num_bars' not in elem:
            elem['num_bars'] = 8
            elem['shear_spacing'] = 15
        key = f"{elem['type']}_{elem['b']}x{elem['h']}_{elem['num_bars']}bars"
        if key not in unique_sections:
            unique_sections[key] = elem

    x_cursor, y_cursor = offset[0], offset[1]
    max_height_in_row = 0
    scale = 10
    
    for key, elem in unique_sections.items():
        b_m = (elem['b'] / 100.0) * scale
        h_m = (elem['h'] / 100.0) * scale
        cover = (4.0 / 100.0) * scale
        
        pts_concrete = [(x_cursor, y_cursor), (x_cursor + b_m, y_cursor), (x_cursor + b_m, y_cursor + h_m), (x_cursor, y_cursor + h_m), (x_cursor, y_cursor)]
        msp.add_lwpolyline(pts_concrete, dxfattribs={'layer': 'VIEW_BOX'})
        
        pts_shear = [(x_cursor + cover, y_cursor + cover), (x_cursor + b_m - cover, y_cursor + cover), (x_cursor + b_m - cover, y_cursor + h_m - cover), (x_cursor + cover, y_cursor + h_m - cover), (x_cursor + cover, y_cursor + cover)]
        msp.add_lwpolyline(pts_shear, dxfattribs={'layer': 'REBAR_SHEAR'})
        
        num_bars = elem['num_bars']
        rebar_radius = (2.54 / 2 / 100.0) * scale
        
        top_bars = math.ceil(num_bars / 2)
        bottom_bars = num_bars - top_bars
        
        for i in range(bottom_bars):
            bx = x_cursor + cover + rebar_radius + i * ((b_m - 2*cover - 2*rebar_radius) / (bottom_bars - 1)) if bottom_bars > 1 else x_cursor + b_m / 2
            by = y_cursor + cover + rebar_radius
            msp.add_circle((bx, by), rebar_radius, dxfattribs={'layer': 'REBAR_MAIN'})
            
        for i in range(top_bars):
            bx = x_cursor + cover + rebar_radius + i * ((b_m - 2*cover - 2*rebar_radius) / (top_bars - 1)) if top_bars > 1 else x_cursor + b_m / 2
            by = y_cursor + h_m - cover - rebar_radius
            msp.add_circle((bx, by), rebar_radius, dxfattribs={'layer': 'REBAR_MAIN'})

        label = f"{'Column' if elem['type']=='column' else 'Beam'} {elem['b']}x{elem['h']} cm"
        msp.add_text(label, dxfattribs={'height': 0.4, 'layer': 'TEXT'}).set_placement((x_cursor, y_cursor - 0.6))
        msp.add_text(f"Main: {num_bars}-#8", dxfattribs={'height': 0.3, 'layer': 'TEXT'}).set_placement((x_cursor, y_cursor - 1.1))
        msp.add_text(f"Shear: #3 @ {elem['shear_spacing']} cm", dxfattribs={'height': 0.3, 'layer': 'TEXT'}).set_placement((x_cursor, y_cursor - 1.6))
        
        x_cursor += (b_m + 3)
        max_height_in_row = max(max_height_in_row, h_m)
        if x_cursor > offset[0] + 30:
            x_cursor = offset[0]
            y_cursor += (max_height_in_row + 4)
            max_height_in_row = 0

def draw_beam_elevation(msp, data, offset=(0, -15, 0)):
    """
    繪製所有樑立面配筋詳圖 (縱向剖面)
    使用 cm 為單位。
    """
    beams = [e for e in data.get('elements', []) if e.get('type') == 'beam']
    if not beams: return offset[1]
    
    msp.add_text("Beam Elevation Details", dxfattribs={'height': 1.0, 'layer': 'TEXT'}).set_placement((offset[0] - 2, offset[1] - 5))
    
    # 單位轉換為公尺(m)來在 DXF 中縮放，但標註文字寫 cm
    # 這裡我們用 1:1 cm 來畫在 DXF 裡比較好計算
    scale_factor = 0.05 # 將 cm 縮小一點放進圖紙
    col_width_cm = 60 # 假設柱寬 60cm
    
    current_y_offset = offset[1] - 15
    
    for beam in beams:
        L_cm = beam['length'] * 100
        h_cm = beam['h']
        b_cm = beam['b']
        
        ox, oy = offset[0], current_y_offset
        
        def pt(x_cm, y_cm):
            return (ox + x_cm * scale_factor, oy + y_cm * scale_factor)
            
        # Add a title for the beam
        beam_title = f"Beam Elevation: B{beam.get('id', '')} ({b_cm}x{h_cm} cm, L={beam['length']}m)"
        msp.add_text(beam_title, dxfattribs={'height': 0.8, 'layer': 'TEXT'}).set_placement(pt(0, h_cm + 20))
        
        # 1. 繪製混凝土邊界
        # 樑
        msp.add_lwpolyline([pt(0, 0), pt(L_cm, 0), pt(L_cm, h_cm), pt(0, h_cm), pt(0, 0)], dxfattribs={'layer': 'VIEW_BOX'})
        # 左柱
        msp.add_line(pt(-col_width_cm, -h_cm), pt(-col_width_cm, 2*h_cm), dxfattribs={'layer': 'VIEW_BOX'})
        msp.add_line(pt(0, -h_cm), pt(0, 2*h_cm), dxfattribs={'layer': 'VIEW_BOX'})
        # 右柱
        msp.add_line(pt(L_cm, -h_cm), pt(L_cm, 2*h_cm), dxfattribs={'layer': 'VIEW_BOX'})
        msp.add_line(pt(L_cm + col_width_cm, -h_cm), pt(L_cm + col_width_cm, 2*h_cm), dxfattribs={'layer': 'VIEW_BOX'})

        # 2. 繪製主筋 (預設配置)
        cover = 4 # cm
        hook_len = 20 # 彎鉤長度 cm
        total_bars = beam.get('num_bars', 8)
        # 耐震分配：頂層端部 5，中央 3。底層端部 3，中央 5。
        top_end_bars, top_mid_bars = 5, 3
        bot_end_bars, bot_mid_bars = 3, 5
        bar_size = "#8"
        
        # 上層主筋
        top_y = h_cm - cover
        # 貫通筋
        msp.add_lwpolyline([pt(-col_width_cm + cover, top_y - hook_len), pt(-col_width_cm + cover, top_y), 
                            pt(L_cm + col_width_cm - cover, top_y), pt(L_cm + col_width_cm - cover, top_y - hook_len)], 
                           dxfattribs={'layer': 'REBAR_MAIN'})
                           
        # 下層主筋
        bot_y = cover
        msp.add_lwpolyline([pt(-col_width_cm + cover, bot_y + hook_len), pt(-col_width_cm + cover, bot_y), 
                            pt(L_cm + col_width_cm - cover, bot_y), pt(L_cm + col_width_cm - cover, bot_y + hook_len)], 
                           dxfattribs={'layer': 'REBAR_MAIN'})

        # 3. 繪製箍筋 (圍束區 2h，其餘中央區)
        conf_zone = min(2 * h_cm, L_cm / 4)
        mid_zone = max(L_cm - 2 * conf_zone, 0)
        s_conf = 10 # 圍束區間距 10cm
        s_mid = 15  # 中央區間距 15cm
        
        # 畫垂直虛線代表箍筋 (限制最多畫 1000 根避免座標異常導致無窮迴圈或當機)
        def draw_stirrups(start_x, end_x, spacing):
            x = start_x + spacing/2
            count = 0
            while x < end_x and count < 1000:
                msp.add_line(pt(x, cover), pt(x, h_cm - cover), dxfattribs={'layer': 'REBAR_SHEAR', 'linetype': 'DASHED'})
                x += spacing
                count += 1

        draw_stirrups(0, conf_zone, s_conf)
        draw_stirrups(conf_zone, L_cm - conf_zone, s_mid)
        draw_stirrups(L_cm - conf_zone, L_cm, s_conf)

        # 4. 文字引線標註
        text_h = 0.3
        # 上部鋼筋標示
        msp.add_line(pt(conf_zone/2, top_y), pt(conf_zone/2, top_y + 30), dxfattribs={'layer': 'TEXT'})
        msp.add_line(pt(conf_zone/2, top_y + 30), pt(conf_zone/2 + 20, top_y + 30), dxfattribs={'layer': 'TEXT'})
        msp.add_text(f"{top_end_bars}-{bar_size}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(conf_zone/2 + 2, top_y + 32))
        
        msp.add_line(pt(L_cm/2, top_y), pt(L_cm/2, top_y + 30), dxfattribs={'layer': 'TEXT'})
        msp.add_line(pt(L_cm/2, top_y + 30), pt(L_cm/2 + 20, top_y + 30), dxfattribs={'layer': 'TEXT'})
        msp.add_text(f"{top_mid_bars}-{bar_size}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(L_cm/2 + 2, top_y + 32))

        # 箍筋標示
        msp.add_text(f"☐ #3@{s_conf}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(conf_zone/2 - 20, h_cm/2))
        msp.add_text(f"☐ #3@{s_mid}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(L_cm/2 - 20, h_cm/2))
        msp.add_text(f"☐ #3@{s_conf}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(L_cm - conf_zone/2 - 20, h_cm/2))

        # 5. 尺寸標註 (DIMENSIONS)
        dim_y = -30
        # 左柱
        msp.add_line(pt(-col_width_cm, -h_cm), pt(-col_width_cm, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
        msp.add_line(pt(0, -h_cm), pt(0, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
        msp.add_line(pt(-col_width_cm, dim_y), pt(0, dim_y), dxfattribs={'layer': 'DIMENSIONS'})
        msp.add_text(f"{col_width_cm}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(-col_width_cm/2 - 10, dim_y + 5))
        
        # 樑段
        msp.add_line(pt(conf_zone, 0), pt(conf_zone, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
        msp.add_line(pt(L_cm - conf_zone, 0), pt(L_cm - conf_zone, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
        msp.add_line(pt(L_cm, -h_cm), pt(L_cm, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
        
        # 畫水平尺寸線
        msp.add_line(pt(0, dim_y), pt(L_cm, dim_y), dxfattribs={'layer': 'DIMENSIONS'})
        
        # 尺寸數字
        msp.add_text(f"{int(conf_zone)}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(conf_zone/2 - 10, dim_y + 5))
        msp.add_text(f"{int(mid_zone)}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(L_cm/2 - 10, dim_y + 5))
        msp.add_text(f"{int(conf_zone)}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(L_cm - conf_zone/2 - 10, dim_y + 5))

        # Update Y offset for the next beam (give 15 units of space)
        current_y_offset -= (h_cm * scale_factor + 15)
        
    return current_y_offset

def draw_stair_section(msp, data, offset=(0, -30, 0)):
    """
    繪製樓梯版的單層配筋詳圖
    """
    stair = next((e for e in data.get('elements', []) if e.get('type') == 'stair'), None)
    if not stair: return
    
    scale_factor = 0.05
    ox, oy = offset[0], offset[1]
    
    b_cm = stair['b'] # 梯寬
    h_cm = stair['h'] # 梯厚
    cover = 3 # 樓梯保護層通常 3cm
    
    def pt(x_cm, y_cm):
        return (ox + x_cm * scale_factor, oy + y_cm * scale_factor)
        
    # 畫混凝土斷面 (顯示梯寬與梯厚)
    msp.add_lwpolyline([pt(0, 0), pt(b_cm, 0), pt(b_cm, h_cm), pt(0, h_cm), pt(0, 0)], dxfattribs={'layer': 'VIEW_BOX'})
    
    # 畫單層雙向主筋 (放中間)
    mid_y = h_cm / 2
    
    # 橫向分佈筋 (直線)
    msp.add_line(pt(cover, mid_y), pt(b_cm - cover, mid_y), dxfattribs={'layer': 'REBAR_MAIN'})
    
    # 縱向主筋 (圓點)
    num_main = math.ceil(b_cm / 15.0) + 1
    spacing = (b_cm - 2*cover) / (num_main - 1) if num_main > 1 else b_cm/2
    
    for i in range(num_main):
        cx = cover + i * spacing
        msp.add_circle(pt(cx, mid_y), 0.6 * scale_factor, dxfattribs={'layer': 'REBAR_MAIN'})
        
    # 文字標示
    text_h = 0.3
    msp.add_text(f"Stair Slab {b_cm}x{h_cm} cm", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(0, h_cm + 5))
    msp.add_text("Main Rebar: #4 @ 15cm (Single Layer)", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(0, h_cm + 15))
    msp.add_text("Dist Rebar: #3 @ 20cm", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(0, h_cm + 25))
    
    # 畫尺寸
    dim_y = -20
    msp.add_line(pt(0, 0), pt(0, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
    msp.add_line(pt(b_cm, 0), pt(b_cm, dim_y - 10), dxfattribs={'layer': 'DIMENSIONS'})
    msp.add_line(pt(0, dim_y), pt(b_cm, dim_y), dxfattribs={'layer': 'DIMENSIONS'})
    msp.add_text(f"{b_cm}", dxfattribs={'height': text_h, 'layer': 'TEXT'}).set_placement(pt(b_cm/2 - 10, dim_y + 5))

if __name__ == "__main__":
    import json
    with open('ai_design_output.json', 'r') as f:
        data = json.load(f)
    generate_dxf_from_geometry(data, "test_structure.dxf")
    print("DXF generated with beam elevation!")
