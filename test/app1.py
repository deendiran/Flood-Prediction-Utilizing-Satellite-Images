# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import rasterio
import numpy as np
from shapely.geometry import Point, Polygon
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import json
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# JWT Configuration (for authenticated version)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
jwt = JWTManager(app)

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'flood_prediction_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '1234'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Water body detection
def detect_water_body(lat, lng):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Query to find nearest water body within 10km radius
        cur.execute("""
            SELECT name, type, 
                   ST_Distance(
                       geometry::geography, 
                       ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                   ) as distance
            FROM water_bodies
            WHERE ST_DWithin(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                10000  -- 10km radius
            )
            ORDER BY distance
            LIMIT 1;
        """, (lng, lat, lng, lat))
        
        result = cur.fetchone()
        return result if result else None
        
    finally:
        cur.close()
        conn.close()

# Analyze vegetation cover
def analyze_vegetation(lat, lng):
    try:
        # This would normally use satellite imagery analysis
        # For demo, returning mock data based on location
        base_ndvi = 0.5  # Base NDVI value
        lat_factor = abs(lat) / 90  # Latitude influence
        ndvi = base_ndvi + (lat_factor * 0.3)  # Adjust NDVI based on latitude
        
        return {
            'ndvi': min(1.0, max(0.0, ndvi)),
            'vegetation_density': 'moderate',
            'change_past_10_days': round(np.random.uniform(-0.1, 0.1), 3)
        }
    except Exception as e:
        return None

# Analyze soil moisture
def analyze_soil_moisture(lat, lng):
    try:
        # Mock soil moisture calculation
        base_moisture = 0.4  # Base moisture value
        moisture = base_moisture + np.random.uniform(-0.1, 0.1)
        
        return {
            'moisture_content': round(moisture, 2),
            'saturation_level': 'moderate',
            'trend': 'stable'
        }
    except Exception as e:
        return None

# Calculate flood risk
def calculate_flood_risk(water_body, vegetation, soil_moisture):
    if not all([water_body, vegetation, soil_moisture]):
        return {'risk_level': 'unknown', 'confidence': 0}
    
    # Risk factors
    distance_factor = 1.0
    if water_body and water_body['distance']:
        distance_factor = max(0.1, min(1.0, 5000 / water_body['distance']))
    
    vegetation_factor = 1.0 - vegetation['ndvi']
    moisture_factor = soil_moisture['moisture_content']
    
    # Combined risk calculation
    risk_score = (distance_factor * 0.4 + 
                 vegetation_factor * 0.3 + 
                 moisture_factor * 0.3)
    
    # Risk level determination
    if risk_score > 0.7:
        risk_level = 'high'
    elif risk_score > 0.4:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    confidence = min(100, max(0, risk_score * 100))
    
    return {
        'risk_level': risk_level,
        'confidence': round(confidence, 1),
        'risk_score': round(risk_score, 2)
    }

# API Routes
@app.route('/api/analyze', methods=['POST'])
def analyze_location():
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    
    if not all([lat, lng]):
        return jsonify({'error': 'Missing coordinates'}), 400
    
    try:
        # Perform analysis
        water_body = detect_water_body(lat, lng)
        vegetation = analyze_vegetation(lat, lng)
        soil_moisture = analyze_soil_moisture(lat, lng)
        risk_analysis = calculate_flood_risk(water_body, vegetation, soil_moisture)
        
        # Store results in database
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO flood_predictions 
            (latitude, longitude, water_body_id, risk_level, 
             vegetation_index, soil_moisture, prediction_date)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (lat, lng, 
              water_body['id'] if water_body else None,
              risk_analysis['risk_level'],
              vegetation['ndvi'],
              soil_moisture['moisture_content']))
        
        prediction_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({
            'id': prediction_id,
            'water_body': water_body,
            'vegetation': vegetation,
            'soil_moisture': soil_moisture,
            'risk_analysis': risk_analysis,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Authentication routes (for authenticated version)
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not all([username, password, email]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if username exists
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({'error': 'Username already exists'}), 409
        
        # Insert new user
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password)  # In production, hash the password!
        )
        conn.commit()
        
        return jsonify({'message': 'User registered successfully'}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'error': 'Missing credentials'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            "SELECT id, username FROM users WHERE username = %s AND password_hash = %s",
            (username, password)  # In production, verify hashed password!
        )
        user = cur.fetchone()
        
        if user:
            access_token = create_access_token(identity=user['id'])
            return jsonify({
                'access_token': access_token,
                'username': user['username']
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)