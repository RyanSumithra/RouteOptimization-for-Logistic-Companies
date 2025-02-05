import requests
import logging
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# API Keys
TOMTOM_API_KEY = "JSIKlxOiGNb6ZSNMieT31BOtGbGeKktv"
WEATHER_API_KEY = "6edc2c692702461e81750126250102"

# Constants for fuel cost calculation
FUEL_PRICE_PER_LITER = 100  # Example price in your currency
AVG_FUEL_CONSUMPTION = 10  # km/L - average consumption


def geocode(location):
    url = f'https://api.tomtom.com/search/2/geocode/{location}.json'
    params = {'key': TOMTOM_API_KEY, 'limit': 1}
    try:
        response = requests.get(url, params=params)
        logging.debug(f"Geocode Response: {response.text}")
        response.raise_for_status()
        data = response.json()
        if 'results' in data and data['results']:
            result = data['results'][0]
            return {
                'lat': result['position']['lat'],
                'lon': result['position']['lon'],
                'address': result['address'].get('freeformAddress', location)
            }
        logging.warning(f"No geocode results for {location}")
    except Exception as e:
        logging.error(f"Geocoding error: {e}")
    return None


def get_weather(lat, lon):
    url = f"http://api.weatherapi.com/v1/forecast.json"
    params = {
        'key': WEATHER_API_KEY,
        'q': f"{lat},{lon}",
        'days': 1
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        # Extract only the current weather information
        current_weather = weather_data.get('current', {})
        return {
            'condition': current_weather.get('condition', {}).get('text', 'N/A'),
            'temperature_c': current_weather.get('temp_c', 'N/A'),
            'temperature_f': current_weather.get('temp_f', 'N/A'),
            'wind_kph': current_weather.get('wind_kph', 'N/A'),
            'humidity': current_weather.get('humidity', 'N/A'),
            # Add more details as needed
        }
    except Exception as e:
        logging.error(f"Weather API error: {e}")
        return None


def calculate_fuel_cost(distance_km):
    # Calculate fuel consumption and cost
    fuel_consumed = distance_km / AVG_FUEL_CONSUMPTION  # in liters
    return fuel_consumed * FUEL_PRICE_PER_LITER


def calculate_routes(waypoints):
    url = f'https://api.tomtom.com/routing/1/calculateRoute/{":".join(waypoints)}/json'
    params = {
        'key': TOMTOM_API_KEY,
        'routeType': 'fastest',
        'traffic': 'true',
        'travelMode': 'car',
        'maxAlternatives': 3,
        'computeTravelTimeFor': 'all'  # Get real-time traffic info
    }
    try:
        response = requests.get(url, params=params)
        logging.debug(f"Routing Response: {response.text}")
        response.raise_for_status()
        data = response.json()

        routes = []
        if 'routes' in data and data['routes']:
            for route in data['routes']:
                # Calculate fuel cost for this route
                distance_km = route['summary']['lengthInMeters'] / 1000
                fuel_cost = calculate_fuel_cost(distance_km)

                routes.append({
                    'points': [{'latitude': p['latitude'], 'longitude': p['longitude']}
                               for p in route['legs'][0]['points']],
                    'summary': route['summary'],
                    'fuel_cost': round(fuel_cost, 2)
                })
            return routes
        logging.warning("No routes found")
    except Exception as e:
        logging.error(f"Routing error: {e}")
    return None


@app.route('/')
def index():
    return render_template('index.html', tomtom_api_key=TOMTOM_API_KEY)


@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('query', '')
    if not query:
        return jsonify([])

    url = f'https://api.tomtom.com/search/2/autocomplete/{query}.json'
    params = {
        'key': TOMTOM_API_KEY,
        'limit': 5  # Adjust as needed
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        if 'results' in data:
            for result in data['results']:
                results.append({
                    'label': result.get('address', {}).get('freeformAddress',
                                                             result.get('poi', {}).get('name', 'Unknown')),
                    'value': result.get('address', {}).get('freeformAddress',
                                                             result.get('poi', {}).get('name', 'Unknown'))
                })
        return jsonify(results)

    except requests.exceptions.RequestException as e:
        logging.error(f"Autocomplete error: {e}")
        return jsonify([])


@app.route('/calculate_route', methods=['POST'])
def calculate_route():
    start = request.form.get('start')
    end = request.form.get('end')

    logging.info(f"Calculating route from {start} to {end}")

    start_location = geocode(start)
    end_location = geocode(end)

    if not start_location or not end_location:
        return jsonify({
            'success': False,
            'message': 'Could not find one or both locations'
        })

    waypoints = [f"{start_location['lat']},{start_location['lon']}",
                 f"{end_location['lat']},{end_location['lon']}"]

    # Get weather information for start and end
    start_weather = get_weather(start_location['lat'], start_location['lon'])
    end_weather = get_weather(end_location['lat'], end_location['lon'])

    routes = calculate_routes(waypoints)

    if not routes:
        return jsonify({
            'success': False,
            'message': 'No routes found'
        })

    route_data = []
    for route in routes:
        route_data.append({
            'route': route['points'],
            'summary': route['summary'],
            'fuel_cost': route['fuel_cost']
        })

    return jsonify({
        'success': True,
        'start': start_location,
        'end': end_location,
        'routes': route_data,
        'weather': {
            'start': start_weather,
            'end': end_weather
        }
    })


if __name__ == '__main__':
    app.run(debug=True)
