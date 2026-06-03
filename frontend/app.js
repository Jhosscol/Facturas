const API_BASE = "";
let currentInvoiceData = null;

// Global state
let selectedInvoiceIds = new Set();
let ultimoIdFactura = null;
let todasLasFacturas = [];

document.addEventListener("DOMContentLoaded", () => {
    cargarEstadisticas();
    cargarFacturas();

    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const selectAllCheckbox = document.getElementById("select-all");
    const btnExportar = document.getElementById("btn-exportar");
    const btnAddLast = document.getElementById("btn-add-last");

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

    // Select all logic
    selectAllCheckbox.addEventListener("change", (e) => {
        const checked = e.target.checked;
        todasLasFacturas.forEach(f => {
            if (checked) {
                selectedInvoiceIds.add(f.id);
            } else {
                selectedInvoiceIds.delete(f.id);
            }
        });
        
        // Update all individual checkboxes in table
        document.querySelectorAll(".factura-checkbox").forEach(cb => {
            cb.checked = checked;
        });
        
        actualizarBotonExportar();
        actualizarBotonUltimaFactura();
    });

    // Export button click
    btnExportar.addEventListener("click", () => {
        if (selectedInvoiceIds.size === 0) return;
        const idsStr = Array.from(selectedInvoiceIds).join(",");
        window.location.href = `${API_BASE}/facturas/exportar/excel/?ids=${idsStr}`;
    });

    // Add last invoice click
    btnAddLast.addEventListener("click", () => {
        if (!ultimoIdFactura) return;
        
        if (selectedInvoiceIds.has(ultimoIdFactura)) {
            // Remove
            selectedInvoiceIds.delete(ultimoIdFactura);
        } else {
            // Add
            selectedInvoiceIds.add(ultimoIdFactura);
        }
        
        // Refresh table checkboxes
        const cb = document.querySelector(`.factura-checkbox[data-id="${ultimoIdFactura}"]`);
        if (cb) {
            cb.checked = selectedInvoiceIds.has(ultimoIdFactura);
        }
        
        // Check if all are selected to update the master checkbox
        actualizarMasterCheckbox();
        actualizarBotonExportar();
        actualizarBotonUltimaFactura();
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

async function cargarFacturas() {
    const tbody = document.getElementById("facturas-tbody");
    try {
        const res = await fetch(`${API_BASE}/facturas/`);
        if (!res.ok) throw new Error("Error obteniendo facturas");
        
        const data = await res.json();
        todasLasFacturas = data.facturas || [];
        
        if (todasLasFacturas.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="placeholder-text" style="text-align: center; padding: 2rem; font-style: italic;">
                        No hay facturas procesadas disponibles.
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = "";
        todasLasFacturas.forEach(f => {
            const tr = document.createElement("tr");
            
            const isChecked = selectedInvoiceIds.has(f.id) ? "checked" : "";
            const totalStr = f.total ? `$${f.total.toFixed(2)}` : "No detectado";
            const confianzaStr = f.confianza_ocr ? `${f.confianza_ocr.toFixed(1)}%` : "0%";
            const estadoColor = f.estado === "EXITO" ? "var(--success)" : "var(--warning)";
            const fechaEmisionStr = f.fecha_emision || "-";
            
            tr.innerHTML = `
                <td style="text-align: center;">
                    <input type="checkbox" class="factura-checkbox" data-id="${f.id}" ${isChecked}>
                </td>
                <td><strong>${f.numero_factura || "-"}</strong></td>
                <td>${f.proveedor_nombre || "No detectado"}</td>
                <td>${f.proveedor_ruc || "-"}</td>
                <td>${f.cliente_nombre || "No detectado"}</td>
                <td>${fechaEmisionStr}</td>
                <td><strong style="color: #a78bfa;">${totalStr}</strong></td>
                <td>${confianzaStr}</td>
                <td style="color: ${estadoColor}; font-weight: 500;">${f.estado}</td>
            `;
            
            tbody.appendChild(tr);
        });
        
        // Add events to checkboxes
        document.querySelectorAll(".factura-checkbox").forEach(cb => {
            cb.addEventListener("change", (e) => {
                const id = parseInt(e.target.dataset.id);
                if (e.target.checked) {
                    selectedInvoiceIds.add(id);
                } else {
                    selectedInvoiceIds.delete(id);
                }
                actualizarMasterCheckbox();
                actualizarBotonExportar();
                actualizarBotonUltimaFactura();
            });
        });
        
        actualizarMasterCheckbox();
        
    } catch (e) {
        console.error("Error cargando tabla de facturas", e);
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="placeholder-text" style="text-align: center; padding: 2rem; color: var(--danger);">
                    Error al cargar las facturas de la base de datos.
                </td>
            </tr>
        `;
    }
}

function actualizarMasterCheckbox() {
    const selectAllCheckbox = document.getElementById("select-all");
    if (!selectAllCheckbox) return;
    
    if (todasLasFacturas.length === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.disabled = true;
        return;
    }
    
    selectAllCheckbox.disabled = false;
    const allSelected = todasLasFacturas.every(f => selectedInvoiceIds.has(f.id));
    selectAllCheckbox.checked = allSelected;
}

function actualizarBotonExportar() {
    const btn = document.getElementById("btn-exportar");
    const count = document.getElementById("export-count");
    if (!btn || !count) return;
    
    count.innerText = selectedInvoiceIds.size;
    btn.disabled = selectedInvoiceIds.size === 0;
}

function actualizarBotonUltimaFactura() {
    const btn = document.getElementById("btn-add-last");
    if (!btn) return;
    
    if (!ultimoIdFactura) {
        btn.disabled = true;
        btn.innerText = "Añadir a la lista de exportación";
        btn.classList.remove("added");
        return;
    }
    
    btn.disabled = false;
    if (selectedInvoiceIds.has(ultimoIdFactura)) {
        btn.innerText = "✓ Añadido a la exportación";
        btn.classList.add("added");
    } else {
        btn.innerText = "Añadir a la lista de exportación";
        btn.classList.remove("added");
    }
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
        cargarFacturas();

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
