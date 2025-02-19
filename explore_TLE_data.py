import requests
from datetime import datetime, timedelta
import pandas as pd


from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv



def get_celestrak_data(catalog_number=None, satellite_name=None, dataset='active'): 
    """
    Fetch TLE data from Celestrak's API 
    
    Parameters: 
    - catalog_number: NORAD catalog number (int)
    - satellite_name: Name of satellite (str)
    - dataset: Predefined dataset like 'active', 'stations', 'visual', etc.
    
    Returns: List of TLE data
    """
    base_url = "https://celestrak.org/NORAD/elements/gp.php"
    
    #setup parameters
    params = {'FORMAT': 'TLE'}
    
    if catalog_number:
        params['CATNR'] = str(catalog_number)
    elif satellite_name:
        params['NAME'] = satellite_name
    else:
        # If no specific satellite, get predefined dataset
        params['GROUP'] = dataset
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Print response status and URL for debugging
        # print(f"Request URL: {response.url}")
        # print(f"Status Code: {response.status_code}")
        
        # Split response into individual TLEs (3 lines each)
        tle_data = response.text.strip().split('\n')
        
        # Print raw data length for debugging
        # print(f"Received {f(tle_data)} lines of data\n")
        
        # Group into sets of three lines
        tle_sets = [tle_data[i:i+3] for i in range(0, len(tle_data), 3)]
        
        return tle_sets
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def main():
    
    iss_tles = get_celestrak_data(catalog_number=25544)#get ISS data
    # Example of processing the data
    if iss_tles:
        for tle_set in iss_tles:
            name = tle_set[0].strip()
            line1 = tle_set[1]
            line2 = tle_set[2]
            print(f"Satellite: {name}")
            print(f"Line 1: {line1}")
            print(f"Line 2: {line2}")
    
    #Convert TLE values into tabular form