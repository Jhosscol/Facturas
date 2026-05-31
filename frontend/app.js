const API_BASE = "";
let currentInvoiceData = null;

document.addEventListener("DOMContentLoaded", () => {
    cargarEstadisticas();

    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");

    // Eventos interactivos para los campos
    document.querySelectorAll(".interactive").forEach(el => {
        el.addEventListener("mouseenter", () => highlightBox(el.dataset.field));
        el.addEventListener("mouseleave", () => clearHighlights());
    });

    // Drag and drop events
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
    dropZone.addEventListener("dragleave", (e) => { e.preventDefault(); dropZone.classList.remove("dragover"); });
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            procesarFactura(fileInput.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (fileInput.files.length) {
            procesarFactura(fileInput.files[0]);
        }
    });
});

async function cargarEstadisticas() {
    try {
        const res = await fetch(`${API_BASE}/estadisticas/`);
        const data = await res.json();
        const stats = data.estadisticas;
        document.getElementById("stat-total").innerText = stats.total || 0;
        document.getElementById("stat-monto").innerText = `S/. ${(stats.monto_total || 0).toFixed(2)}`;
        document.getElementById("stat-exitosas").innerText = stats.exitosas || 0;
    } catch (e) { console.error("Error cargando estadísticas", e); }
}

async function procesarFactura(file) {
    const statusMsg = document.getElementById("upload-status");
    const resultPlaceholder = document.getElementById("result-placeholder");
    const resultData = document.getElementById("result-data");
    const imageWrapper = document.getElementById("image-wrapper");
    const viewerPlaceholder = document.getElementById("viewer-placeholder");
    const facturaImg = document.getElementById("factura-img");

    statusMsg.classList.remove("hidden");
    statusMsg.innerText = "Analizando documento...";
    
    const formData = new FormData();
    formData.append("archivo", file);

    try {
        const res = await fetch(`${API_BASE}/facturas/`, { method: "POST", body: formData });
        if (!res.ok) throw new Error(`Error HTTP: ${res.status}`);

        const data = await res.json();
        const f = data.factura;
        currentInvoiceData = f;

        // Renderizar Imagen
        facturaImg.src = `${API_BASE}${f.url_imagen}?t=${Date.now()}`;
        facturaImg.onload = () => {
            viewerPlaceholder.classList.add("hidden");
            imageWrapper.classList.remove("hidden");
            dibujarCajas(f.coordenadas, facturaImg.naturalWidth, facturaImg.naturalHeight);
        };

        // Llenar datos
        document.getElementById("res-nombre").innerText = f.proveedor_nombre || "No detectado";
        document.getElementById("res-ruc").innerText = f.proveedor_ruc || "No detectado";
        document.getElementById("res-factura").innerText = f.numero_factura || "No detectado";
        document.getElementById("res-fecha").innerText = f.fecha_emision || "No detectado";
        const sym = f.simbolo_moneda || "S/.";
        document.getElementById("res-subtotal").innerText = f.subtotal ? `${sym} ${f.subtotal.toFixed(2)}` : "-";
        document.getElementById("res-igv").innerText = f.igv ? `${sym} ${f.igv.toFixed(2)}` : "-";
        document.getElementById("res-total").innerText = f.total ? `${sym} ${f.total.toFixed(2)}` : "No detectado";
        
        const conf = f.confianza_ocr || 0;
        document.getElementById("res-confianza-bar").style.width = `${conf}%`;
        document.getElementById("res-confianza-txt").innerText = `${conf.toFixed(1)}%`;

        // Botón de exportar
        document.getElementById("btn-export-csv").onclick = () => exportarCSV(f);

        // Alertas
        const alertsContainer = document.getElementById("alerts-container");
        const alertsList = document.getElementById("alerts-list");
        if (f.alertas && f.alertas.length > 0) {
            alertsList.innerHTML = "";
            f.alertas.forEach(a => {
                let li = document.createElement("li");
                li.innerText = a;
                alertsList.appendChild(li);
            });
            alertsContainer.classList.remove("hidden");
        } else {
            alertsContainer.classList.add("hidden");
        }

        statusMsg.innerText = "¡Procesado!";
        setTimeout(() => statusMsg.classList.add("hidden"), 2000);
        resultPlaceholder.classList.add("hidden");
        resultData.classList.remove("hidden");
        cargarEstadisticas();

    } catch (e) {
        console.error(e);
        statusMsg.innerText = "Error en el servidor";
        statusMsg.style.color = "var(--danger)";
    }
}

function dibujarCajas(coordenadas, naturalWidth, naturalHeight) {
    const svg = document.getElementById("ocr-overlay");
    svg.innerHTML = "";
    // Ajustar el ViewBox al tamaño natural de la imagen
    svg.setAttribute("viewBox", `0 0 ${naturalWidth} ${naturalHeight}`);

    for (let campo in coordenadas) {
        const [x, y, w, h] = coordenadas[campo];
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", x);
        rect.setAttribute("y", y);
        rect.setAttribute("width", w);
        rect.setAttribute("height", h);
        rect.setAttribute("class", "highlight-box");
        rect.setAttribute("id", `box-${campo}`);
        svg.appendChild(rect);
    }
}

function highlightBox(field) {
    if (!field) return;
    const box = document.getElementById(`box-${field}`);
    if (box) box.classList.add("active");
}

function clearHighlights() {
    document.querySelectorAll(".highlight-box").forEach(b => b.classList.remove("active"));
}

function exportarCSV(f) {
    const headers = ["Proveedor", "RUC", "Factura", "Fecha", "Subtotal", "IGV", "Total"];
    const row = [
        f.proveedor_nombre,
        f.proveedor_ruc,
        f.numero_factura,
        f.fecha_emision,
        f.subtotal,
        f.igv,
        f.total
    ];
    
    let csvContent = "data:text/csv;charset=utf-8," 
        + headers.join(",") + "\n"
        + row.join(",");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `ERP_${f.numero_factura || 'factura'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
