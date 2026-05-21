const API_BASE = "";

document.addEventListener("DOMContentLoaded", () => {
    cargarEstadisticas();

    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");

    // Drag and drop events
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
    });

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
        document.getElementById("stat-monto").innerText = `$${(stats.monto_total || 0).toFixed(2)}`;
        document.getElementById("stat-exitosas").innerText = stats.exitosas || 0;
    } catch (e) {
        console.error("Error cargando estadísticas", e);
    }
}

async function procesarFactura(file) {
    const statusMsg = document.getElementById("upload-status");
    const resultPlaceholder = document.getElementById("result-placeholder");
    const resultData = document.getElementById("result-data");
    const alertsContainer = document.getElementById("alerts-container");
    const alertsList = document.getElementById("alerts-list");

    // UI Updates
    statusMsg.classList.remove("hidden");
    statusMsg.innerText = "Procesando factura con IA, por favor espera...";
    resultPlaceholder.classList.remove("hidden");
    resultData.classList.add("hidden");

    const formData = new FormData();
    formData.append("archivo", file);

    try {
        const res = await fetch(`${API_BASE}/facturas/`, {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            throw new Error(`Error HTTP: ${res.status}`);
        }

        const data = await res.json();
        const f = data.factura;

        // Populate results
        document.getElementById("res-nombre").innerText = f.proveedor_nombre || "No detectado";
        document.getElementById("res-ruc").innerText = f.proveedor_ruc || "No detectado";
        document.getElementById("res-total").innerText = f.total ? `$${f.total.toFixed(2)}` : "No detectado";
        
        let conf = f.confianza_ocr ? `${f.confianza_ocr.toFixed(1)}%` : "0%";
        document.getElementById("res-confianza").innerText = conf;
        
        let estadoEl = document.getElementById("res-estado");
        estadoEl.innerText = f.estado;
        estadoEl.style.color = f.estado === "EXITO" ? "var(--success)" : "var(--warning)";

        // Handle alerts
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

        // Show results
        statusMsg.innerText = "¡Factura procesada con éxito!";
        statusMsg.style.color = "var(--success)";
        setTimeout(() => statusMsg.classList.add("hidden"), 3000);

        resultPlaceholder.classList.add("hidden");
        resultData.classList.remove("hidden");

        // Update global stats
        cargarEstadisticas();

    } catch (e) {
        console.error(e);
        statusMsg.innerText = "Error procesando la factura.";
        statusMsg.style.color = "var(--danger)";
    }
}
