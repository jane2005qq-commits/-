document.addEventListener('DOMContentLoaded', () => {
    const runAiBtn = document.getElementById('run-ai-btn');
    const downloadBtn = document.getElementById('download-dxf-btn');
    const tableBody = document.getElementById('table-body');
    const canvas = document.getElementById('structure-canvas');
    const ctx = canvas.getContext('2d');
    const overlayMsg = document.getElementById('canvas-overlay');
    const complianceAlert = document.getElementById('compliance-alert');
    const alertList = document.getElementById('alert-list');
    
    // Inputs
    const dimX = document.getElementById('dim-x');
    const dimZ = document.getElementById('dim-z');
    const dimY = document.getElementById('dim-y');
    const floors = document.getElementById('floors');

    // Stairs
    const hasStairs = document.getElementById('has-stairs');
    const stairWidth = document.getElementById('stair-width');
    const stairTread = document.getElementById('stair-tread');
    const stairThickness = document.getElementById('stair-thickness');

    // Summary
    const materialSummary = document.getElementById('material-summary');
    const totalConcrete = document.getElementById('total-concrete');
    const totalRebar = document.getElementById('total-rebar');

    // Tabs & Modes
    let currentMode = 'parametric';
    const tabParametric = document.getElementById('tab-parametric');
    const tabCad = document.getElementById('tab-cad');
    const modeParametric = document.getElementById('mode-parametric');
    const modeCad = document.getElementById('mode-cad');

    tabParametric.addEventListener('click', () => {
        currentMode = 'parametric';
        tabParametric.classList.add('active');
        tabCad.classList.remove('active');
        modeParametric.classList.add('active');
        modeCad.style.display = 'none';
    });

    tabCad.addEventListener('click', () => {
        currentMode = 'cad';
        tabCad.classList.add('active');
        tabParametric.classList.remove('active');
        modeCad.style.display = 'block';
        modeParametric.classList.remove('active');
    });

    // CAD 上傳模式切換
    const uploadModeRadios = document.querySelectorAll('input[name="upload-mode"]');
    const multiFileSection = document.getElementById('multi-file-section');
    const singleFileSection = document.getElementById('single-file-section');
    let cadUploadMode = 'multi';

    uploadModeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            cadUploadMode = e.target.value;
            if (cadUploadMode === 'multi') {
                multiFileSection.style.display = 'block';
                singleFileSection.style.display = 'none';
            } else {
                multiFileSection.style.display = 'none';
                singleFileSection.style.display = 'block';
            }
        });
    });

    // 單一檔案模式：樓高設定
    const singleFloorHeights = document.getElementById('single-floor-heights');
    const addSingleHeightBtn = document.getElementById('add-single-height-btn');
    let singleHeightCounter = 0;

    function addSingleHeightItem() {
        singleHeightCounter++;
        const id = singleHeightCounter;
        const div = document.createElement('div');
        div.className = 'floor-item';
        div.id = `single-height-item-${id}`;
        div.style.padding = "0.5rem 1rem";
        div.style.marginTop = "0.5rem";
        div.innerHTML = `
            <div class="input-group" style="flex: 1;">
                <label>${id}F 樓高 (m)</label>
                <input type="number" id="single-height-${id}" value="3.2" min="2.0" step="0.1" required>
            </div>
            <button class="btn-remove" onclick="document.getElementById('single-height-item-${id}').remove()">移除</button>
        `;
        singleFloorHeights.appendChild(div);
    }
    
    // 初始化單一檔案的預設樓高
    addSingleHeightItem();
    addSingleHeightBtn.addEventListener('click', addSingleHeightItem);

    // 多檔案模式：樓層設定
    const floorList = document.getElementById('floor-list');
    const addFloorBtn = document.getElementById('add-floor-btn');
    let floorCounter = 0;

    function addFloorItem() {
        floorCounter++;
        const id = floorCounter;
        const div = document.createElement('div');
        div.className = 'floor-item';
        div.id = `floor-item-${id}`;
        div.innerHTML = `
            <div class="input-group" style="flex: 1;">
                <label>樓層 ${id} 檔案 (.dxf)</label>
                <input type="file" id="floor-file-${id}" accept=".dxf" required>
            </div>
            <div class="input-group" style="width: 100px;">
                <label>樓高 (m)</label>
                <input type="number" id="floor-height-${id}" value="3.2" min="2.0" step="0.1" required>
            </div>
            <button class="btn-remove" onclick="document.getElementById('floor-item-${id}').remove()">移除</button>
        `;
        floorList.appendChild(div);
    }
    
    // 初始化加一層
    addFloorItem();
    addFloorBtn.addEventListener('click', addFloorItem);

    function drawGrid() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        for (let x = 0; x <= canvas.width; x += 40) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
        }
        for (let y = 0; y <= canvas.height; y += 40) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
        }
    }

    drawGrid();

    runAiBtn.addEventListener('click', async () => {
        runAiBtn.textContent = "與伺服器運算中...";
        runAiBtn.disabled = true;
        overlayMsg.textContent = "生成設計中...";
        overlayMsg.style.opacity = 1;

        try {
            let res;
            if (currentMode === 'parametric') {
                const x = parseFloat(dimX.value);
                const z = parseFloat(dimZ.value);
                const y = parseFloat(dimY.value);
                const f = parseInt(floors.value);

                if (!x || !z || !y || !f || x <= 0 || z <= 0 || y <= 0 || f <= 0) {
                    throw new Error("請輸入有效的空間尺寸參數！");
                }
                
                const payload = { 
                    length: x, 
                    width: z, 
                    height: y, 
                    floors: f,
                    has_stairs: hasStairs.checked,
                    stair_width: parseFloat(stairWidth.value) || 1.2,
                    stair_tread: parseFloat(stairTread.value) || 25,
                    stair_thickness: parseFloat(stairThickness.value) || 15
                };
                
                res = await fetch('/api/generate_design', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
            } else {
                // CAD 上傳模式
                const formData = new FormData();
                let heights = [];
                
                if (cadUploadMode === 'multi') {
                    formData.append('is_single_file', 'false');
                    const floorItems = floorList.querySelectorAll('.floor-item');
                    if (floorItems.length === 0) {
                        throw new Error("請至少新增一個樓層並選擇檔案！");
                    }
                    
                    for (let i = 0; i < floorItems.length; i++) {
                        const item = floorItems[i];
                        const fileInput = item.querySelector('input[type="file"]');
                        const heightInput = item.querySelector('input[type="number"]');
                        
                        if (!fileInput.files[0]) {
                            throw new Error(`請為所有樓層選擇 DXF 檔案！`);
                        }
                        
                        formData.append('dxf_files', fileInput.files[0]);
                        heights.push(parseFloat(heightInput.value));
                    }
                } else {
                    // 單一檔案模式
                    formData.append('is_single_file', 'true');
                    const singleFileInput = document.getElementById('single-file-input');
                    if (!singleFileInput.files[0]) {
                        throw new Error("請選擇一個包含所有樓層的 DXF 檔案！");
                    }
                    formData.append('dxf_files', singleFileInput.files[0]);
                    
                    const heightItems = singleFloorHeights.querySelectorAll('.floor-item input[type="number"]');
                    if (heightItems.length === 0) {
                        throw new Error("請至少定義一個樓層的高度！");
                    }
                    heightItems.forEach(input => {
                        heights.push(parseFloat(input.value));
                    });
                }
                
                formData.append('heights', JSON.stringify(heights));
                
                res = await fetch('/api/upload_dxf_multi', {
                    method: 'POST',
                    body: formData
                });
            }
            
            if (!res.ok) throw new Error("API 錯誤或檔案解析失敗");
            const data = await res.json();
            
            renderData(data.elements, data.issues);
            
            // 顯示材料用量
            materialSummary.style.display = 'grid';
            totalConcrete.textContent = data.total_concrete_volume.toFixed(2);
            totalRebar.textContent = data.total_rebar_weight_ton.toFixed(2);
            
            // 顯示下載按鈕
            downloadBtn.style.display = 'inline-block';
            downloadBtn.onclick = (e) => {
                e.preventDefault();
                // 從 base64 解碼檔案內容
                const byteCharacters = atob(data.dxf_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {type: 'application/dxf'});
                
                // 建立下載連結並觸發
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'structure.dxf';
                document.body.appendChild(a);
                a.click();
                
                // 清理
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            };
            // 簡單處理 2D 視覺化: 取最高樓高跟總樓層畫圖
            let h = 3.2, f = 3;
            if(currentMode === 'parametric') {
                 h = parseFloat(dimY.value);
                 f = parseInt(floors.value);
            } else {
                 f = floorList.querySelectorAll('.floor-item').length;
            }
            drawProcessedStructure(10, 8, h, f);
            overlayMsg.style.opacity = 0;
            
        } catch (err) {
            console.error(err);
            alert(err.message || "連接伺服器失敗，請確認已啟動 server.py");
        } finally {
            runAiBtn.textContent = "生成設計與分析";
            runAiBtn.disabled = false;
        }
    });

    function renderData(elements, issues) {
        tableBody.innerHTML = '';
        alertList.innerHTML = '';
        let hasErrors = issues && issues.length > 0;

        elements.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.style.animation = `fadeIn 0.3s ease-out ${index * 0.05}s forwards`;
            tr.style.opacity = 0;
            
            const itemIssues = issues.filter(i => i.includes(` ${item.id}`));
            const isError = itemIssues.length > 0;
            
            const statusClass = isError ? 'status-error' : 'status-ok';
            const statusIcon = isError ? '⚠️' : '✅';
            
            let msg = '合規';
            if (isError) {
                msg = itemIssues[0].split(':').slice(1).join(':').trim() || '不合規';
            }

            const rho = item.rebar_area ? ((item.rebar_area / (item.b * item.h)) * 100).toFixed(2) + '%' : 'N/A';

            tr.innerHTML = `
                <td>${item.id}</td>
                <td>${item.type === 'column' ? '柱' : '樑'}</td>
                <td>${item.b} x ${item.h}</td>
                <td>${rho}</td>
                <td class="${statusClass}">${statusIcon} ${msg}</td>
            `;
            tableBody.appendChild(tr);
        });

        if (hasErrors) {
            issues.forEach(issue => {
                const li = document.createElement('li');
                li.textContent = issue;
                alertList.appendChild(li);
            });
        }
        complianceAlert.style.display = hasErrors ? 'block' : 'none';
    }

    function drawProcessedStructure(length, width, height, floors) {
        drawGrid();
        
        // 簡單 2D 視覺化: 畫出一榀框架
        ctx.fillStyle = 'rgba(0, 242, 254, 0.2)';
        ctx.strokeStyle = '#00f2fe';
        ctx.lineWidth = 3;
        
        // 將畫布置中與縮放
        const marginX = 100;
        const marginY = 50;
        const drawWidth = canvas.width - marginX * 2;
        const drawHeight = canvas.height - marginY * 2;
        
        // 畫出樓層與柱
        const colWidth = 20;
        const beamHeight = 15;
        
        const floorHeightPx = drawHeight / floors;
        
        ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.strokeStyle = '#f0f0f0';
        
        // 左柱與右柱
        ctx.fillRect(marginX, marginY, colWidth, drawHeight);
        ctx.strokeRect(marginX, marginY, colWidth, drawHeight);
        ctx.fillRect(marginX + drawWidth - colWidth, marginY, colWidth, drawHeight);
        ctx.strokeRect(marginX + drawWidth - colWidth, marginY, colWidth, drawHeight);
        
        ctx.fillStyle = 'rgba(0, 242, 254, 0.2)';
        ctx.strokeStyle = '#00f2fe';
        
        // 畫每一層樑
        for (let i = 0; i <= floors; i++) {
            const yPos = marginY + i * floorHeightPx - (i===floors ? 0 : beamHeight/2);
            if (i > 0) { // 最底層不畫樑，通常是基礎
                ctx.fillRect(marginX, yPos, drawWidth, beamHeight);
                ctx.strokeRect(marginX, yPos, drawWidth, beamHeight);
            }
        }
    }
});
