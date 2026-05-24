import math

def calculate_rebar(b, h, Mu_kgf_cm, Vu_kgf, Pu_kgf=0, fc=280, fy=4200, elem_type='beam'):
    """
    根據 ACI 318 / 台灣結構混凝土設計規範進行配筋計算
    :param b: 斷面寬度 (cm)
    :param h: 斷面深度 (cm)
    :param Mu_kgf_cm: 設計彎矩 (kgf-cm)
    :param Vu_kgf: 設計剪力 (kgf)
    :param Pu_kgf: 設計軸力 (kgf) (受壓為正)
    :param fc: 混凝土抗壓強度 (kgf/cm^2)
    :param fy: 鋼筋降伏強度 (kgf/cm^2)
    :param elem_type: 構件種類 ('beam' 或 'column')
    """
    # 有效深度 d 估算：假設保護層(4cm) + 箍筋(#3約1cm) + 主筋半徑(#8約1.27cm) 約為 6.5 cm
    d = h - 6.5
    if d <= 0:
        d = h * 0.8 # 防呆容錯
        
    phi_v = 0.75 # 剪力折減係數
    
    # 假設使用 #8 主筋, #3 箍筋
    db_main = 2.54 # cm
    area_bar = 5.07 # cm^2
    db_tie = 0.95 # cm
    Av = 1.42 # 雙股 #3 面積
    
    # -----------------------------------
    # 1. 計算主筋數量 (Main Rebar)
    # -----------------------------------
    if elem_type == 'column':
        # 柱子: 必須考慮軸力與彎矩，折減係數通常較低
        phi_c = 0.65 # 橫箍柱為0.65 (螺箍為0.75)
        # 最小配筋率 1%，最大 8% (實務常限制在 4% 以下避免擁擠)
        rho_min = 0.01
        rho_max = 0.08
        
        Mu = abs(Mu_kgf_cm)
        Pu = abs(Pu_kgf)
        
        # 使用極度簡化型 P-M 交互估算 As_req
        # 先以大偏心(彎矩為主)估算拉力鋼筋
        Rn = Mu / (0.9 * b * (d ** 2)) 
        discriminant = 1 - (2 * Rn) / (0.85 * fc)
        if discriminant >= 0:
            rho_flexure = (0.85 * fc / fy) * (1 - math.sqrt(discriminant))
        else:
            rho_flexure = 0.02
            
        As_flexure = rho_flexure * b * d
        As_req = max(As_flexure, rho_min * b * h)
        
        # 檢查軸力容量 (近似估算純壓能力極限)，若不足則增加鋼筋
        Pu_max = 0.8 * phi_c * (0.85 * fc * b * h + fy * As_req)
        if Pu > Pu_max:
            # 軸力過大，簡化補償所需鋼筋面積
            As_req = (Pu / (0.8 * phi_c) - 0.85 * fc * b * h) / (fy - 0.85 * fc)
            As_req = max(As_req, rho_min * b * h)
        
        # 確保不超過最大配筋率 8%
        As_req = min(As_req, rho_max * b * h) 
        
    else:
        # 梁: 純彎矩計算
        phi_b = 0.9 
        Mu = abs(Mu_kgf_cm)
        Rn = Mu / (phi_b * b * (d ** 2))
        
        # 計算梁的最大拉應變限制 (epsilon_t >= 0.004) 推導之最大配筋率
        beta1 = 0.85 if fc <= 280 else max(0.65, 0.85 - 0.05 * (fc - 280) / 70)
        rho_max_beam = 0.85 * beta1 * (fc / fy) * (0.003 / (0.003 + 0.004))
        
        discriminant = 1 - (2 * Rn) / (0.85 * fc)
        if discriminant < 0:
            rho = rho_max_beam # 超出單筋極限，實務應改用雙筋設計
        else:
            rho = (0.85 * fc / fy) * (1 - math.sqrt(discriminant))
            
        # 梁最小配筋率檢查
        rho_min_beam = max(14 / fy, 0.8 * math.sqrt(fc) / fy)
        
        rho = max(min(rho, rho_max_beam), rho_min_beam)
        As_req = rho * b * d

    num_bars = math.ceil(As_req / area_bar)
    
    # 規範要求矩形柱至少 4 根主筋
    if elem_type == 'column' and num_bars < 4:
        num_bars = 4 
        
    # -----------------------------------
    # 2. 計算剪力筋間距 (Shear Spacing)
    # -----------------------------------
    Vu = abs(Vu_kgf)
    
    # 混凝土提供之剪力強度 Vc (公斤力)
    if elem_type == 'column' and Pu_kgf > 0:
        # 柱子有受壓時，Vc 會因為軸力而提高
        Vc = 0.53 * (1 + Pu_kgf / (140 * b * h)) * math.sqrt(fc) * b * d
    else:
        Vc = 0.53 * math.sqrt(fc) * b * d
        
    Vs = max((Vu / phi_v) - Vc, 0)
    
    # 規範最大間距 (考量基本規範，未加入全套塑性鉸區細部規定)
    if elem_type == 'column':
        # 柱的橫箍筋間距限制 (一般區)
        max_spacing = min(16 * db_main, 48 * db_tie, min(b, h))
    else:
        # 梁剪力筋最大間距
        # 若 Vs 過大，間距須減半
        if Vs > 1.06 * math.sqrt(fc) * b * d:
            max_spacing = min(d / 4, 30.0)
        else:
            max_spacing = min(d / 2, 60.0)
            
    if Vs <= 0:
        spacing = max_spacing
    else:
        spacing = (Av * fy * d) / Vs
        spacing = min(spacing, max_spacing)
        
    spacing = max(math.floor(spacing), 10.0) # 取整數，且不小於 10cm 施工極限
    
    # -----------------------------------
    # 3. 計算鋼筋搭接長度 (Lap Splice Length)
    # -----------------------------------
    # 簡化公式：Ld = (0.28 * fy / sqrt(fc)) * db (針對無足夠保護層折減之偏保守估計)
    Ld = (0.28 * fy / math.sqrt(fc)) * db_main
    lap_length = 1.3 * Ld # B級搭接 (實務最常見)
    lap_length = max(math.ceil(lap_length), 30.0)
    
    return {
        "As_req": round(As_req, 2),
        "num_bars": num_bars,
        "bar_size": "#8",
        "shear_spacing": int(spacing),
        "lap_length": int(lap_length)
    }

def calculate_element_materials(b_cm, h_cm, length_m, num_bars, shear_spacing_cm):
    """計算單一構件的混凝土體積與鋼筋重量"""
    b_m = b_cm / 100.0
    h_m = h_cm / 100.0
    volume_m3 = b_m * h_m * length_m
    
    main_weight_kg = num_bars * length_m * 3.98 # #8鋼筋每公尺重量
    
    shear_spacing_m = shear_spacing_cm / 100.0
    num_shear_bars = int(length_m / shear_spacing_m) + 1
    single_shear_len = 2 * (b_m + h_m)
    shear_weight_kg = num_shear_bars * single_shear_len * 0.56 # #3鋼筋每公尺重量
    
    return {
        "volume_m3": round(volume_m3, 3),
        "rebar_weight_kg": round(main_weight_kg + shear_weight_kg, 2)
    }

def calculate_stair_materials(b_cm, h_cm, length_m):
    """計算樓梯版(單層配筋)的混凝土體積與鋼筋重量"""
    b_m = b_cm / 100.0
    h_m = h_cm / 100.0
    volume_m3 = b_m * h_m * length_m
    
    # 樓梯版使用 #4@15cm(主筋) 及 #3@20cm(分佈筋)
    num_main_bars = math.ceil(b_cm / 15.0) + 1
    main_weight_kg = num_main_bars * length_m * 0.99
    
    num_dist_bars = math.ceil((length_m * 100) / 20.0) + 1
    dist_weight_kg = num_dist_bars * b_m * 0.56
    
    rebar_area_cm2 = num_main_bars * 1.29 + num_dist_bars * 0.71
    
    return {
        "volume_m3": round(volume_m3, 3),
        "rebar_weight_kg": round(main_weight_kg + dist_weight_kg, 2),
        "rebar_area_cm2": round(rebar_area_cm2, 2)
    }

if __name__ == "__main__":
    res_beam = calculate_rebar(b=40, h=60, Mu_kgf_cm=1500000, Vu_kgf=20000, elem_type='beam')
    print("梁配筋結果:", res_beam)
    
    res_col = calculate_rebar(b=50, h=50, Mu_kgf_cm=2000000, Vu_kgf=20000, Pu_kgf=150000, elem_type='column')
    print("柱配筋結果:", res_col)
