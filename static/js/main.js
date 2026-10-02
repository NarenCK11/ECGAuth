(function(){
  document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('ecg-form');
    const result = document.getElementById('result');
    const busy = document.getElementById('busy');
    const btn = document.getElementById('predictBtn');

    const waveCanvas = document.getElementById('waveCanvas');
    let waveform = [];

    // Theme toggle & persistence
    const root = document.documentElement;
    const themeToggle = document.getElementById('themeToggle');
    const saved = localStorage.getItem('theme');
    if(saved) root.setAttribute('data-theme', saved);
    themeToggle?.addEventListener('click', ()=>{
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });

    // Show selected filenames in dropzones
    const heaInput = document.getElementById('heaFile');
    const datInput = document.getElementById('datFile');
    const heaName  = document.getElementById('heaName');
    const datName  = document.getElementById('datName');

    heaInput?.addEventListener('change', ()=>{
      heaName.textContent = heaInput.files?.[0]?.name || 'No file selected';
    });
    datInput?.addEventListener('change', ()=>{
      datName.textContent = datInput.files?.[0]?.name || 'No file selected';
    });

    // Canvas sizing (hi-dpi aware)
    function sizeCanvasForDPR(canvas){
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width  = Math.max(300, Math.floor(rect.width  * dpr));
      canvas.height = Math.max(160, Math.floor(rect.height * dpr));
      const ctx = canvas.getContext('2d');
      ctx.setTransform(1,0,0,1,0,0);     // reset
      ctx.scale(dpr, dpr);               // draw in CSS pixels
      return ctx;
    }

    function drawWaveform(){
      if(!waveCanvas || !waveform.length) return;
      const ctx = sizeCanvasForDPR(waveCanvas);
      const w = waveCanvas.getBoundingClientRect().width;
      const h = waveCanvas.getBoundingClientRect().height;

      ctx.clearRect(0,0,w,h);

      // axis
      ctx.globalAlpha = 0.5;
      ctx.strokeStyle = '#445';
      ctx.beginPath();
      ctx.moveTo(0, h/2);
      ctx.lineTo(w, h/2);
      ctx.stroke();

      // signal
      ctx.globalAlpha = 1;
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#9fd';

      const n = waveform.length;
      const min = Math.min.apply(null, waveform);
      const max = Math.max.apply(null, waveform);
      const rng = (max - min) || 1;

      ctx.beginPath();
      for(let i=0;i<w;i++){
        const idx = Math.floor(i*(n-1)/(w-1));
        const v = (waveform[idx] - min) / rng;   // 0..1
        const y = h - v*h;                       // invert to canvas coords
        if(i===0) ctx.moveTo(0, y); else ctx.lineTo(i, y);
      }
      ctx.stroke();
    }

    window.addEventListener('resize', drawWaveform);

    function showJSON(json){
      if(json.error){
        result.innerHTML = `<div class="glass" style="padding:12px;border-radius:12px;">❌ ${json.error}</div>`;
        return;
      }
      const simPct = ((json.similarity ?? 0) * 100).toFixed(2);
      const thresh = json.threshold ? ` <span class="muted small">(threshold: ${(json.threshold*100).toFixed(0)}%)</span>` : '';
      result.innerHTML = `
        <div class="result-card-large glass" style="padding:16px;border-radius:14px;">
          <p><strong>Predicted:</strong> ${json.predicted_name} (ID ${json.predicted_label ?? '—'})</p>
          <p><strong>Similarity:</strong> ${simPct}%${thresh}</p>
          ${json.authenticated!==undefined ? `<p><strong>Authenticated:</strong> ${json.authenticated ? '✅ YES' : '❌ NO'}</p>` : ''}
        </div>`;

      if(Array.isArray(json.waveform)){
        waveform = json.waveform.slice(0); // copy
        drawWaveform();
      }
    }

    if(form){
      form.addEventListener('submit', async function(e){
        e.preventDefault();
        const fd = new FormData(form);
        busy.style.display = 'inline-block';
        btn.disabled = true;
        try{
          const res  = await fetch(form.action, { method:'POST', body: fd });
          const json = await res.json();
          showJSON(json);
        }catch(err){
          result.innerHTML = `<div class="glass" style="padding:12px;border-radius:12px;">❌ Request failed</div>`;
        }finally{
          busy.style.display = 'none';
          btn.disabled = false;
        }
      });
    }
  });
})();
