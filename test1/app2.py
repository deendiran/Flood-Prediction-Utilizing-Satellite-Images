# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import ee
import numpy as np
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
import json

# Initialize Earth Engine
try:
    ee.Initialize(project='ee-ndirangudenise61')
except:
    ee.Authenticate()
    ee.Initialize(project='ee-ndirangudenise61')


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Enable CORS for all routes and allow all origins
CORS(app, resources={r"/api/*": {"origins": "*"}})

def get_satellite_data(lat, lng, start_date, end_date):
    """Get satellite data from Google Earth Engine"""
    point = ee.Geometry.Point([lng, lat])
    
    # Get Sentinel-2 collection
    s2 = ee.ImageCollection('COPERNICUS/S2_SR') \
        .filterBounds(point) \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    
    if s2.size().getInfo() == 0:
        return None

    # Function to calculate indices
    def calculate_indices(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('ndvi')
        ndwi = image.normalizedDifference(['B3', 'B8']).rename('ndwi')
        return image.addBands([ndvi, ndwi])

    # Add indices to collection
    s2_with_indices = s2.map(calculate_indices)
    
    # Get the most recent image
    latest_image = s2_with_indices.sort('system:time_start', False).first()
    
    # Extract values at point
    values = latest_image.select(['ndvi', 'ndwi']).reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=point,
        scale=10
    ).getInfo()
    
    return values

def get_soil_moisture(lat, lng, start_date, end_date):
    """Get soil moisture data from Google Earth Engine"""
    point = ee.Geometry.Point([lng, lat])
    
    # Get SMAP Global Soil Moisture Data
    smap = ee.ImageCollection('NASA_USDA/HSL/SMAP_soil_moisture') \
        .filterBounds(point) \
        .filterDate(start_date, end_date)
    
    if smap.size().getInfo() == 0:
        return None

    latest = smap.sort('system:time_start', False).first()
    
    values = latest.select('ssm').reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=point,
        scale=10000
    ).getInfo()
    
    return values.get('ssm')

def get_water_level(lat, lng):
    """
    Get water level data
    In a production system, this would connect to actual water level sensors or
    hydrological databases. For demo, using simulated data.
    """
    base_level = 2.5  # Base water level in meters
    seasonal_variation = np.sin(datetime.now().timetuple().tm_yday / 365 * 2 * np.pi) * 0.5
    location_variation = (lat + lng) % 1 * 0.5
    
    return round(base_level + seasonal_variation + location_variation, 2)

def analyze_location(lat, lng):
    """Main analysis function"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)
    
    # Get current satellite data
    current_data = get_satellite_data(
        lat, lng,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    # Get current soil moisture
    soil_moisture = get_soil_moisture(
        lat, lng,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    # Get current water level
    water_level = get_water_level(lat, lng)
    
    # Get historical data
    historical_data = []
    for i in range(10):
        date = end_date - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        prev_date = date - timedelta(days=1)
        
        day_data = get_satellite_data(lat, lng, prev_date.strftime('%Y-%m-%d'), date_str)
        day_soil = get_soil_moisture(lat, lng, prev_date.strftime('%Y-%m-%d'), date_str)
        day_water = get_water_level(lat, lng) + (np.random.random() - 0.5) * 0.2
        
        if day_data:
            historical_data.append({
                'date': date_str,
                'ndvi': round(day_data.get('ndvi', 0), 3),
                'ndwi': round(day_data.get('ndwi', 0), 3),
                'soil_moisture': round(day_soil * 100 if day_soil else 0, 1),
                'water_level': round(day_water, 2)
            })
    
    # Calculate risk level
    if current_data:
        ndvi = current_data.get('ndvi', 0)
        ndwi = current_data.get('ndwi', 0)
        soil_moisture_normalized = soil_moisture if soil_moisture else 0
        
        risk_score = (
            (1 - ndvi) * 0.3 +  # Lower vegetation increases risk
            ndwi * 0.3 +        # Higher water content increases risk
            soil_moisture_normalized * 0.4  # Higher soil moisture increases risk
        )
        
        risk_level = 'HIGH' if risk_score > 0.7 else 'MEDIUM' if risk_score > 0.4 else 'LOW'
        confidence = min(100, max(0, risk_score * 100))
    else:
        risk_level = 'UNKNOWN'
        confidence = 0
        
    # Prepare response data
    response_data = {
        'location': {
            'latitude': lat,
            'longitude': lng
        },
        'current_conditions': {
            'ndvi': round(current_data.get('ndvi', 0), 3) if current_data else None,
            'ndwi': round(current_data.get('ndwi', 0), 3) if current_data else None,
            'soil_moisture': round(soil_moisture * 100 if soil_moisture else 0, 1),
            'water_level': water_level
        },
        'risk_assessment': {
            'level': risk_level,
            'confidence': round(confidence, 1)
        },
        'historical_data': historical_data
    }
    
    return response_data

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """API endpoint for flood risk analysis"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data or 'latitude' not in data or 'longitude' not in data:
            return jsonify({
                'error': 'Missing required parameters: latitude and longitude'
            }), 400
            
        lat = float(data['latitude'])
        lng = float(data['longitude'])
        
        # Validate coordinate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return jsonify({
                'error': 'Invalid coordinates. Latitude must be between -90 and 90, longitude between -180 and 180'
            }), 400
        
        # Perform analysis
        result = analyze_location(lat, lng)
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({
            'error': 'Invalid parameter format. Latitude and longitude must be numbers'
        }), 400
    except Exception as e:
        logger.error(f'Error processing request: {str(e)}')
        return jsonify({
            'error': 'Internal server error'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)