const map = L.map('map').setView([0.0236, 37.9062], 7);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

// Initialize drawing features
const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const drawControl = new L.Control.Draw({
    draw: {
        polygon: true,
        marker: false,
        circle: false,
        polyline: false,
        rectangle: false
    },
    edit: {
        featureGroup: drawnItems
    }
});
map.addControl(drawControl);

// Handle drawn shapes
map.on('draw:created', function(e) {
    const layer = e.layer;
    drawnItems.addLayer(layer);
    
    // Get coordinates of the drawn polygon
    const coordinates = layer.getLatLngs()[0];
    updateLocationInfo(coordinates[0]);
    
    // Simulate risk assessment
    assessFloodRisk(coordinates);
});

// Geolocation function
function getCurrentLocation() {
    if ("geolocation" in navigator) {
        const loadingDiv = document.querySelector('.loading');
        loadingDiv.style.display = 'flex';
        
        navigator.geolocation.getCurrentPosition(function(position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            map.setView([lat, lng], 13);
            updateLocationInfo({lat: lat, lng: lng});
            
            // Create a marker at user's location
            L.marker([lat, lng]).addTo(map);
            
            loadingDiv.style.display = 'none';
        }, function(error) {
            console.error("Error getting location:", error);
            loadingDiv.style.display = 'none';
            alert("Unable to get your location. Please try again.");
        });
    } else {
        alert("Geolocation is not supported by your browser");
    }
}

// Update location information
function updateLocationInfo(coords) {
    const coordsDisplay = document.getElementById('coordinates');
    coordsDisplay.textContent = `Coordinates: ${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)}`;
    
    // Simulate finding nearest water body
    findNearestWaterBody(coords);
}

// Simulate finding nearest water body
function findNearestWaterBody(coords) {
    // This would normally call an API or database
    // Simulated response
    const waterBodies = {
        'Lake Victoria': [-0.7527, 33.4357],
        'Lake Nakuru': [-0.3667, 36.0833],
        'River Tana': [-0.4544, 39.6393]
    };
    
    // Find closest water body (simplified)
    let nearest = 'Lake Victoria';
    document.getElementById('nearest-water').textContent = `Nearest Water Body: ${nearest}`;
}

// Simulate flood risk assessment
function assessFloodRisk(coords) {
    const riskIndicator = document.getElementById('risk-indicator');
    
    // Simulate processing
    setTimeout(() => {
        // Random risk level for demonstration
        const risks = ['LOW', 'MEDIUM', 'HIGH'];
        const randomRisk = risks[Math.floor(Math.random() * risks.length)];
        const probability = Math.floor(Math.random() * 100);
        
        // Update UI
        riskIndicator.className = `risk-${randomRisk.toLowerCase()}`;
        riskIndicator.innerHTML = `
            <p>Current Risk: ${randomRisk}</p>
            <p>Probability: ${probability}%</p>
        `;
    }, 1000);
}